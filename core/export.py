"""发布包：把终稿打包成可直接粘贴/上传的文件集。

公众号文章 → paste.html + article-body.html + article.md + summary.txt + titles.txt + zip
小红书图文 → cards/*.png + caption.txt + zip
公众号图文 → images/*.png + caption.txt + zip
"""
from __future__ import annotations

import hashlib
import io
import struct
import zlib
from pathlib import Path
from typing import Any

from core.format import format_article, paste_shell


def build_export(
    md: str,
    title: str,
    platform: str = "wechat_article",
    theme_id: str = "minimal",
    theme_dir: str | None = None,
    out_dir: str | Path = "export",
    account_name: str = "",
    summary_hook: str = "",
    summary_full: str = "",
    titles: list[dict[str, Any]] | None = None,
    images: list[Path] | None = None,
) -> dict[str, Any]:
    """生成发布包，返回文件清单和路径。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    if platform == "wechat_article":
        fmt = format_article(md, theme_id, theme_dir)
        sub = out / "wechat"
        sub.mkdir(exist_ok=True)

        body_path = sub / "article-body.html"
        body_path.write_text(fmt.body_html, encoding="utf-8")
        files.append(str(body_path.relative_to(out)))

        shell = paste_shell(fmt.body_html, title, account_name)
        paste_path = sub / "paste.html"
        paste_path.write_text(shell, encoding="utf-8")
        files.append(str(paste_path.relative_to(out)))

        md_path = sub / "article.md"
        md_path.write_text(md, encoding="utf-8")
        files.append(str(md_path.relative_to(out)))

        # 摘要
        hook = summary_hook or title[:54]
        full = summary_full or md.replace("\n", " ")[:120]
        summary_path = sub / "summary.txt"
        summary_path.write_text(f"钩子（≤54字）：{hook}\n\n完整（≤120字）：{full}\n", encoding="utf-8")
        files.append(str(summary_path.relative_to(out)))

        # 标题候选
        if titles:
            lines = []
            for t in titles:
                mark = "★ " if t.get("chosen") else "  "
                lines.append(f"{mark}{t.get('text', '')}（{t.get('type', '')}）")
            titles_path = sub / "titles.txt"
            titles_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            files.append(str(titles_path.relative_to(out)))

        # 使用说明
        guide = sub / "使用说明.md"
        guide.write_text(
            "# 公众号发布步骤\n\n"
            "1. 用浏览器打开 `paste.html`\n"
            "2. 点「复制到公众号」按钮\n"
            "3. 去公众号编辑器 Ctrl+V 粘贴\n"
            "4. 检查样式是否正常（深色模式切换看一下）\n"
            "5. 填入标题、摘要、封面\n"
            "6. 预览 → 发布\n\n"
            "**不要直接复制 article-body.html 的源码**，要用 paste.html 的复制按钮。\n",
            encoding="utf-8",
        )
        files.append(str(guide.relative_to(out)))

        validation = {"errors": len(fmt.validation.errors), "warnings": len(fmt.validation.warnings)}

    elif platform in ("xhs_carousel", "wechat_imagepost"):
        sub = out / ("xhs" if platform == "xhs_carousel" else "imagepost")
        sub.mkdir(exist_ok=True)

        # 图片（由 cover.py 预先生成，这里只收集）
        if images:
            img_dir = sub / "images"
            img_dir.mkdir(exist_ok=True)
            for i, img in enumerate(images, 1):
                dest = img_dir / f"{i:02d}-{img.name}"
                dest.write_bytes(img.read_bytes())
                files.append(str(dest.relative_to(out)))

        # 文案
        caption_path = sub / "caption.txt"
        caption_path.write_text(md, encoding="utf-8")
        files.append(str(caption_path.relative_to(out)))

        guide = sub / "使用说明.md"
        if platform == "xhs_carousel":
            guide.write_text(
                "# 小红书发布步骤\n\n"
                "1. 打开小红书 App → 发笔记\n"
                "2. 按顺序上传 images/ 里的图片\n"
                "3. 把 caption.txt 的内容粘进正文\n"
                "4. 加标签、选话题\n"
                "5. 发布\n",
                encoding="utf-8",
            )
        else:
            guide.write_text(
                "# 公众号图文（小绿书）发布步骤\n\n"
                "1. 公众号后台 → 图片消息\n"
                "2. 按顺序上传 images/ 里的图片\n"
                "3. 把 caption.txt 的内容粘进文字区\n"
                "4. 发布\n",
                encoding="utf-8",
            )
        files.append(str(guide.relative_to(out)))
        validation = {"errors": 0, "warnings": 0}

    else:
        return {"ok": False, "error": f"不支持的平台：{platform}"}

    # ZIP（手写 STORE 格式，零依赖）
    zip_path = out / "export.zip"
    _build_zip(out, files, zip_path)
    files.append("export.zip")

    # 回执
    receipt = out / "publish-receipt.yaml"
    import yaml
    from datetime import datetime, timezone, timedelta
    receipt.write_text(yaml.safe_dump({
        "title": title,
        "platform": platform,
        "theme": theme_id,
        "account": account_name,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "files": files,
        "validation": validation,
        "md_hash": hashlib.sha256(md.encode()).hexdigest()[:16],
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    files.append("publish-receipt.yaml")

    return {
        "ok": True,
        "dir": str(out),
        "files": files,
        "validation": validation,
        "zip": str(zip_path),
    }


def _build_zip(base: Path, rel_files: list[str], zip_path: Path) -> None:
    """纯 Python STORE zip，不压缩（markdown/html 已经很小）。"""
    buf = io.BytesIO()
    central: list[bytes] = []
    for rel in rel_files:
        fp = base / rel
        if not fp.is_file():
            continue
        data = fp.read_bytes()
        name = rel.replace("\\", "/").encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        offset = buf.tell()
        # local file header（flags=0x800：文件名按 UTF-8 存，中文否则被解成 CP437 乱码）
        buf.write(struct.pack("<4sHHHHHIIIHH",
                              b"PK\x03\x04", 20, 0x800, 0, 0, 0, crc, len(data), len(data), len(name), 0))
        buf.write(name)
        buf.write(data)
        # central directory entry（结构体后必须紧跟文件名，与 local header 对齐）
        central.append(struct.pack("<4sHHHHHHIIIHHHHHII",
                                   b"PK\x01\x02", 20, 20, 0x800, 0, 0, 0, crc, len(data), len(data),
                                   len(name), 0, 0, 0, 0, 0, offset) + name)
    cd_offset = buf.tell()
    for c in central:
        buf.write(c)
    cd_size = buf.tell() - cd_offset
    buf.write(struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, len(central), len(central), cd_size, cd_offset, 0))
    zip_path.write_bytes(buf.getvalue())