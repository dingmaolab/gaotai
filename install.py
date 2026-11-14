#!/usr/bin/env python3
"""稿台安装脚本：自动检测环境，装到 Claude Code / Cursor / WorkBuddy 等 Agent 环境。"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SKILL_SRC = Path(__file__).parent / "skills" / "gaotai" / "SKILL.md"
CLI_SRC = Path(__file__).parent / "gaotai.py"


def detect_targets() -> list[dict]:
    """检测可用的安装目标。"""
    targets = []
    home = Path.home()

    # Generic agent skills directory
    generic_skills = home / ".agent-skills"
    if generic_skills.is_dir():
        targets.append({"name": "Agent Skills", "path": generic_skills / "gaotai", "type": "skill_dir"})

    # Claude Code (global)
    claude_skills = home / ".claude" / "skills"
    if claude_skills.is_dir():
        targets.append({"name": "Claude Code (global)", "path": claude_skills / "gaotai", "type": "skill_dir"})

    # Claude Code (project)
    project_claude = Path.cwd() / ".claude" / "skills"
    if project_claude.is_dir():
        targets.append({"name": "Claude Code (project)", "path": project_claude / "gaotai", "type": "skill_dir"})

    # WorkBuddy / Cursor / generic
    for name, subdir in [("WorkBuddy", ".workbuddy/skills"), ("Cursor", ".cursor/skills")]:
        p = home / subdir
        if p.is_dir():
            targets.append({"name": name, "path": p / "gaotai", "type": "skill_dir"})

    return targets


def install_skill(target: dict) -> bool:
    """把 SKILL.md 复制到目标目录。"""
    dest_dir = target["path"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "SKILL.md"
    shutil.copy2(SKILL_SRC, dest_file)
    print(f"  ✓ {target['name']}: {dest_file}")
    return True


def install_cli_link():
    """尝试把 gaotai.py 链接到 PATH 中的位置。"""
    # 优先用 pip install -e . 如果有的话
    # 否则提示用户手动加 alias
    print(f"\n  CLI 入口: {CLI_SRC}")
    print(f"  用法: python {CLI_SRC} <命令>")
    print(f"  或添加 alias: alias gaotai='python {CLI_SRC}'")


def main():
    print("稿台 · 安装\n")

    if not SKILL_SRC.is_file():
        print(f"✗ 找不到技能文件: {SKILL_SRC}")
        sys.exit(1)

    targets = detect_targets()

    if not targets:
        print("未检测到 Claude Code / Cursor / WorkBuddy 等 Agent 环境 的技能目录。")
        print("你可以手动复制 skills/gaotai/SKILL.md 到你的 Agent 技能目录。\n")
        # 至少装到当前目录
        local = Path.cwd() / ".gaotai-skill"
        local.mkdir(exist_ok=True)
        shutil.copy2(SKILL_SRC, local / "SKILL.md")
        print(f"  ✓ 已复制到当前目录: {local / 'SKILL.md'}")
    else:
        print(f"检测到 {len(targets)} 个安装目标:\n")
        for t in targets:
            install_skill(t)

    install_cli_link()

    print("\n✓ 安装完成。")
    print("  下一步: cd 到你的账号目录，运行 python gaotai.py init --name 你的账号名")
    print("  或者在对话里说「初始化」让 Agent 引导你。")


if __name__ == "__main__":
    main()