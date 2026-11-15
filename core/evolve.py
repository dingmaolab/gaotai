"""持续迭代：recent_articles 追踪 + story-bank + DNA 防漂移。

业界实证（mayday/gracker/writing-dna）：
- 每次创作后自动记录结构/开头/结尾/金句 → 反重复的基础
- 个人素材库跨项目持久化 → 真实人味的来源
- DNA 更新必须用户确认 → 防止偶然偏好变成固定风格
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from core.vault import Account, Vault, write_atomic, parse_doc, local_date

TZ = timezone(timedelta(hours=8))


# ── recent_articles 追踪 ──────────────────────────────────

def record_article(
    vault: Vault, account: Account,
    title: str, structure: str = "", opening_type: str = "",
    ending_type: str = "", golden_phrases: list[str] | None = None,
    platform: str = "", dimensions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """每次 send 时调用，记录本篇的结构特征供反重复检查。

    幂等：同日同标题已存在则更新该条，不重复插入。
    """
    path = vault.account_path(account, "style", "recent.yaml")
    data: dict[str, Any] = {"articles": []}
    if path.is_file():
        data = yaml.safe_load(path.read_text("utf-8")) or {"articles": []}

    entry = {
        "date": local_date(),
        "title": title,
        "structure": structure,
        "opening_type": opening_type,
        "ending_type": ending_type,
        "golden_phrases": golden_phrases or [],
        "platform": platform,
        "dimensions": dimensions or {},
    }
    # 同日同标题 → 原地更新（保留已有非空字段）
    for i, a in enumerate(data["articles"]):
        if a.get("date") == entry["date"] and a.get("title") == title:
            merged = {**a, **{k: v for k, v in entry.items() if v}}
            data["articles"][i] = merged
            write_atomic(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000))
            return {"ok": True, "recorded": title, "updated": True, "total_tracked": len(data["articles"])}
    data["articles"].insert(0, entry)
    # 只保留最近 20 篇
    data["articles"] = data["articles"][:20]
    write_atomic(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000))
    return {"ok": True, "recorded": title, "total_tracked": len(data["articles"])}


def check_repetition(vault: Vault, account: Account, structure: str,
                     opening_type: str = "", ending_type: str = "",
                     golden_phrases: list[str] | None = None) -> dict[str, Any]:
    """写稿前调用，检查是否与最近文章重复。返回 warnings 列表。"""
    path = vault.account_path(account, "style", "recent.yaml")
    if not path.is_file():
        return {"warnings": [], "recent_count": 0}

    data = yaml.safe_load(path.read_text("utf-8")) or {}
    articles = data.get("articles", [])
    warnings = []

    # 最近 2 篇同结构 → 强制换
    recent_structures = [a.get("structure", "") for a in articles[:2]]
    if structure and all(s == structure for s in recent_structures if s):
        warnings.append({
            "id": "structure-repeat",
            "msg": f"最近 2 篇都用了「{structure}」，建议换一个结构原型",
            "severity": "warn",
        })

    # 最近 3 篇同开头类型
    recent_openings = [a.get("opening_type", "") for a in articles[:3]]
    if opening_type and sum(1 for o in recent_openings if o == opening_type) >= 2:
        warnings.append({
            "id": "opening-repeat",
            "msg": f"最近 3 篇中有 2 篇用了「{opening_type}」开头，建议换",
            "severity": "info",
        })

    # 金句重复率 > 30%
    if golden_phrases:
        recent_golden = set()
        for a in articles[:5]:
            recent_golden.update(a.get("golden_phrases", []))
        if recent_golden:
            overlap = sum(1 for p in golden_phrases if p in recent_golden)
            rate = overlap / len(golden_phrases)
            if rate > 0.3:
                warnings.append({
                    "id": "golden-repeat",
                    "msg": f"金句与最近 5 篇重复率 {rate:.0%}（>30%），建议换新表达",
                    "severity": "warn",
                })

    return {"warnings": warnings, "recent_count": len(articles)}


# ── story-bank 个人素材库 ──────────────────────────────────

def get_story_bank(vault: Vault, account: Account) -> dict[str, Any]:
    """读取个人素材库。不存在则返回空模板。"""
    path = vault.account_path(account, "style", "story-bank.yaml")
    if path.is_file():
        return yaml.safe_load(path.read_text("utf-8")) or _empty_bank()
    return _empty_bank()


def add_story(vault: Vault, account: Account, category: str, entry: dict[str, Any]) -> dict[str, Any]:
    """往素材库加一条。category: stories/viewpoints/phrases/emotions"""
    bank = get_story_bank(vault, account)
    if category not in bank:
        bank[category] = []
    bank[category].append({**entry, "added_at": local_date()})
    path = vault.account_path(account, "style", "story-bank.yaml")
    write_atomic(path, yaml.safe_dump(bank, allow_unicode=True, sort_keys=False, width=1000))
    return {"ok": True, "category": category, "count": len(bank[category])}


def _empty_bank() -> dict[str, Any]:
    return {
        "stories": [],      # {scene, detail, feeling, tags}
        "viewpoints": [],   # {topic, view, one_liner}
        "phrases": {        # {favorites: [], avoid: [], tone_notes: []}
            "favorites": [],
            "avoid": [],
            "tone_notes": [],
        },
        "emotions": [],     # {topic, tone, note}
    }


# ── DNA 防漂移 + 自动提议 ──────────────────────────────────

def propose_dna_update(
    vault: Vault, account: Account,
    signals: list[dict[str, str]],
) -> dict[str, Any]:
    """从创作反馈中提取偏好信号，生成待确认的 DNA 更新建议。

    signals: [{type: "avoid"/"prefer"/"structure", content: "...", source: "user_feedback"/"diff"}]

    关键纪律（mayday 实证）：
    - 不自动写入，先展示建议让用户确认
    - 手动调整过的字段优先级最高
    - 区分临时要求和持久偏好
    - 单次出现的偏好标为 tentative，多次出现才升为 confirmed
    """
    lessons_dir = vault.account_path(account, "style", "lessons")
    lessons_dir.mkdir(parents=True, exist_ok=True)

    proposals = []
    for sig in signals:
        key = sig.get("content", "")[:40]
        sig_type = sig.get("type", "prefer")
        source = sig.get("source", "user_feedback")

        # 检查是否已有同类 lesson
        existing_hits = 0
        for lf in lessons_dir.glob("*.md"):
            meta, _ = parse_doc(lf.read_text("utf-8"))
            if meta.get("key") == key:
                existing_hits = meta.get("hits", 1)
                break

        new_hits = existing_hits + 1
        # 单次 = tentative，≥3次 = 建议 confirm
        status = "tentative" if new_hits < 3 else "suggest_confirm"
        # 用户直接说的 = 立即 confirmed
        if source == "user_explicit":
            status = "confirmed"

        proposals.append({
            "key": key,
            "type": sig_type,
            "status": status,
            "hits": new_hits,
            "source": source,
            "message": f"{'建议确认' if status == 'suggest_confirm' else '暂记'}：{sig_type} 「{key}」（第{new_hits}次出现）",
        })

    return {"ok": True, "proposals": proposals, "needs_confirmation": any(p["status"] != "confirmed" for p in proposals)}


def apply_confirmed_updates(vault: Vault, account: Account, confirmed_keys: list[str]) -> dict[str, Any]:
    """用户确认后，把 tentative/suggest_confirm 的 lesson 标为 confirmed。"""
    lessons_dir = vault.account_path(account, "style", "lessons")
    updated = []
    for lf in lessons_dir.glob("*.md"):
        meta, body = parse_doc(lf.read_text("utf-8"))
        if meta.get("key") in confirmed_keys and not meta.get("confirmed"):
            meta["confirmed"] = True
            meta["confirmed_at"] = datetime.now(TZ).isoformat(timespec="seconds")
            write_atomic(lf, yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "\n---\n\n" + body)
            updated.append(meta["key"])
    return {"ok": True, "confirmed": updated}