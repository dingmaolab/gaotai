#!/usr/bin/env python3
"""稿台卸载脚本：只删技能文件，绝不碰账号内容。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main():
    print("稿台 · 卸载\n")
    home = Path.home()
    removed = []

    candidates = [
        ("Agent Skills", home / ".agent-skills" / "gaotai"),
        ("Claude Code (global)", home / ".claude" / "skills" / "gaotai"),
        ("Claude Code (project)", Path.cwd() / ".claude" / "skills" / "gaotai"),
        ("WorkBuddy", home / ".workbuddy" / "skills" / "gaotai"),
        ("Cursor", home / ".cursor" / "skills" / "gaotai"),
        ("当前目录", Path.cwd() / ".gaotai-skill"),
    ]

    for name, path in candidates:
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(f"{name}: {path}")
            print(f"  ✓ 已删除 {name}")

    if not removed:
        print("  未找到已安装的技能文件。")

    # 明确告知账号内容不动
    print("\n⚠ 账号内容目录未被触碰。")
    print("  你的稿子、灵感、风格数据都在各自的账号目录里，不会被删除。")
    print("  如需删除账号内容，请手动删除对应目录。")

    print("\n✓ 卸载完成。")


if __name__ == "__main__":
    main()