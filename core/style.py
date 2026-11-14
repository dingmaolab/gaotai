"""风格系统：DNA 六层蒸馏 + 持续学习 + 参考分流。

两条学习路径严格分离：
  learn_from_own   → 自己的文章 → 更新 L1-L6 → 重整 dna.md
  learn_from_reference → 别人的文章 → 只提取技法 → 存 references/ → 不动 DNA

置信度：exemplars <5 low / 5-10 medium / >10 high
低置信度时软建议只提示不拦截，硬规则必须用户确认。
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from core.vault import Account, Vault, write_atomic, serialize_doc, parse_doc, local_date

TZ = timezone(timedelta(hours=8))


# ── L1 语言统计（脚本可算） ──────────────────────────────────

def analyze_language(texts: list[str]) -> dict[str, Any]:
    """从多篇正文提取表层语言特征。"""
    all_text = "\n".join(texts)
    prose = re.sub(r"```[\s\S]*?```", "", all_text)
    prose = re.sub(r"^\s*>.*$", "", prose, flags=re.M)
    prose = re.sub(r"^\s*#{1,6}\s+", "", prose, flags=re.M)
    chars = max(1, len(re.sub(r"\s", "", prose)))

    sentences = [s.strip() for s in re.split(r"[。！？…]+", prose) if s.strip()]
    sent_lens = [len(s) for s in sentences]
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", prose) if p.strip()]
    para_lines = [max(1, round(len(p) / 38)) for p in paragraphs]

    me = len(re.findall(r"我", prose))
    you = len(re.findall(r"你|您", prose))
    total_pronouns = me + you + len(re.findall(r"他|她|它", prose))

    nums = len(re.findall(r"\d+(?:\.\d+)?%?", prose))
    exclaim = len(re.findall(r"！", prose))
    dash = len(re.findall(r"——", prose))
    question = len(re.findall(r"？", prose))

    # 高频词（简单分词：连续中文2-4字）
    words = re.findall(r"[\u4e00-\u9fff]{2,4}", prose)
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top_words = sorted(freq.items(), key=lambda x: -x[1])[:30]

    return {
        "chars": chars,
        "sentences": len(sentences),
        "avg_sentence_len": round(statistics.mean(sent_lens), 1) if sent_lens else 0,
        "sentence_len_p90": round(sorted(sent_lens)[int(len(sent_lens) * 0.9)] if sent_lens else 0, 1),
        "sentence_len_std": round(statistics.stdev(sent_lens), 1) if len(sent_lens) > 1 else 0,
        "short_sentence_ratio": round(sum(1 for l in sent_lens if l <= 15) / max(1, len(sent_lens)), 2),
        "paragraph_mean_lines": round(statistics.mean(para_lines), 1) if para_lines else 0,
        "pronoun_me_ratio": round(me / max(1, total_pronouns), 2),
        "pronoun_you_ratio": round(you / max(1, total_pronouns), 2),
        "numbers_per_1k": round(nums / chars * 1000, 1),
        "exclaim_per_1k": round(exclaim / chars * 1000, 1),
        "dash_per_1k": round(dash / chars * 1000, 1),
        "question_per_1k": round(question / chars * 1000, 1),
        "top_words": [{"word": w, "count": c} for w, c in top_words],
    }


# ── 自己的文章 → 更新 DNA ──────────────────────────────────

def learn_from_own(vault: Vault, account: Account, files: list[Path]) -> dict[str, Any]:
    """把自己的文章加入 exemplars，重算 L1，更新 profile。"""
    style_dir = vault.account_path(account, "style")
    exemplar_dir = style_dir / "exemplars"
    exemplar_dir.mkdir(parents=True, exist_ok=True)

    added = []
    texts = []
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        meta, body = parse_doc(text)
        # 复制到 exemplars
        dest = exemplar_dir / f.name
        if not dest.exists():
            write_atomic(dest, text)
            added.append(str(dest.relative_to(vault.root)))
        texts.append(body)

    # 收集所有 exemplars 的正文
    all_texts = []
    for ef in exemplar_dir.glob("*.md"):
        _, b = parse_doc(ef.read_text(encoding="utf-8"))
        all_texts.append(b)

    lang = analyze_language(all_texts)
    n = len(all_texts)
    confidence = "low" if n < 5 else ("medium" if n <= 10 else "high")

    profile = {
        "confidence": confidence,
        "sample_count": n,
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "language": lang,
    }
    write_atomic(style_dir / "profile.yaml", yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=1000))

    # 写 L1
    layers_dir = style_dir / "layers"
    layers_dir.mkdir(exist_ok=True)
    l1_md = f"# L1 语言特征\n\n样本 {n} 篇 · 置信度 {confidence}\n\n"
    l1_md += f"- 平均句长 {lang['avg_sentence_len']}，p90 {lang['sentence_len_p90']}\n"
    l1_md += f"- 短句占比 {lang['short_sentence_ratio']}\n"
    l1_md += f"- 段落均行 {lang['paragraph_mean_lines']}\n"
    l1_md += f"- 「我」占比 {lang['pronoun_me_ratio']}，「你」占比 {lang['pronoun_you_ratio']}\n"
    l1_md += f"- 数字密度 {lang['numbers_per_1k']}/千字\n"
    l1_md += f"- 感叹号 {lang['exclaim_per_1k']}/千字\n"
    l1_md += f"- 高频词：{'、'.join(w['word'] for w in lang['top_words'][:10])}\n"
    write_atomic(layers_dir / "language.md", l1_md)

    return {"ok": True, "added": added, "sample_count": n, "confidence": confidence, "language": lang}


# ── 别人的文章 → 只提取技法 ──────────────────────────────────

def learn_from_reference(
    vault: Vault, account: Account,
    text: str, author: str = "", title: str = "", url: str = "",
) -> dict[str, Any]:
    """别人的文章只存 references，提取结构/数据手法，不动 DNA。

    注意：具体的"他们怎么做/你可以借鉴什么/你不要做什么"三栏分析
    由 skill 里的模型完成，这里只负责存储和标记 allowed_uses。
    """
    ref_dir = vault.account_path(account, "style", "references")
    ref_dir.mkdir(parents=True, exist_ok=True)

    date = local_date()
    stem = re.sub(r'[<>:"/\\|?*]', "", title or author or "reference")[:40].strip(".-") or "ref"
    path = ref_dir / f"{date}-{stem}.md"
    i = 2
    while path.exists():
        path = ref_dir / f"{date}-{stem}-{i}.md"
        i += 1

    meta = {
        "type": "reference",
        "ownership": "third_party",
        "allowed_uses": ["structure", "data_discipline"],
        "content_reusable": False,
        "author": author,
        "title": title,
        "url": url,
        "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    body = f"## 原文\n\n{text.strip()}\n\n## 技法提取（由模型填写）\n\n### 他们怎么做\n\n（待分析）\n\n### 你可以借鉴什么\n\n（待分析）\n\n### 你不要做什么\n\n（待分析）\n"
    write_atomic(path, serialize_doc(meta, body))

    return {"ok": True, "path": str(path.relative_to(vault.root)), "allowed_uses": meta["allowed_uses"]}


# ── 改稿对比 → 抽 lesson ──────────────────────────────────

def learn_from_diff(vault: Vault, account: Account, draft: str, final: str) -> dict[str, Any]:
    """对比初稿和终稿，记录差异，供模型抽取 lesson。

    脚本只做机械 diff 和存储；"这条改动意味着什么规则"由 skill 里的模型判断。
    """
    diff_dir = vault.account_path(account, "style", "diffs")
    diff_dir.mkdir(parents=True, exist_ok=True)

    date = local_date()
    path = diff_dir / f"{date}-diff.md"
    i = 2
    while path.exists():
        path = diff_dir / f"{date}-diff-{i}.md"
        i += 1

    # 简单行级 diff
    d_lines = draft.split("\n")
    f_lines = final.split("\n")
    removed = [l for l in d_lines if l.strip() and l not in f_lines]
    added = [l for l in f_lines if l.strip() and l not in d_lines]

    body = f"## 删除的内容（{len(removed)} 行）\n\n"
    body += "\n".join(f"- {l.strip()}" for l in removed[:30]) or "（无）"
    body += f"\n\n## 新增的内容（{len(added)} 行）\n\n"
    body += "\n".join(f"+ {l.strip()}" for l in added[:30]) or "（无）"
    body += "\n\n## 待抽取的规则\n\n（由模型分析上述差异后写入 lessons/）\n"

    write_atomic(path, f"---\ndate: {date}\ntype: diff\n---\n\n{body}")
    return {"ok": True, "path": str(path.relative_to(vault.root)), "removed": len(removed), "added": len(added)}


def save_lesson(vault: Vault, account: Account, key: str, rule_type: str,
                description: str, scope: str = "global", confirmed: bool = False) -> Path:
    """保存一条学到的规则。"""
    lessons_dir = vault.account_path(account, "style", "lessons")
    lessons_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r'[<>:"/\\|?*]', "", key)[:40].strip(".-") or "lesson"
    path = lessons_dir / f"{local_date()}-{stem}.md"
    meta = {
        "key": key, "type": rule_type, "scope": scope,
        "description": description, "confirmed": confirmed,
        "created_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "hits": 1,
    }
    write_atomic(path, serialize_doc(meta, description))
    return path


# ── 画像查看 ──────────────────────────────────────────────

def get_profile(vault: Vault, account: Account) -> dict[str, Any]:
    path = vault.account_path(account, "style", "profile.yaml")
    if path.is_file():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {"confidence": "none", "sample_count": 0, "message": "还没有画像，先喂几篇你自己的文章"}


# ── 风格卡拼装 ──────────────────────────────────────────────

def build_card(vault: Vault, account: Account, max_chars: int = 2400) -> dict[str, Any]:
    """从 layers + lessons 拼装 dna.md（写稿时注入的风格卡）。

    优先级：confirmed lessons > layers 摘要 > 默认建议
    超长时截断低优先级内容。
    """
    style_dir = vault.account_path(account, "style")
    layers_dir = style_dir / "layers"
    lessons_dir = style_dir / "lessons"

    parts: list[str] = []
    budget = max_chars

    # 1. confirmed lessons（最高优先级）
    if lessons_dir.is_dir():
        for lf in sorted(lessons_dir.glob("*.md")):
            meta, body = parse_doc(lf.read_text(encoding="utf-8"))
            if meta.get("confirmed"):
                entry = f"- 【{meta.get('type', 'rule')}】{meta.get('key', '')}：{body.strip()[:100]}\n"
                if len(entry) < budget:
                    parts.append(entry)
                    budget -= len(entry)

    # 2. layers 摘要
    layer_order = ["language.md", "structures.md", "topics.md", "sources.md", "cognition.md", "visual.md"]
    for name in layer_order:
        lp = layers_dir / name
        if lp.is_file() and budget > 100:
            text = lp.read_text(encoding="utf-8")
            # 取前几行作为摘要
            summary = "\n".join(text.split("\n")[:8])
            if len(summary) > budget:
                summary = summary[:budget - 20] + "\n…（截断）"
            parts.append(f"\n## {name.replace('.md', '')}\n\n{summary}\n")
            budget -= len(summary) + 30

    # 3. 未确认 lessons（低优先级，标注仅供参考）
    if lessons_dir.is_dir() and budget > 50:
        unconfirmed = []
        for lf in sorted(lessons_dir.glob("*.md")):
            meta, body = parse_doc(lf.read_text(encoding="utf-8"))
            if not meta.get("confirmed"):
                unconfirmed.append(f"- （待确认）{meta.get('key', '')}")
        if unconfirmed:
            section = "\n## 待确认偏好（仅供参考）\n\n" + "\n".join(unconfirmed[:5])
            if len(section) < budget:
                parts.append(section)

    card = "# 风格卡\n\n" + "".join(parts)
    if len(card) > max_chars:
        card = card[:max_chars - 20] + "\n\n…（超长截断）"

    card_path = style_dir / "dna.md"
    write_atomic(card_path, card)

    profile = get_profile(vault, account)
    return {
        "ok": True,
        "path": str(card_path.relative_to(vault.root)),
        "chars": len(card),
        "confidence": profile.get("confidence", "none"),
        "warning": "样本不足，风格卡仅供参考" if profile.get("confidence") == "low" else None,
    }