"""微信排版：markdown → 可直接粘进公众号编辑器的 HTML。

微信编辑器的红线（踩了会掉样式或被吃掉）：
  · 不能用 style / script / div / link 标签 → 全部用 section / span / p
  · 不能用 class / id
  · 不能用 position / float / grid / flex / @media / CSS 变量
  · 所有样式必须内联
  · 文字必须包在 <span leaf=""> 里
  · 外链不能带 href → 转成脚注
  · 图片不能是 base64 → 用占位符
  · 深色模式用 data-darkmode-color / data-darkmode-bgcolor / data-darkmode-bordercolor
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from core.md import (
    Block, bold_punct_fix, cjk_space, escape_attr, escape_html,
    fullwidth_punct, parse_blocks,
)
from core.themes import DEFAULT_FONT, get_theme


def leaf(text: str, style: str = "", dark_color: str | None = None) -> str:
    """微信唯一认的文字容器。空 style 也输出，保证结构一致。"""
    attrs = f' style="{style}"' if style else ""
    if dark_color:
        attrs += f' data-darkmode-color="{dark_color}"'
    return f'<span leaf=""{attrs}>{text}</span>'


@dataclass
class Validation:
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    def err(self, rule: str, msg: str) -> None:
        self.errors.append({"rule": rule, "msg": msg})

    def warn(self, rule: str, msg: str) -> None:
        self.warnings.append({"rule": rule, "msg": msg})


@dataclass
class FormatResult:
    body_html: str
    footnotes: int
    images: list[dict[str, str]]
    validation: Validation
    stats: dict[str, int]


def format_article(md: str, theme_id: str = "minimal", theme_dir: str | None = None) -> FormatResult:
    theme = get_theme(theme_id, theme_dir)
    R = theme["roles"]
    P = R["primary"]
    Tx = R["text"]
    Mu = R["muted"]
    Bg = R["bgCard"]
    Bd = R["border"]
    body_size = theme["body"]["size"]
    body_line = theme["body"]["line"]
    font = theme["body"].get("family") or DEFAULT_FONT

    footnotes: list[str] = []
    images: list[dict[str, str]] = []
    v = Validation()
    h2_count = 0
    char_count = 0

    def inline(text: str) -> str:
        """行内渲染：加粗/斜体/代码/链接转脚注。"""
        text = bold_punct_fix(text)
        text = cjk_space(text)
        text = fullwidth_punct(text)
        out: list[str] = []
        i, n = 0, len(text)
        while i < n:
            # 行内代码
            if text[i] == "`":
                j = text.find("`", i + 1)
                if j > i:
                    out.append(leaf(
                        escape_html(text[i + 1:j]),
                        f"font-family:Consolas,Menlo,monospace;font-size:90%;background:{Bg['light']};padding:1px 4px;border-radius:3px;",
                        Bg["dark"],
                    ))
                    i = j + 1
                    continue
            # 链接 → 脚注
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
            if m:
                label, url = m.group(1), m.group(2)
                footnotes.append(url)
                idx = len(footnotes)
                out.append(leaf(escape_html(label), f"color:{P['light']};", P["dark"]))
                out.append(f'<sup style="font-size:11px;color:{P["light"]};vertical-align:super;" data-darkmode-color="{P["dark"]}">{idx}</sup>')
                i += m.end()
                continue
            # 加粗
            if text[i:i + 2] in ("**", "__"):
                mark = text[i:i + 2]
                j = text.find(mark, i + 2)
                if j > i + 2:
                    out.append(leaf(escape_html(text[i + 2:j]), f"font-weight:700;", None))
                    i = j + 2
                    continue
            # 斜体
            if text[i] in "*_":
                j = text.find(text[i], i + 1)
                if j > i + 1:
                    out.append(leaf(escape_html(text[i + 1:j]), "font-style:italic;", None))
                    i = j + 1
                    continue
            # 普通文本
            j = i
            while j < n and text[j] not in "`*_[":
                j += 1
            if j == i:
                j = i + 1
            out.append(leaf(escape_html(text[i:j]), "", None))
            i = j
        return "".join(out)

    parts: list[str] = []
    blocks = parse_blocks(md)
    for b in blocks:
        if b.kind == "heading":
            char_count += len(b.text)
            if b.level == 2:
                h2_count += 1
                num = f"{h2_count:02d} " if theme["sectionNumbering"] else ""
                inner = inline(b.text)
                hs, hw = theme["h2"]["size"], theme["h2"]["weight"]
                decor = theme["h2"]["decor"]
                if decor == "left-bar":
                    parts.append(
                        f'<section style="margin:36px 0 18px;padding-left:12px;border-left:4px solid {P["light"]};" data-darkmode-bordercolor="{P["dark"]}">'
                        + leaf(escape_html(num) + inner, f"font-size:{hs}px;font-weight:{hw};color:{Tx['light']};line-height:1.5;", Tx["dark"])
                        + "</section>"
                    )
                elif decor == "numbered":
                    parts.append(
                        f'<section style="margin:36px 0 18px;">'
                        + leaf(escape_html(num), f"font-size:{hs}px;font-weight:{hw};color:{P['light']};margin-right:6px;", P["dark"])
                        + leaf(inner, f"font-size:{hs}px;font-weight:{hw};color:{Tx['light']};", Tx["dark"])
                        + "</section>"
                    )
                elif decor == "underline":
                    parts.append(
                        f'<section style="margin:36px 0 18px;">'
                        + leaf(inner, f"font-size:{hs}px;font-weight:{hw};color:{Tx['light']};border-bottom:2px solid {P['light']};padding-bottom:6px;", Tx["dark"])
                        + "</section>"
                    )
                else:  # pill
                    parts.append(
                        f'<section style="margin:34px 0 16px;"><span style="display:inline-block;padding:4px 12px;background:{Bg["light"]};border-radius:999px;" data-darkmode-bgcolor="{Bg["dark"]}">'
                        + leaf(inner, f"font-size:{hs}px;font-weight:{hw};color:{Tx['light']};letter-spacing:0.5px;", Tx["dark"])
                        + "</span></section>"
                    )
            elif b.level == 1:
                parts.append(
                    f'<section style="margin:8px 0 24px;">'
                    + leaf(inline(b.text), f"font-size:22px;font-weight:700;color:{Tx['light']};line-height:1.35;", Tx["dark"])
                    + "</section>"
                )
            else:
                parts.append(
                    f'<section style="margin:24px 0 12px;">'
                    + leaf(inline(b.text), f"font-size:16px;font-weight:700;color:{Tx['light']};", Tx["dark"])
                    + "</section>"
                )
        elif b.kind == "paragraph":
            char_count += len(b.text)
            parts.append(
                f'<p style="margin:0 0 20px;font-size:{body_size}px;line-height:{body_line};color:{Tx["light"]};letter-spacing:0.02em;text-align:justify;" data-darkmode-color="{Tx["dark"]}">'
                + inline(b.text)
                + "</p>"
            )
        elif b.kind == "list":
            rows = []
            for idx, item in enumerate(b.items, 1):
                marker = f"{idx}. " if b.ordered else "• "
                rows.append(
                    f'<section style="margin:0 0 10px;padding-left:4px;">'
                    + leaf(marker, f"color:{P['light']};font-size:{body_size}px;", P["dark"])
                    + leaf(inline(item), f"font-size:{body_size}px;line-height:1.85;color:{Tx['light']};", Tx["dark"])
                    + "</section>"
                )
            parts.append(f'<section style="margin:0 0 20px;">{"".join(rows)}</section>')
        elif b.kind == "quote":
            char_count += len(b.text)
            inner = "<br/>".join(inline(x) for x in (b.lines or [b.text]))
            qs = theme["quote"]["size"]
            variant = theme["quote"]["variant"]
            if variant == "line":
                parts.append(
                    f'<section style="margin:0 0 20px;padding:2px 0 2px 14px;border-left:3px solid {P["light"]};" data-darkmode-bordercolor="{P["dark"]}">'
                    + leaf(inner, f"font-size:{qs}px;line-height:1.8;color:{Mu['light']};", Mu["dark"]) + "</section>"
                )
            elif variant == "plain":
                parts.append(
                    f'<section style="margin:0 0 20px;padding:0 8px;">'
                    + leaf(inner, f"font-size:{qs}px;line-height:1.8;color:{Mu['light']};font-style:italic;", Mu["dark"]) + "</section>"
                )
            elif variant == "bigquote":
                parts.append(
                    '<section style="margin:28px 0;text-align:center;">'
                    + leaf("「", f"font-size:26px;line-height:1;color:{Bd['light']};", Bd["dark"])
                    + leaf(inner, f"font-size:{qs}px;line-height:1.8;color:{Tx['light']};", Tx["dark"])
                    + leaf("」", f"font-size:26px;line-height:1;color:{Bd['light']};", Bd["dark"])
                    + "</section>"
                )
            else:  # card
                parts.append(
                    f'<section style="margin:0 0 20px;padding:14px 16px;background:{Bg["light"]};border-left:3px solid {Bd["light"]};" data-darkmode-bgcolor="{Bg["dark"]}">'
                    + leaf(inner, f"font-size:{qs}px;line-height:1.75;color:{Mu['light']};", Mu["dark"]) + "</section>"
                )
        elif b.kind == "code":
            dark = theme["code"]["variant"] == "dark"
            bg = "#0F172A" if dark else Bg["light"]
            fg = "#E2E8F0" if dark else Tx["light"]
            bg_dark = "#0B1220" if dark else Bg["dark"]
            style = f"font-family:Consolas,Menlo,'Courier New',monospace;font-size:13px;line-height:1.7;color:{fg};white-space:pre-wrap;word-break:break-all;"
            rows = "".join(
                f'<section style="margin:0;padding:0 16px;">{leaf(escape_html(x) or "&nbsp;", style, fg)}</section>'
                for x in (b.lines or [""])
            )
            parts.append(f'<section style="margin:0 0 20px;padding:12px 0;background:{bg};border-radius:6px;" data-darkmode-bgcolor="{bg_dark}">{rows}</section>')
        elif b.kind == "table":
            head_cells = "".join(
                f'<td style="padding:8px 10px;border:1px solid {Bd["light"]};font-size:13px;font-weight:700;color:{Tx["light"]};background:{Bg["light"]};" data-darkmode-bgcolor="{Bg["dark"]}">{leaf(c, "", None)}</td>'
                for c in b.header
            )
            body_rows = ""
            for r in b.rows:
                cells = "".join(
                    f'<td style="padding:8px 10px;border:1px solid {Bd["light"]};font-size:13px;color:{Tx["light"]};" data-darkmode-color="{Tx["dark"]}">{leaf(escape_html(c), "", Tx["dark"])}</td>'
                    for c in r
                )
                body_rows += f'<tr data-darkmode-color="{Tx["dark"]}">{cells}</tr>'
            parts.append(
                '<section style="margin:0 0 20px;overflow-x:auto;">'
                f'<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                f'<thead><tr>{head_cells}</tr></thead><tbody>{body_rows}</tbody></table></section>'
            )
        elif b.kind == "image":
            images.append({"alt": b.alt, "url": b.url})
            parts.append(
                f'<section style="margin:0 0 20px;padding:24px 16px;text-align:center;border:1px dashed {Bd["light"]};border-radius:6px;" data-darkmode-bordercolor="{Bd["dark"]}">'
                + leaf(f"［图片：{escape_html(b.alt or '待插入')}］", f"font-size:13px;color:{Mu['light']};", Mu["dark"])
                + "</section>"
            )
        elif b.kind == "hr":
            parts.append(f'<section style="margin:28px 0;text-align:center;">'
                         + leaf("· · ·", f"font-size:14px;color:{Bd['light']};letter-spacing:8px;", Bd["dark"]) + "</section>")

    # 脚注区
    if footnotes:
        rows = "".join(
            f'<section style="margin:0 0 6px;">'
            + leaf(f"{i}. ", f"font-size:12px;color:{Mu['light']};", Mu["dark"])
            + leaf(escape_html(u), f"font-size:12px;color:{Mu['light']};word-break:break-all;", Mu["dark"])
            + "</section>"
            for i, u in enumerate(footnotes, 1)
        )
        parts.append(
            f'<section style="margin:32px 0 0;padding-top:14px;border-top:1px solid {Bd["light"]};" data-darkmode-bordercolor="{Bd["dark"]}">'
            f'<section style="margin:0 0 8px;">{leaf("参考链接", f"font-size:12px;font-weight:700;color:{Mu["light"]};", Mu["dark"])}</section>'
            + rows + "</section>"
        )

    body_html = (
        f'<section style="font-family:{font};max-width:677px;margin:0 auto;padding:20px 16px;">'
        + "".join(parts) + "</section>"
    )
    validate(body_html, v)
    return FormatResult(
        body_html=body_html,
        footnotes=len(footnotes),
        images=images,
        validation=v,
        stats={"chars": char_count, "h2": h2_count},
    )


_FORBIDDEN_TAGS = re.compile(r"<(style|script|div|link|iframe|frame)\b", re.I)
_BASE64 = re.compile(r"data:image/", re.I)


def validate(body_html: str, v: Validation) -> None:
    """微信红线校验。errors 必须修，warnings 建议修。"""
    for tag in {m.group(1).lower() for m in _FORBIDDEN_TAGS.finditer(body_html)}:
        v.err("forbidden-tag", f"出现了微信不支持的 <{tag}> 标签")
    if re.search(r"\bclass=", body_html):
        v.err("class-attr", "出现了 class 属性，微信会丢样式")
    if re.search(r"\bid=", body_html):
        v.warn("id-attr", "出现了 id 属性，建议去掉")
    for kw in ("position:", "float:", "grid-template", "display:flex", "display: grid", "@media", "var(--"):
        if kw in body_html:
            v.err("unsupported-css", f"用了微信不支持的 CSS：{kw}")
    if _BASE64.search(body_html):
        v.err("base64-image", "图片用了 base64，微信会吃掉")
    if re.search(r'<a\s', body_html, re.I):
        v.err("anchor-tag", "出现了 <a> 标签，微信会剥掉链接，应该转脚注")
    # 必须的深色模式属性
    if 'leaf=""' not in body_html:
        v.err("no-leaf", "没有 span leaf 包裹，微信会丢文字样式")
    if "data-darkmode-color" not in body_html:
        v.warn("no-darkmode", "没有 data-darkmode-color，深色模式下正文可能看不清")
    # 裸文本：CJK 文字不在任何 span leaf 里
    bare = _bare_cjk(body_html)
    if bare > 0:
        v.warn("leaf-wrap", f"{bare} 段中文没有包在 span leaf 里")


def _bare_cjk(h: str) -> int:
    stack: list[str] = []
    count = 0
    for m in re.finditer(r"</?([a-zA-Z][\w-]*)[^>]*>|([^<]+)", h):
        whole, tag, text = m.group(0), m.group(1), m.group(2)
        if tag:
            t = tag.lower()
            if whole.startswith("</"):
                idx = -1
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k] in (t, "leaf" if t == "span" else t):
                        idx = k
                        break
                if idx >= 0:
                    del stack[idx:]
            elif not whole.endswith("/>"):
                if t == "span" and 'leaf=""' in whole:
                    stack.append("leaf")
                else:
                    stack.append(t)
        elif text and re.search(r"[\u4e00-\u9fff]", text):
            if "leaf" not in stack:
                count += 1
    return count


def paste_shell(body_html: str, title: str, account: str = "") -> str:
    """独立预览页：375px 手机宽度 + 一键复制。复制的是 body_html 的富文本。"""
    safe_title = escape_attr(title)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{safe_title} · 公众号预览</title>
<style>
  body{{margin:0;background:#eef0f2;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;}}
  .bar{{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid #e5e5e5;padding:12px 16px;display:flex;gap:10px;align-items:center;}}
  .bar b{{font-size:14px;}}
  .bar small{{color:#888;font-size:12px;}}
  button{{margin-left:auto;font-size:13px;padding:7px 16px;border-radius:6px;border:1px solid #111;background:#111;color:#fff;cursor:pointer;}}
  button.ok{{background:#0B6E4F;border-color:#0B6E4F;}}
  .stage{{display:flex;justify-content:center;padding:24px 12px 60px;}}
  .phone{{width:375px;background:#fff;border-radius:10px;box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden;}}
  .hint{{text-align:center;font-size:12px;color:#888;padding:0 0 20px;}}
</style></head><body>
<div class="bar">
  <div><b>{safe_title}</b>{f'<br/><small>{escape_html(account)}</small>' if account else ''}</div>
  <button id="copy">复制到公众号</button>
</div>
<div class="stage"><div class="phone" id="content">{body_html}</div></div>
<p class="hint">点「复制」后，去公众号编辑器里 Ctrl+V 粘贴。样式会跟着过来。</p>
<script>
document.getElementById('copy').addEventListener('click', async () => {{
  const el = document.getElementById('content');
  const btn = document.getElementById('copy');
  try {{
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges(); sel.addRange(range);
    const ok = document.execCommand('copy');
    sel.removeAllRanges();
    if (!ok) throw new Error('execCommand failed');
    btn.textContent = '已复制'; btn.classList.add('ok');
    setTimeout(() => {{ btn.textContent = '复制到公众号'; btn.classList.remove('ok'); }}, 1800);
  }} catch (e) {{
    btn.textContent = '请手动全选复制';
    setTimeout(() => {{ btn.textContent = '复制到公众号'; }}, 2000);
  }}
}});
</script>
</body></html>"""