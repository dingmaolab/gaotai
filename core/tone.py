"""AI 味检测：五维评分 + 定位 + 修改建议。

借鉴 Lieflat Less AI Tone 的七项能力：
  1 句式检测 → PATTERNS（可定位到行）
  2 排比重复 → 三连排比 / 4-gram / 段落开头雷同
  3 语义补充 → 交给上层模型，本模块只出机械证据
  4 指标+例句+建议 → findings
  5 最小改写 → 由调用方按 suggestion 施加，本模块不改原文
  6 复测对比 → compare()
  7 误判保护 → 引号内豁免 + 账号基线相对判断

关键设计：**AI 味 = 偏离「你自己」**，不是偏离某个通用人类基线。
传入 baseline 时按你的习惯判，避免把"一段一句""不用感叹号"当成机器味。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

DIMS = ["sentence", "parallelism", "lexicon", "structure", "punctuation"]
DIM_LABEL = {
    "sentence": "句式", "parallelism": "排比重复", "lexicon": "词汇",
    "structure": "结构", "punctuation": "标点",
}


@dataclass
class Rule:
    id: str
    pattern: re.Pattern
    dim: str
    level: str          # warn | info
    label: str
    fix: str


def _r(id: str, pat: str, dim: str, level: str, label: str, fix: str) -> Rule:
    return Rule(id, re.compile(pat), dim, level, label, fix)


# 43 条中文 AI 写作高频句式。刻意保守：宁少标，不乱标。
PATTERNS: list[Rule] = [
    _r("not-only-but", r"不仅[^。！？\n]{0,30}(而且|还|更)", "sentence", "warn", "「不仅…而且…」递进句", "拆成两句，或直接说结论"),
    _r("worth-noting", r"(值得注意|值得关注|需要指出|需要强调)(的是)?[，,]", "sentence", "warn", "「值得注意的是」类填充", "删掉，直接说事"),
    _r("in-this-era", r"在(这个|当今|如今)[^。！？\n]{0,12}(时代|社会|环境)", "sentence", "warn", "「在这个…的时代」空泛起手", "换具体场景或时间"),
    _r("with-development", r"随着[^。！？\n]{0,20}(的发展|的普及|的兴起|的进步)", "sentence", "warn", "「随着…的发展」", "换成因果事实"),
    _r("firstly-secondly", r"(首先|第一)[，,][^。！？\n]{0,80}(其次|第二|再次|然后)[，,]", "sentence", "warn", "「首先…其次…」机械罗列", "直接列事实，或用真实顺序"),
    _r("in-conclusion", r"(总而言之|综上所述|总的来说|总之)[，,：:]", "sentence", "warn", "「总而言之」总结段起手", "删掉，总结段直接写判断"),
    _r("it-is-obvious", r"(不难发现|可以看出|由此可见|可见)[，,]", "sentence", "warn", "「不难发现」", "删掉，直接给结论"),
    _r("as-we-know", r"(众所周知|毋庸置疑|不言而喻)", "sentence", "warn", "「众所周知」", "要么给来源，要么删"),
    _r("lets-together", r"让我们(一起)?|一起来(看|看下|了解)", "sentence", "warn", "「让我们一起」号召式", "删掉"),
    _r("in-a-sense", r"从某种程度上(说|讲)|在某种意义上", "sentence", "info", "「从某种意义上说」", "能删就删"),
    _r("on-one-hand", r"一方面[^。！？\n]{0,40}另一方面", "sentence", "warn", "「一方面…另一方面」", "拆成两句，说清取舍"),
    _r("more-importantly", r"更重要的是[，,]|更为关键的是", "sentence", "info", "「更重要的是」", "如果真是重点，直接说重点"),
    _r("at-the-same-time", r"与此同时[，,]", "sentence", "info", "「与此同时」", "用具体时间替代"),
    _r("in-other-words", r"换句话说[，,]|简而言之[，,]|一言以蔽之", "sentence", "info", "「换句话说」", "删掉，直接说"),
    _r("ultimately", r"归根结底[，,]|说到底[，,]", "sentence", "info", "「归根结底」", "偶尔可用，密度高就删"),
    _r("needless-to-say", r"毫无疑问[，,]|可以肯定的说[，,]?", "sentence", "warn", "「毫无疑问」", "要么给证据，要么删"),
    _r("it-can-be-said", r"可以说[，,]", "sentence", "info", "「可以说」", "删掉"),
    _r("simply-put", r"简单来说[，,]|简单来讲[，,]", "sentence", "info", "「简单来说」", "如果真简单，直接说"),
    _r("as-a-xxx", r"作为(一[名个位])[^，。]{2,10}[，,]", "sentence", "info", "「作为一名…」身份起手", "除非真的需要身份"),
    _r("this-is-not-only", r"这不仅是[^。！？\n]{0,30}(更是|也是)", "parallelism", "warn", "「这不仅是…更是…」", "拆开说"),
    _r("last-but-not-least", r"最后但同样重要的是|最后同样重要的是", "sentence", "warn", "「最后但同样重要的是」", "删掉"),
    _r("as-mentioned", r"如前所述|正如前面(所说|提到的)", "sentence", "info", "「如前所述」", "删掉"),
    _r("no-matter-whether", r"无论是[^。！？\n]{0,25}还是", "sentence", "info", "「无论是…还是…」", "举一个具体例子"),
    _r("adverb-inflate", r"(极大地|显著地|大幅度地?|全面地|充分地|深入地|有效地)", "lexicon", "warn", "程度副词堆砌", "换成数字"),
    _r("buzzword", r"(赋能|抓手|闭环|底层逻辑|颗粒度|组合拳|护城河|降维打击|破圈|生态位|第二曲线|增长飞轮|北极星指标)", "lexicon", "warn", "互联网黑话", "换成大白话"),
    _r("vague-boost", r"(全面提升|深度赋能|全面升级|强力支撑|有效促进|持续推动)", "lexicon", "warn", "空泛动词短语", "写清具体做了什么"),
    _r("hollow-adj", r"(强大的|丰富的|完善的|卓越的|领先的|优质的|高效的)", "lexicon", "info", "空洞形容词", "删掉或给证据"),
    _r("three-part-enum", r"(三[个种大]?(方面|维度|层面|关键)|几点(思考|建议|体会))", "structure", "info", "「三个方面」式预告", "直接讲第一个"),
    _r("let-me-share", r"(分享一下|聊聊我的|谈谈我的)(看法|想法|理解|经验)", "structure", "info", "「聊聊我的看法」", "直接给看法"),
    _r("hope-helpful", r"(希望[^。！？\n]{0,12}对你有(所)?帮助|希望[^。！？\n]{0,12}有所启发|以上就是全部内容)", "structure", "warn", "「希望对你有帮助」结尾", "换成具体判断或留白"),
    _r("summary-list", r"^(最后|总结一下)[，,：:]?\s*$", "structure", "info", "「最后总结一下」独立成段", "直接写结论"),
]

EXEMPT_PATTERNS = [
    re.compile(r"引用|原文|他说|她说|作者(说|写|认为)|书上|报告(说|里)"),
    re.compile(r"反例|错误(的)?说法|常见的(误区|错误)|有人(说|认为)"),
    re.compile(r"「[^」]{0,20}」|\"[^\"]{0,20}\"|\u201c[^\u201d]{0,20}\u201d"),
]

CLICHES = [
    "总而言之", "综上所述", "总的来说", "总之", "一言以蔽之",
    "不难发现", "可以看出", "由此可见", "可见", "众所周知", "毋庸置疑", "不言而喻",
    "值得注意的是", "值得关注", "需要指出", "需要强调", "更重要的是", "更为关键",
    "在这个快节奏的时代", "在这个信息爆炸的时代", "随着科技的发展", "随着社会的发展", "随着互联网的普及",
    "在当今社会", "在当今时代", "如今的社会",
    "让我们一起", "一起来看", "接下来我们", "下面我们来看",
    "赋能", "抓手", "闭环", "底层逻辑", "颗粒度", "组合拳", "护城河", "降维打击",
    "破圈", "生态位", "第二曲线", "增长飞轮", "北极星指标", "顶层设计", "全链路", "端到端",
    "打造", "助力", "深耕", "迭代升级", "全面升级", "强力支撑",
    "极大地", "显著地", "大幅度", "全面提升", "深度赋能", "有效促进", "持续推动",
    "强大的", "丰富的", "完善的", "卓越的", "领先的", "优质的", "高效的", "全方位",
    "家人们", "谁懂啊", "yyds", "绝绝子", "天花板级别", "一整个爱住", "直接封神", "狠狠拿捏", "炸裂",
    "希望对你有帮助", "希望对你有所启发", "以上就是全部内容", "感谢阅读", "码字不易",
    "干货满满", "强烈建议收藏", "不看后悔", "必看",
    "开启新篇章", "谱写新篇章", "新的征程", "新的起点",
    "深度融合", "协同发力", "双向奔赴", "久久为功", "行稳致远", "高质量发展",
    "客观来讲", "客观来说", "事实上", "反观",
]


def analyze(md: str, baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    body = re.sub(r"^---[\n\s\S]*?---\n", "", md)
    lines = body.split("\n")

    # 抽出正文行（去掉代码块 / 引用 / 表格 / 脚注定义），保留行号
    prose_lines: list[tuple[str, int]] = []
    in_code = False
    for i, raw in enumerate(lines):
        if re.match(r"^\s*```", raw):
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.match(r"^\s*>", raw):
            continue
        if re.match(r"^\s*\|?[\s:|-]*\|[\s:|-]*\|?\s*$", raw):
            continue
        if re.match(r"^\s*\|", raw):
            continue
        if re.match(r"^\[\^[^\]]+\]:", raw):
            continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", raw):
            continue
        is_heading = bool(re.match(r"^\s*#{1,6}\s+", raw))
        text = re.sub(r"^\s*#{1,6}\s+", "", raw)
        text = re.sub(r"^\s*[-*+]\s+", "", text)
        text = re.sub(r"^\s*\d+[.)]\s+", "", text)
        if is_heading and not re.search(r"[。！？…：:!?]$", text.strip()):
            text += "。"
        prose_lines.append((text, i + 1))
    prose = "\n".join(t for t, _ in prose_lines)

    chars = max(1, len(re.sub(r"\s", "", prose)))
    sentences = [s.strip() for s in re.split(r"[。！？…]+", prose) if s.strip()]
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", prose)
                  if p.strip() and not re.match(r"^#{1,6}\s", p)]

    def lens(items): return [len(x) for x in items]

    sent_lens = lens(sentences)
    para_lines = [max(1, round(len(p) / 38)) for p in paragraphs]

    def mean(a): return sum(a) / len(a) if a else 0.0

    def std(a):
        if not a:
            return 0.0
        m = mean(a)
        return math.sqrt(sum((x - m) ** 2 for x in a) / len(a))

    def per1k(pat):
        return round(len(re.findall(pat, prose)) / chars * 1000, 1)

    findings: list[dict[str, Any]] = []

    # ---- 句式/词汇/结构 ----
    for rule in PATTERNS:
        for m in rule.pattern.finditer(prose):
            start = m.start()
            ln = _line_at(prose, start, prose_lines)
            excerpt = _excerpt(prose, start, len(m.group(0)))
            ctx = prose[max(0, start - 30): start + len(m.group(0)) + 30]
            exempted = any(p.search(ctx) for p in EXEMPT_PATTERNS)
            findings.append({
                "id": rule.id, "dim": rule.dim,
                "level": "info" if exempted else rule.level,
                "pattern": rule.label, "line": ln, "excerpt": excerpt,
                "suggestion": rule.fix, "exempted": exempted,
            })

    # ---- 套话密度（引号内的不算） ----
    quoted = [(m.start(), m.end()) for m in re.finditer(r"「[^」]{0,80}」|\u201c[^\u201d]{0,80}\u201d|\"[^\"]{0,80}\"", prose)]

    def in_quote(i: int) -> bool:
        return any(a <= i < b for a, b in quoted)

    cliche_hits = 0
    detail: list[tuple[str, int]] = []
    for w in CLICHES:
        n = 0
        i = prose.find(w)
        while i != -1:
            if not in_quote(i):
                n += 1
            i = prose.find(w, i + len(w))
        if n:
            cliche_hits += n
            detail.append((w, n))
    if detail:
        per = round(cliche_hits / chars * 1000, 1)
        detail.sort(key=lambda x: -x[1])
        findings.append({
            "id": "cliche-bank", "dim": "lexicon",
            "level": "warn" if per > 6 else "info",
            "pattern": "套话词表", "line": 0,
            "excerpt": " ".join(f"{w}×{n}" for w, n in detail[:6]),
            "suggestion": f"套话密度 {per}/千字（阈值 6）",
            "exempted": False,
        })

    # ---- 段落开头雷同 ----
    strip_lead = lambda p: re.sub(r"^[\s>*_\-#]+|^\*\*|^\d+[.)]\s*", "", p)
    openers = ["".join(list(strip_lead(p))[:2]) for p in paragraphs]
    run = max_run = 1
    run_at = 0
    for i in range(1, len(openers)):
        if openers[i] and openers[i] == openers[i - 1]:
            run += 1
            if run > max_run:
                max_run, run_at = run, i
        else:
            run = 1
    if max_run >= 3:
        findings.append({
            "id": "same-opener", "dim": "structure", "level": "warn",
            "pattern": "段落开头雷同", "line": 0,
            "excerpt": f"连续 {max_run} 段以「{openers[run_at]}」开头",
            "suggestion": "换一种起手方式，或合并成一处列举", "exempted": False,
        })

    # ---- 三连排比 ----
    tri = re.compile(r"(?:[^。！？\n]{2,12}是[^。！？\n]{2,20})[，。][^。！？\n]{2,12}是[^。！？\n]{2,20}[，。][^。！？\n]{2,12}是[^。！？\n]{2,20}")
    for m in tri.finditer(prose):
        findings.append({
            "id": "triple-parallel", "dim": "parallelism", "level": "warn",
            "pattern": "三连排比", "line": _line_at(prose, m.start(), prose_lines),
            "excerpt": _excerpt(prose, m.start(), len(m.group(0))),
            "suggestion": "留一句最有力的，其余改成陈述或删掉", "exempted": False,
        })

    # ---- 句长过于均匀 ----
    sent_std = std(sent_lens)
    sent_mean = mean(sent_lens)
    base_std = max(8.0, (baseline or {}).get("avg_sentence_len", 0) * 0.45) if baseline else 8.0
    if len(sentences) >= 12 and sent_std < base_std * 0.6:
        findings.append({
            "id": "uniform-sentence", "dim": "sentence", "level": "warn",
            "pattern": "句长过于均匀", "line": 0,
            "excerpt": f"句长标准差 {sent_std:.1f}（参考下限 {base_std * 0.6:.1f}）",
            "suggestion": "插几句三五个字的短句，打破匀速", "exempted": False,
        })

    # ---- 段落长度过于均匀 ----
    para_std = std(para_lines)
    if len(paragraphs) >= 10 and para_std < 0.45:
        findings.append({
            "id": "uniform-paragraph", "dim": "structure", "level": "info",
            "pattern": "段落长度过于均匀", "line": 0,
            "excerpt": f"段落行数标准差 {para_std:.2f}",
            "suggestion": "偶尔让一段只有一句话", "exempted": False,
        })

    # ---- 标点 ----
    exclaim = per1k(r"！")
    dash = per1k(r"——")
    emoji = round(len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", prose)) / chars * 1000, 1)
    qmark = per1k(r"？")

    if baseline is not None and baseline.get("exclaim_per_1k", 0) < 0.5 and exclaim > 2:
        findings.append({
            "id": "exclaim-over", "dim": "punctuation", "level": "warn",
            "pattern": "感叹号超标", "line": 0,
            "excerpt": f"感叹号 {exclaim}/千字，你的习惯是 {baseline.get('exclaim_per_1k')}/千字",
            "suggestion": "你的风格里几乎不用感叹号", "exempted": False,
        })
    if dash > 3:
        findings.append({
            "id": "dash-abuse", "dim": "punctuation", "level": "info",
            "pattern": "破折号偏多", "line": 0, "excerpt": f"破折号 {dash}/千字",
            "suggestion": "破折号是插入解释，多了会打断节奏", "exempted": False,
        })
    if qmark > 4:
        findings.append({
            "id": "question-heavy", "dim": "punctuation", "level": "info",
            "pattern": "问号偏多", "line": 0, "excerpt": f"问号 {qmark}/千字",
            "suggestion": "自问自答用多了像讲课", "exempted": False,
        })
    if baseline is not None and baseline.get("emoji_per_1k", 0) < 1 and emoji > 3:
        findings.append({
            "id": "emoji-over", "dim": "punctuation", "level": "info",
            "pattern": "emoji 超标", "line": 0,
            "excerpt": f"emoji {emoji}/千字，你的习惯是 {baseline.get('emoji_per_1k')}/千字",
            "suggestion": "你的风格里几乎不用 emoji", "exempted": False,
        })

    # ---- 打分 ----
    penalty = {d: 0 for d in DIMS}
    weight = {"blocker": 18, "warn": 9, "info": 3}
    for f in findings:
        if not f["exempted"]:
            penalty[f["dim"]] += weight[f["level"]]
    cliche_per = round(cliche_hits / chars * 1000, 1)
    if cliche_per > 6:
        penalty["lexicon"] += min(20, (cliche_per - 6) * 2)
    scale = min(1.0, 600 / chars)
    scores = {d: max(0, min(100, round(100 - penalty[d] * (0.5 + 0.5 * scale)))) for d in DIMS}
    scores["overall"] = round(sum(scores[d] for d in DIMS) / len(DIMS))

    grade = ("干净" if scores["overall"] >= 88 else
             "轻微 AI 味" if scores["overall"] >= 72 else
             "明显 AI 味" if scores["overall"] >= 55 else "重灾区")

    worst = min(DIMS, key=lambda d: scores[d])
    active = [f for f in findings if not f["exempted"]]
    top = sorted(active, key=lambda f: -_rank(f["level"]))[:1]
    summary = [f"{scores['overall']} 分（{grade}）"]
    if scores[worst] < 85:
        summary.append(f"最弱项是{DIM_LABEL[worst]} {scores[worst]} 分")
    if top:
        t = top[0]
        summary.append(f"首要问题：{t.get('pattern') or t['id']}" + (f"（{t['excerpt'][:30]}）" if t.get("excerpt") else ""))

    return {
        "scores": scores, "grade": grade, "findings": findings,
        "stats": {
            "chars": chars, "sentences": len(sentences), "paragraphs": len(paragraphs),
            "avg_sentence_len": round(sent_mean, 1), "sentence_len_std": round(sent_std, 1),
            "paragraph_mean_lines": round(mean(para_lines), 1), "paragraph_len_std": round(para_std, 2),
            "cliche_per_1k": cliche_per, "exclaim_per_1k": exclaim,
            "dash_per_1k": dash, "emoji_per_1k": emoji,
        },
        "baseline_used": baseline is not None,
        "summary": "；".join(summary),
    }


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    delta = {d: after["scores"][d] - before["scores"][d] for d in DIMS}
    delta["overall"] = after["scores"]["overall"] - before["scores"]["overall"]
    improved = [d for d in DIMS if delta[d] > 0]
    worsened = [d for d in DIMS if delta[d] < 0]
    b_ids = {f["id"] for f in before["findings"] if not f["exempted"]}
    a_ids = {f["id"] for f in after["findings"] if not f["exempted"]}
    fixed = len(b_ids - a_ids)
    remaining = len(a_ids)
    if delta["overall"] > 0:
        verdict = f"总分 {before['scores']['overall']} → {after['scores']['overall']}（+{delta['overall']}）"
        if improved:
            verdict += "，" + "、".join(DIM_LABEL[d] for d in improved) + "改善"
        if worsened:
            verdict += "；" + "、".join(DIM_LABEL[d] for d in worsened) + "变差"
    elif delta["overall"] == 0:
        verdict = "分数未变"
    else:
        verdict = f"总分下降 {abs(delta['overall'])} 分，注意是否改坏了"
    return {"delta": delta, "improved": improved, "worsened": worsened,
            "fixed": fixed, "remaining": remaining, "verdict": verdict}


def _rank(level: str) -> int:
    return {"blocker": 3, "warn": 2, "info": 1}.get(level, 0)


def _line_at(prose: str, idx: int, mapping: list[tuple[str, int]]) -> int:
    nl = prose[:idx].count("\n")
    return mapping[min(nl, len(mapping) - 1)][1] if mapping else 0


def _excerpt(prose: str, idx: int, length: int) -> str:
    s = max(0, idx - 8)
    e = min(len(prose), idx + length + 8)
    return re.sub(r"\s+", " ", prose[s:e]).strip()