"""Markdown 解析：块级切分 + 行内渲染（给微信排版用）。

只覆盖写作实际会用的语法：标题、段落、列表、引用、代码块、表格、图片、分割线。
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Block:
    kind: str                      # heading | paragraph | list | quote | code | table | image | hr | footnote
    text: str = ""
    level: int = 0
    ordered: bool = False
    items: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)     # code
    lang: str = ""
    rows: list[list[str]] = field(default_factory=list)  # table
    header: list[str] = field(default_factory=list)
    url: str = ""
    alt: str = ""


def parse_blocks(md: str) -> list[Block]:
    lines = md.split("\n")
    blocks: list[Block] = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        line = raw.rstrip()

        # 空行
        if not line.strip():
            i += 1
            continue

        # 围栏代码
        m = re.match(r"^\s*```(\w*)\s*$", line)
        if m:
            lang = m.group(1)
            i += 1
            buf: list[str] = []
            while i < n and not re.match(r"^\s*```\s*$", lines[i]):
                buf.append(lines[i].rstrip("\n"))
                i += 1
            i += 1  # 跳过收尾围栏
            blocks.append(Block(kind="code", lines=buf, lang=lang))
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            blocks.append(Block(kind="heading", level=len(m.group(1)), text=m.group(2).strip()))
            i += 1
            continue

        # 分割线
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            blocks.append(Block(kind="hr"))
            i += 1
            continue

        # 图片独占一行
        m = re.match(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$", line)
        if m:
            blocks.append(Block(kind="image", alt=m.group(1), url=m.group(2)))
            i += 1
            continue

        # 表格：header 行 + 分隔行
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            header = _split_row(line)
            i += 2
            rows: list[list[str]] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(_split_row(lines[i]))
                i += 1
            blocks.append(Block(kind="table", header=header, rows=rows))
            continue

        # 引用
        if line.lstrip().startswith(">"):
            buf: list[str] = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]).rstrip())
                i += 1
            blocks.append(Block(kind="quote", lines=buf, text="\n".join(buf)))
            continue

        # 列表
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            ordered = bool(re.match(r"\d", m.group(2)))
            items: list[str] = []
            while i < n:
                mm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[i])
                if not mm:
                    break
                items.append(mm.group(3).strip())
                i += 1
            blocks.append(Block(kind="list", items=items, ordered=ordered))
            continue

        # 段落：吃到空行或下一个块起始
        buf = [line.strip()]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                break
            if re.match(r"^\s*(#{1,6}\s|```|>|!\[|\s*[-*+]\s|\s*\d+[.)]\s)", nxt):
                break
            if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", nxt):
                break
            buf.append(nxt.strip())
            i += 1
        blocks.append(Block(kind="paragraph", text=" ".join(buf)))

    return blocks


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


# ---------------- 行内渲染 ----------------

_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def escape_html(s: str) -> str:
    return "".join(_ESC.get(c, c) for c in s)


def escape_attr(s: str) -> str:
    return escape_html(s).replace("'", "&#39;")


def render_inline(text: str, style_bold: dict[str, Any], style_italic: dict[str, Any], style_code: dict[str, Any]) -> str:
    """行内格式 → HTML。每个文本片段单独包 span，微信才不会丢样式。"""
    from core.format import leaf  # 延迟导入避免循环

    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        # 行内代码 `x`
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j > i:
                out.append(leaf(escape_html(text[i + 1:j]), style_code.get("style", ""), style_code.get("dark")))
                i = j + 1
                continue
        # 加粗 **x** / __x__
        if text[i:i + 2] in ("**", "__"):
            mark = text[i:i + 2]
            j = text.find(mark, i + 2)
            if j > i + 2:
                out.append(leaf(escape_html(text[i + 2:j]), style_bold.get("style", ""), style_bold.get("dark")))
                i = j + 2
                continue
        # 斜体 *x* / _x_
        if text[i] in "*_":
            j = text.find(text[i], i + 1)
            if j > i + 1:
                out.append(leaf(escape_html(text[i + 1:j]), style_italic.get("style", ""), style_italic.get("dark")))
                i = j + 1
                continue
        # 链接 [text](url) → 转脚注
        if text[i] == "[":
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
            if m:
                out.append(("__LINK__", m.group(1), m.group(2)))
                i += m.end()
                continue
        # 普通文本：吃到下一个标记
        j = i
        while j < n and text[j] not in "`*_[": 
            j += 1
        if j == i:
            j = i + 1
        out.append(escape_html(text[i:j]))
        i = j
    return "".join(x if isinstance(x, str) else f"\x00LINK\x00{x[1]}\x00{x[2]}\x00" for x in out)


# ---------------- 中文排版细节 ----------------

_CJK = r"\u4e00-\u9fff"
_LATIN = r"A-Za-z0-9"


def cjk_space(s: str) -> str:
    """中英之间补一个空格（已经是空格的跳过）。"""
    s = re.sub(rf"([{_CJK}])([{_LATIN}])", r"\1 \2", s)
    s = re.sub(rf"([{_LATIN}])([{_CJK}])", r"\1 \2", s)
    return s


_PUNCT_FIX = [(r",", "，"), (r";", "；"), (r":", "："), (r"\?", "？"), (r"!", "！")]


def fullwidth_punct(s: str) -> str:
    """中文语境里的半角标点转全角（只处理中文后的）。"""
    for half, full in _PUNCT_FIX:
        s = re.sub(rf"([{_CJK}]){half}", rf"\1{full}", s)
    return s


def bold_punct_fix(s: str) -> str:
    """把「字，字」里的逗号从加粗范围里挤出来：**粗，** → **粗**，"""
    return re.sub(r"(\*\*[^*]+\*\*)([，。；：！？、）】」』])", r"\1\2", s)