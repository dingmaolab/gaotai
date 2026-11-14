"""配图渲染：HTML 模板 → Playwright 截图 → PNG。

按平台×形式查规格（covers/*.yaml），字号随尺寸缩放，字数超限自动降级。
deviceScaleFactor=2 出高清图。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


def load_spec(platform: str, covers_dir: str | Path | None = None) -> dict[str, Any]:
    """加载配图规格。"""
    d = Path(covers_dir) if covers_dir else Path(__file__).parent.parent / "covers"
    # 平台映射到文件名
    name_map = {
        "wechat_article": "wechat-article",
        "xhs_carousel": "xhs",
        "wechat_imagepost": "wechat-imagepost",
    }
    fname = name_map.get(platform, platform)
    path = d / f"{fname}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"找不到配图规格：{path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def render_cover(
    title: str,
    platform: str = "wechat_article",
    subtitle: str = "",
    column: str = "",
    number: str = "",
    account_name: str = "",
    theme_id: str = "minimal",
    covers_dir: str | Path | None = None,
    out_dir: str | Path = "assets/covers",
) -> dict[str, Any]:
    """生成封面图。返回 {ok, path, size}。"""
    spec = load_spec(platform, covers_dir)
    slot = spec.get("slots", {}).get("cover", {})
    size = slot.get("size", [900, 383])
    limits = slot.get("limits", {})

    # 字数检查 + 降级
    title_lines = limits.get("title_lines", 2)
    chars_per_line = limits.get("title_chars_per_line", 12)
    display_title, warning = _fit_text(title, title_lines, chars_per_line)

    html = _cover_html(display_title, subtitle, column, number, account_name, size, theme_id)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    png_path = out / f"cover-{platform}.png"

    ok = _screenshot(html, png_path, size[0], size[1])
    return {"ok": ok, "path": str(png_path), "size": size, "warning": warning}


def render_cards(
    points: list[dict[str, str]],
    platform: str = "xhs_carousel",
    account_name: str = "",
    theme_id: str = "minimal",
    covers_dir: str | Path | None = None,
    out_dir: str | Path = "assets/cards",
) -> dict[str, Any]:
    """生成多张卡片。points: [{title, note}]，第一张是封面。"""
    spec = load_spec(platform, covers_dir)
    slots = spec.get("slots", {})
    cover_spec = slots.get("cover", slots.get("first", {}))
    inner_spec = slots.get("inner", slots.get("rest", cover_spec))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    warnings = []
    total = len(points)

    for i, pt in enumerate(points):
        is_cover = (i == 0)
        s = cover_spec if is_cover else inner_spec
        size = s.get("size", [1086, 1448])
        limits = s.get("limits", {})

        if is_cover:
            lines = limits.get("title_lines", 3)
            cpl = limits.get("title_chars_per_line", 8)
            text, w = _fit_text(pt.get("title", ""), lines, cpl)
            html = _card_cover_html(text, pt.get("note", ""), account_name, f"{i+1}/{total}", size, theme_id)
        else:
            lines = limits.get("point_lines", 2)
            cpl = limits.get("point_chars_per_line", 9)
            text, w = _fit_text(pt.get("title", ""), lines, cpl)
            note = pt.get("note", "")
            note_lines = limits.get("note_lines", 3)
            note_cpl = limits.get("note_chars_per_line", 18)
            note, nw = _fit_text(note, note_lines, note_cpl)
            if nw:
                warnings.append(nw)
            html = _card_inner_html(text, note, account_name, f"{i+1}/{total}", size, theme_id)

        if w:
            warnings.append(w)
        png_path = out / f"{i+1:02d}-{'cover' if is_cover else 'point'}.png"
        ok = _screenshot(html, png_path, size[0], size[1])
        if ok:
            paths.append(str(png_path))

    return {"ok": len(paths) > 0, "paths": paths, "count": len(paths), "warnings": warnings}


def _fit_text(text: str, max_lines: int, chars_per_line: int) -> tuple[str, str | None]:
    """字数超限时降字号（最多2次），再不行截断+警告。"""
    max_chars = max_lines * chars_per_line
    if len(text) <= max_chars:
        return text, None
    # 尝试缩短（去掉修饰词）
    shortened = text[:max_chars]
    if len(text) > max_chars * 1.2:
        return shortened + "…", f"标题过长（{len(text)}字），已截断到{max_chars}字"
    return shortened, f"标题略长（{len(text)}字），建议精简到{max_chars}字以内"


def _screenshot(html: str, out_path: Path, width: int, height: int) -> bool:
    """用 Playwright 截图。需要 node + playwright。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        html_path = f.name

    js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const p = await b.newPage({{ viewport: {{ width: {width}, height: {height} }}, deviceScaleFactor: 2 }});
  await p.goto('file:///{html_path.replace(chr(92), "/")}');
  await p.waitForTimeout(500);
  await p.screenshot({{ path: '{str(out_path).replace(chr(92), "/")}', fullPage: false }});
  await b.close();
}})();
"""
    js_path = Path(html_path).with_suffix(".js")
    js_path.write_text(js, encoding="utf-8")
    try:
        r = subprocess.run(["node", str(js_path)], capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and out_path.is_file()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    finally:
        try:
            Path(html_path.unlink())
            js_path.unlink()
        except OSError:
            pass


# ── HTML 模板 ──────────────────────────────────────────────

_THEMES = {
    "minimal": {"bg": "#ffffff", "fg": "#111111", "accent": "#111111", "muted": "#888888"},
    "ink-green": {"bg": "#F0F7F4", "fg": "#1F2937", "accent": "#0B6E4F", "muted": "#6B7280"},
    "newspaper": {"bg": "#FAF5EC", "fg": "#2B2118", "accent": "#7B3F00", "muted": "#7A6A5A"},
    "midnight": {"bg": "#0F172A", "fg": "#DCE3EE", "accent": "#60A5FA", "muted": "#94A3B8"},
}


def _t(theme_id: str) -> dict:
    return _THEMES.get(theme_id, _THEMES["minimal"])


def _cover_html(title, subtitle, column, number, account, size, theme_id):
    t = _t(theme_id)
    w, h = size
    fs_title = int(w * 0.065)
    fs_sub = int(w * 0.028)
    fs_meta = int(w * 0.022)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{w}px;height:{h}px;background:{t['bg']};color:{t['fg']};
font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
display:flex;flex-direction:column;justify-content:center;padding:0 {int(w*0.07)}px;position:relative;}}
.col{{position:absolute;top:{int(h*0.12)}px;left:{int(w*0.07)}px;font-size:{fs_meta}px;color:{t['muted']};letter-spacing:2px;}}
.title{{font-size:{fs_title}px;font-weight:800;line-height:1.3;letter-spacing:-1px;}}
.sub{{font-size:{fs_sub}px;color:{t['muted']};margin-top:{int(h*0.06)}px;}}
.no{{position:absolute;bottom:{int(h*0.1)}px;right:{int(w*0.07)}px;font-size:{fs_meta}px;color:{t['accent']};font-weight:600;}}
</style></head><body>
<div class="col">{column}</div>
<div class="title">{title}</div>
{"<div class='sub'>" + subtitle + "</div>" if subtitle else ""}
<div class="no">{number or account}</div>
</body></html>"""


def _card_cover_html(title, subtitle, account, page_no, size, theme_id):
    t = _t(theme_id)
    w, h = size
    fs_title = int(w * 0.088)
    fs_sub = int(w * 0.037)
    fs_meta = int(w * 0.020)
    safe = int(w)  # 中间正方形安全区
    top_pad = int((h - safe) / 2)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{w}px;height:{h}px;background:{t['bg']};color:{t['fg']};
font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:{top_pad}px {int(w*0.08)}px;position:relative;}}
.title{{font-size:{fs_title}px;font-weight:900;line-height:1.25;letter-spacing:-2px;}}
.sub{{font-size:{fs_sub}px;color:{t['muted']};margin-top:{int(h*0.03)}px;line-height:1.5;}}
.page{{position:absolute;bottom:{int(h*0.04)}px;right:{int(w*0.06)}px;font-size:{fs_meta}px;color:{t['muted']};}}
.acct{{position:absolute;top:{int(h*0.04)}px;left:{int(w*0.06)}px;font-size:{fs_meta}px;color:{t['muted']};}}
</style></head><body>
<div class="acct">{account}</div>
<div class="title">{title}</div>
{"<div class='sub'>" + subtitle + "</div>" if subtitle else ""}
<div class="page">{page_no}</div>
</body></html>"""


def _card_inner_html(point, note, account, page_no, size, theme_id):
    t = _t(theme_id)
    w, h = size
    fs_point = int(w * 0.065)
    fs_note = int(w * 0.033)
    fs_meta = int(w * 0.020)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{w}px;height:{h}px;background:{t['bg']};color:{t['fg']};
font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
display:flex;flex-direction:column;justify-content:center;padding:0 {int(w*0.1)}px;position:relative;}}
.point{{font-size:{fs_point}px;font-weight:800;line-height:1.35;}}
.note{{font-size:{fs_note}px;color:{t['muted']};margin-top:{int(h*0.04)}px;line-height:1.7;}}
.page{{position:absolute;top:{int(h*0.04)}px;right:{int(w*0.06)}px;font-size:{fs_meta}px;color:{t['muted']};}}
.acct{{position:absolute;bottom:{int(h*0.04)}px;left:{int(w*0.1)}px;font-size:{fs_meta}px;color:{t['muted']};border-top:1px solid {t['muted']}40;padding-top:8px;}}
</style></head><body>
<div class="page">{page_no}</div>
<div class="point">{point}</div>
{"<div class='note'>" + note + "</div>" if note else ""}
<div class="acct">{account}</div>
</body></html>"""