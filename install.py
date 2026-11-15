#!/usr/bin/env python3
"""稿台安装脚本：自动检测环境，装到 Claude Code / Cursor / WorkBuddy 等 Agent 环境。

skill 自包含：SKILL.md + 完整运行时（gaotai.py / core / themes / covers）
一起复制进技能目录，装完不依赖源码仓库位置。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
SKILL_SRC = ROOT / "skills" / "gaotai" / "SKILL.md"

# 运行时需要一起打包的文件/目录（相对仓库根）
RUNTIME_ITEMS = ["gaotai.py", "core", "themes", "covers"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")


def detect_targets() -> list[dict]:
    """检测可用的安装目标。"""
    targets = []
    home = Path.home()

    # Generic agent skills directory
    generic_skills = home / ".agent-skills"
    if generic_skills.is_dir():
        targets.append({"name": "Agent Skills", "path": generic_skills / "gaotai"})

    # Claude Code (global)
    claude_skills = home / ".claude" / "skills"
    if claude_skills.is_dir():
        targets.append({"name": "Claude Code (global)", "path": claude_skills / "gaotai"})

    # Claude Code (project)
    project_claude = Path.cwd() / ".claude" / "skills"
    if project_claude.is_dir():
        targets.append({"name": "Claude Code (project)", "path": project_claude / "gaotai"})

    # WorkBuddy / Cursor / generic
    for name, subdir in [("WorkBuddy", ".workbuddy/skills"), ("Cursor", ".cursor/skills")]:
        p = home / subdir
        if p.is_dir():
            targets.append({"name": name, "path": p / "gaotai"})

    return targets


def install_skill(target: dict) -> bool:
    """把 SKILL.md + 完整运行时复制到目标目录（自包含）。"""
    dest_dir = target["path"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SKILL_SRC, dest_dir / "SKILL.md")
    for item in RUNTIME_ITEMS:
        src = ROOT / item
        dst = dest_dir / item
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=IGNORE)
        else:
            shutil.copy2(src, dst)
    print(f"  OK {target['name']}: {dest_dir}")
    return True


def main():
    print("稿台 · 安装\n")

    if not SKILL_SRC.is_file():
        print(f"FAIL 找不到技能文件: {SKILL_SRC}")
        sys.exit(1)

    targets = detect_targets()

    if not targets:
        print("未检测到 Claude Code / Cursor / WorkBuddy 等 Agent 环境的技能目录。")
        print("你可以手动复制 skills/gaotai/ 整个目录到你的 Agent 技能目录。\n")
        local = Path.cwd() / ".gaotai-skill"
        install_skill({"name": "当前目录", "path": local})
    else:
        print(f"检测到 {len(targets)} 个安装目标:\n")
        for t in targets:
            install_skill(t)

    print("\nOK 安装完成（skill 自包含，含完整 CLI 运行时）。")
    print("  下一步: cd 到你的账号目录，在对话里说「初始化」让 Agent 引导你。")
    print("  手动用法: python <技能目录>/gaotai.py <命令>")


if __name__ == "__main__":
    main()