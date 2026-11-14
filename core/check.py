"""分级审稿：硬底线 / 软建议 / 个人偏好。

硬底线 → blocker，不可覆盖，所有文体生效
软建议 → warn/info，按维度组合查表，可被账号 overrides 覆盖
个人偏好 → info，从 DNA 来，低置信度标注"仅供参考"

绝不把排查词表变成自动禁词表（gracker 原则）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ── 硬底线词表 ──────────────────────────────────────────────

AD_LAW = [
    "最好", "最强", "最优", "最佳", "第一", "唯一", "顶级", "极致",
    "全网最", "史上最", "国家级", "世界级", "绝无仅有", "万能",
    "100%", "零风险", " guaranteed", "永久", "彻底根治",
]
AD_EXEMPT = re.compile(
    r"之一|我用过的|我见过的|目前为止我|个人认为|在我看来|"
    r"最佳做法|最佳实践|最佳时机|最佳方案|最佳路径|最佳答案|最有效的办法"
)

FABRICATION_PATTERNS = [
    re.compile(r"我(亲眼|亲身|亲自)(看到|经历|体验|见证)了.{0,20}(奇迹|震撼|颠覆)"),
    re.compile(r"(那一刻|瞬间|刹那间)我(明白|顿悟|领悟|意识到)了"),
    re.compile(r"我的(朋友|同事|同学)(小王|小李|小张|老[王李张])"),
]

CONFUSIONS = [
    (re.compile(r"帐号"), "账号"), (re.compile(r"登陆"), "登录"),
    (re.compile(r"另令"), "另外"), (re.compile(r"既使"), "即使"),
    (re.compile(r"做为"), "作为"), (re.compile(r"必竟"), "毕竟"),
    (re.compile(r"按装"), "安装"), (re.compile(r"布署"), "部署"),
    (re.compile(r"测式"), "测试"), (re.compile(r"配值"), "配置"),
    (re.compile(r"权现"), "权限"),
]


def _strip_prose(md: str) -> str:
    """去掉代码块/引用/表格分隔/脚注定义/标题标记，保留正文。"""
    s = re.sub(r"```[\s\S]*?```", "", md)
    s = re.sub(r"^\s*>.*$", "", s, flags=re.M)
    s = re.sub(r"\[\^[^\]]+\]:?.*$", "", s, flags=re.M)
    s = re.sub(r"^\s*\|?[\s:|-]*\|[\s:|-]*\|?\s*$", "", s, flags=re.M)
    s = re.sub(r"^\s*#{1,6}\s+", "", s, flags=re.M)
    return s


def check(
    md: str,
    dimensions: dict[str, str] | None = None,
    account_overrides: dict[str, Any] | None = None,
    dna_prefs: list[dict[str, Any]] | None = None,
    rules_path: str | Path | None = None,
) -> dict[str, Any]:
    """返回 {blockers, warnings, infos, counts}。"""
    dims = dimensions or {}
    overrides = account_overrides or {}
    prefs = dna_prefs or []

    # 加载维度规则
    rules_file = Path(rules_path) if rules_path else Path(__file__).parent / "dimensions.yaml"
    try:
        rules = yaml.safe_load(rules_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        rules = {}

    prose = _strip_prose(md)
    chars = max(1, len(re.sub(r"\s", "", prose)))
    lines = md.split("\n")

    blockers: list[dict] = []
    warnings: list[dict] = []
    infos: list[dict] = []

    # ═══ 硬底线 ═══

    # 广告法
    for w in AD_LAW:
        for m in re.finditer(re.escape(w), prose):
            ctx = prose[max(0, m.start() - 20):m.end() + 20]
            if not AD_EXEMPT.search(ctx):
                blockers.append({
                    "id": "ad-law", "level": "blocker",
                    "msg": f"广告法绝对化用语「{w}」",
                    "context": ctx.strip(),
                    "fix": "换成具体描述或删除",
                })

    # 编造经历
    for pat in FABRICATION_PATTERNS:
        for m in pat.finditer(prose):
            blockers.append({
                "id": "fabricated-experience", "level": "blocker",
                "msg": f"疑似编造经历：{m.group(0)[:40]}",
                "fix": "只写真实发生的事；没有就删掉",
            })

    # 无来源硬事实（source=event/material/mixed 时）
    source = dims.get("source", "")
    if source in ("event", "material", "mixed"):
        # 找含具体数字但无 URL/出处的句子
        sentences = re.split(r"[。！？\n]", prose)
        for sent in sentences:
            if re.search(r"\d{2,}", sent) and not re.search(r"https?://|来源|出处|据.*报道|财报|官方", sent):
                if len(sent.strip()) > 10:
                    blockers.append({
                        "id": "unverified-hard-fact", "level": "blocker",
                        "msg": f"硬事实无来源：{sent.strip()[:50]}",
                        "fix": "补出处，或改为模糊表述，或删掉",
                    })

    # 错别字（硬底线级别，因为影响可信度）
    for pat, correct in CONFUSIONS:
        for m in pat.finditer(prose):
            blockers.append({
                "id": "typo", "level": "blocker",
                "msg": f"错别字「{m.group(0)}」→「{correct}」",
                "fix": f"改为「{correct}」",
            })

    # ═══ 软建议（按维度组合） ═══

    fmt = dims.get("format", "longform")
    fmt_rules = rules.get("format", {}).get(fmt, {})
    soft_defaults = rules.get("soft_defaults", {})

    def get(key: str, default=None):
        """优先级：账号 override > 维度规则 > 默认值"""
        if key in overrides:
            return overrides[key]
        if key in fmt_rules:
            return fmt_rules[key]
        return soft_defaults.get(key, default)

    # 字数
    char_range = get("chars")
    if char_range and isinstance(char_range, list) and len(char_range) == 2:
        lo, hi = char_range
        if chars < lo:
            warnings.append({"id": "too-short", "level": "warn",
                             "msg": f"字数 {chars}，低于建议下限 {lo}", "fix": "补充内容或确认是否短文"})
        elif chars > hi:
            warnings.append({"id": "too-long", "level": "warn",
                             "msg": f"字数 {chars}，超过建议上限 {hi}", "fix": "精简或拆分"})

    # 感叹号
    exclaim_max = get("exclaim_max", 0)
    exclaim_count = len(re.findall(r"！", prose))
    exclaim_per = round(exclaim_count / chars * 1000, 1)
    if exclaim_count > exclaim_max:
        warnings.append({"id": "exclaim-over", "level": "warn",
                         "msg": f"感叹号 {exclaim_count} 个（{exclaim_per}/千字），建议上限 {exclaim_max}",
                         "fix": "你的风格里几乎不用感叹号"})

    # 数字密度
    num_min = get("numbers_per_1k_min", 6)
    nums = len(re.findall(r"\d+(?:\.\d+)?%?", prose))
    num_per = round(nums / chars * 1000, 1)
    if num_per < num_min and num_min > 0:
        infos.append({"id": "low-numbers", "level": "info",
                      "msg": f"数字密度 {num_per}/千字，建议 ≥{num_min}",
                      "fix": "补充可核实的数字；感悟类可忽略"})

    # 段落长度
    para_max = get("paragraph_max_lines", 4)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", prose) if p.strip()]
    long_paras = [i + 1 for i, p in enumerate(paragraphs)
                  if len(p) / 38 > para_max and not p.startswith("#")]
    if long_paras:
        infos.append({"id": "long-paragraph", "level": "info",
                      "msg": f"{len(long_paras)} 段超过 {para_max} 行（第 {', '.join(map(str, long_paras[:5]))} 段）",
                      "fix": "拆成短段，或确认是否需要长段"})

    # 套话密度
    cliche_max = get("cliche_per_1k_max", 6)
    from core.tone import CLICHES
    cliche_hits = sum(prose.count(w) for w in CLICHES)
    cliche_per = round(cliche_hits / chars * 1000, 1)
    if cliche_per > cliche_max:
        warnings.append({"id": "cliche-density", "level": "warn",
                         "msg": f"套话密度 {cliche_per}/千字，超过 {cliche_max}",
                         "fix": "替换为具体表达"})

    # 人称占比（按 audience）
    audience = dims.get("audience", "peer")
    aud_rules = rules.get("audience", {}).get(audience, {})
    me_range = overrides.get("pronoun_me_range") or aud_rules.get("pronoun_me_range")
    if me_range:
        me_count = len(re.findall(r"我", prose))
        total_pronouns = me_count + len(re.findall(r"你|您|他|她|它", prose))
        me_ratio = round(me_count / max(1, total_pronouns), 2)
        lo, hi = me_range
        if not (lo <= me_ratio <= hi):
            infos.append({"id": "pronoun-ratio", "level": "info",
                          "msg": f"「我」占比 {me_ratio}，当前读者类型建议 [{lo}, {hi}]",
                          "fix": "调整人称；这只是建议，不是错误"})

    # ═══ 个人偏好（DNA） ═══
    for pref in prefs:
        if pref.get("type") == "forbid":
            word = pref.get("key", "")
            if word and word in prose:
                confidence = pref.get("confidence", "high")
                level = "warn" if confidence == "high" else "info"
                msg = f"你的风格规则：不用「{word}」"
                if confidence != "high":
                    msg += "（样本不足，仅供参考）"
                (warnings if level == "warn" else infos).append({
                    "id": f"dna-{pref.get('key', 'unknown')}", "level": level,
                    "msg": msg, "fix": pref.get("description", "按你的习惯修改"),
                })

    return {
        "blockers": blockers,
        "warnings": warnings,
        "infos": infos,
        "counts": {"blocker": len(blockers), "warn": len(warnings), "info": len(infos)},
        "stats": {"chars": chars, "exclaim_per_1k": exclaim_per, "numbers_per_1k": num_per,
                  "cliche_per_1k": cliche_per},
    }