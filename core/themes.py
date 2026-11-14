"""主题：从 themes/*.yaml 读取，角色制 + 版式变体。

角色（roles）：primary / text / muted / bgCard / mark / border，每个都有 light 和 dark。
版式变体：h2.decor（left-bar|numbered|underline|pill）、quote.variant（card|line|plain|bigquote）、code.variant（light|dark）。
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_FONT = (
    "-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC',"
    "'Hiragino Sans GB','Microsoft YaHei',sans-serif"
)

BUILTIN: list[dict[str, Any]] = [
    {
        "id": "ink-green", "name": "墨绿",
        "roles": {
            "primary": {"light": "#0B6E4F", "dark": "#4ADE80"},
            "text": {"light": "#1F2937", "dark": "#E5E7EB"},
            "muted": {"light": "#6B7280", "dark": "#9CA3AF"},
            "bgCard": {"light": "#F0F7F4", "dark": "#0B2E23"},
            "mark": {"light": "#CDE8DC", "dark": "#14532D"},
            "border": {"light": "#D8E5DF", "dark": "#1F4A3A"},
        },
        "body": {"size": 16, "line": 1.8},
        "h2": {"decor": "left-bar", "size": 19, "weight": 700},
        "sectionNumbering": True,
        "quote": {"variant": "card", "size": 15},
        "code": {"variant": "light"},
    },
    {
        "id": "minimal", "name": "极简黑白",
        "roles": {
            "primary": {"light": "#111111", "dark": "#FFFFFF"},
            "text": {"light": "#111111", "dark": "#EEEEEE"},
            "muted": {"light": "#8A8A8A", "dark": "#9A9A9A"},
            "bgCard": {"light": "#F6F6F6", "dark": "#1A1A1A"},
            "mark": {"light": "#EAEAEA", "dark": "#333333"},
            "border": {"light": "#E0E0E0", "dark": "#333333"},
        },
        "body": {"size": 16, "line": 1.95},
        "h2": {"decor": "pill", "size": 18, "weight": 700},
        "sectionNumbering": False,
        "quote": {"variant": "bigquote", "size": 16},
        "code": {"variant": "light"},
    },
    {
        "id": "red-white", "name": "红白",
        "roles": {
            "primary": {"light": "#C0392B", "dark": "#F87171"},
            "text": {"light": "#222222", "dark": "#EAEAEA"},
            "muted": {"light": "#777777", "dark": "#A3A3A3"},
            "bgCard": {"light": "#FBF3F2", "dark": "#3A1512"},
            "mark": {"light": "#F5D9D5", "dark": "#5B1F1A"},
            "border": {"light": "#EBD8D5", "dark": "#4A221E"},
        },
        "body": {"size": 16, "line": 1.8},
        "h2": {"decor": "numbered", "size": 19, "weight": 800},
        "sectionNumbering": True,
        "quote": {"variant": "line", "size": 15},
        "code": {"variant": "light"},
    },
    {
        "id": "graphite", "name": "石墨",
        "roles": {
            "primary": {"light": "#374151", "dark": "#D1D5DB"},
            "text": {"light": "#111827", "dark": "#F3F4F6"},
            "muted": {"light": "#9CA3AF", "dark": "#6B7280"},
            "bgCard": {"light": "#F5F5F4", "dark": "#1C1917"},
            "mark": {"light": "#E7E5E4", "dark": "#292524"},
            "border": {"light": "#E5E7EB", "dark": "#374151"},
        },
        "body": {"size": 16, "line": 1.85},
        "h2": {"decor": "underline", "size": 19, "weight": 700},
        "sectionNumbering": False,
        "quote": {"variant": "plain", "size": 15},
        "code": {"variant": "light"},
    },
    {
        "id": "newspaper", "name": "报纸",
        "roles": {
            "primary": {"light": "#7B3F00", "dark": "#D2A679"},
            "text": {"light": "#2B2118", "dark": "#E8DDD0"},
            "muted": {"light": "#7A6A5A", "dark": "#A89880"},
            "bgCard": {"light": "#FAF5EC", "dark": "#2A2119"},
            "mark": {"light": "#F0E5D2", "dark": "#3D2F22"},
            "border": {"light": "#DCCDB6", "dark": "#4A3A28"},
        },
        "body": {"size": 16, "line": 1.9, "family": "Georgia,'Songti SC','SimSun',serif"},
        "h2": {"decor": "underline", "size": 20, "weight": 700},
        "sectionNumbering": True,
        "quote": {"variant": "bigquote", "size": 16},
        "code": {"variant": "light"},
    },
    {
        "id": "midnight", "name": "午夜",
        "roles": {
            "primary": {"light": "#1E3A8A", "dark": "#60A5FA"},
            "text": {"light": "#1A2333", "dark": "#DCE3EE"},
            "muted": {"light": "#64748B", "dark": "#94A3B8"},
            "bgCard": {"light": "#EEF2FA", "dark": "#0F172A"},
            "mark": {"light": "#DCE6FA", "dark": "#1E293B"},
            "border": {"light": "#D5DEEC", "dark": "#243044"},
        },
        "body": {"size": 16, "line": 1.85},
        "h2": {"decor": "left-bar", "size": 19, "weight": 700},
        "sectionNumbering": True,
        "quote": {"variant": "card", "size": 15},
        "code": {"variant": "dark"},
    },
]

_DECORS = {"left-bar", "numbered", "underline", "pill"}
_QUOTES = {"card", "line", "plain", "bigquote"}


def _norm(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """用 fallback 补齐缺的字段，坏值回落到 fallback。"""
    if not isinstance(raw, dict):
        return copy.deepcopy(fallback)
    t = copy.deepcopy(fallback)
    t["id"] = str(raw.get("id") or fallback["id"])
    t["name"] = str(raw.get("name") or fallback["name"])
    roles = raw.get("roles") or {}
    for k in ("primary", "text", "muted", "bgCard", "mark", "border"):
        v = roles.get(k)
        if isinstance(v, dict) and isinstance(v.get("light"), str) and isinstance(v.get("dark"), str):
            t["roles"][k] = {"light": v["light"], "dark": v["dark"]}
    body = raw.get("body") or {}
    t["body"]["size"] = int(body.get("size") or t["body"]["size"])
    t["body"]["line"] = float(body.get("line") or t["body"]["line"])
    if body.get("family"):
        t["body"]["family"] = str(body["family"])
    h2 = raw.get("h2") or {}
    if h2.get("decor") in _DECORS:
        t["h2"]["decor"] = h2["decor"]
    t["h2"]["size"] = int(h2.get("size") or t["h2"]["size"])
    t["h2"]["weight"] = int(h2.get("weight") or t["h2"]["weight"])
    if "sectionNumbering" in raw:
        t["sectionNumbering"] = bool(raw["sectionNumbering"])
    q = raw.get("quote") or {}
    if q.get("variant") in _QUOTES:
        t["quote"]["variant"] = q["variant"]
    t["quote"]["size"] = int(q.get("size") or t["quote"]["size"])
    c = raw.get("code") or {}
    if c.get("variant") == "dark":
        t["code"]["variant"] = "dark"
    return t


def load_themes(theme_dir: str | Path | None = None) -> list[dict[str, Any]]:
    by_id = {t["id"]: copy.deepcopy(t) for t in BUILTIN}
    if theme_dir:
        d = Path(theme_dir)
        if d.is_dir():
            for f in sorted(list(d.glob("*.yaml")) + list(d.glob("*.yml"))):
                try:
                    raw = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                except (yaml.YAMLError, OSError):
                    continue
                tid = str(raw.get("id") or f.stem)
                base = by_id.get(tid) or BUILTIN[0]
                by_id[tid] = _norm({**raw, "id": tid}, base)
    ordered: list[dict[str, Any]] = []
    for t in BUILTIN:
        if t["id"] in by_id:
            ordered.append(by_id.pop(t["id"]))
    ordered.extend(by_id.values())
    return ordered


def get_theme(theme_id: str | None, theme_dir: str | Path | None = None) -> dict[str, Any]:
    themes = load_themes(theme_dir)
    for t in themes:
        if t["id"] == theme_id:
            return t
    return themes[0]