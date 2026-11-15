#!/usr/bin/env python3
"""稿台 CLI —— 唯一入口。cd 进账号目录，所有命令默认作用于当前目录。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 让 core 可导入
sys.path.insert(0, str(Path(__file__).parent))

from core.vault import Vault, resolve_vault, init_vault, local_date, VaultError


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fail(code, msg, next_action=None):
    out({"ok": False, "code": code, "message": msg, **({"nextAction": next_action} if next_action else {})})
    sys.exit(1)


def get_vault(args) -> tuple[Vault, "Account"]:
    root = resolve_vault(getattr(args, "vault", None))
    v = Vault(root)
    if not v.exists():
        fail("NO_VAULT", f"内容库不存在：{root}", "先运行 gaotai init")
    acc = v.resolve_account(getattr(args, "account", None))
    return v, acc


def main():
    p = argparse.ArgumentParser(prog="gaotai", description="稿台 · 自媒体内容生产")
    p.add_argument("--vault", help="内容库路径（默认当前目录或 ~/GaotaiVault）")
    sub = p.add_subparsers(dest="cmd")

    # init
    s = sub.add_parser("init", help="在当前目录初始化账号")
    s.add_argument("--name", required=True, help="账号中文名")
    s.add_argument("--id", help="账号 id（小写连字符，默认从 name 生成）")
    s.add_argument("--positioning", default="")
    s.add_argument("--audience", default="")

    # note
    s = sub.add_parser("note", help="记一条灵感")
    s.add_argument("text", help="一句话")
    s.add_argument("--category", default="other")
    s.add_argument("--tags", default="")

    # hot
    s = sub.add_parser("hot", help="抓热点 / 重筛")
    s.add_argument("--fetch-only", action="store_true", help="只抓全量到 shared，不筛")
    s.add_argument("--refilter", action="store_true", help="从已有 raw 重筛，不重抓")
    s.add_argument("--date", default=None)

    # new
    s = sub.add_parser("new", help="新建创作项目")
    s.add_argument("title", help="标题")
    s.add_argument("--platform", default="wechat_article")
    s.add_argument("--source", default="", help="素材来源维度")
    s.add_argument("--urgency", default="none")
    s.add_argument("--intent", default="")

    # learn
    s = sub.add_parser("learn", help="学习风格")
    s.add_argument("files", nargs="+", help="自己的文章（可多篇）；--diff 时传初稿+终稿；--reference 时传单文件或 URL")
    s.add_argument("--author", default="", help="参考文章的作者")
    s.add_argument("--reference", action="store_true", help="强制作为第三方参考")
    s.add_argument("--own", action="store_true", help="强制作为自己的范文（即使只有两篇）")
    s.add_argument("--diff", action="store_true", help="改稿对比：恰好两个文件，初稿+终稿")

    # profile
    sub.add_parser("profile", help="查看画像和置信度")

    # card-build
    sub.add_parser("card-build", help="重整风格卡 dna.md")

    # check
    s = sub.add_parser("check", help="机械审稿")
    s.add_argument("md", help="稿件路径")
    s.add_argument("--format", default="longform", dest="fmt")
    s.add_argument("--source", default="")
    s.add_argument("--audience", default="peer")

    # tone
    s = sub.add_parser("tone", help="AI 味检测")
    s.add_argument("md", help="稿件路径")
    s.add_argument("--compare", default=None, help="改后文件路径")

    # format
    s = sub.add_parser("format", help="公众号排版预览")
    s.add_argument("md", help="稿件路径")
    s.add_argument("--theme", default="minimal")
    s.add_argument("--out", default=None)

    # cover / cards
    s = sub.add_parser("cover", help="生成封面")
    s.add_argument("md", help="稿件路径")
    s.add_argument("--platform", default="wechat_article")
    s.add_argument("--theme", default="minimal")
    s.add_argument("--subtitle", default="")
    s.add_argument("--column", default="")

    s = sub.add_parser("cards", help="生成小红书/图文卡片")
    s.add_argument("md", help="稿件路径")
    s.add_argument("--platform", default="xhs_carousel")
    s.add_argument("--theme", default="minimal")
    s.add_argument("--points", default=None, help="要点文件（一行一个）")

    # send
    s = sub.add_parser("send", help="出发布包")
    s.add_argument("md", help="终稿路径")
    s.add_argument("--title", required=True)
    s.add_argument("--platform", default="wechat_article")
    s.add_argument("--theme", default="minimal")
    s.add_argument("--hook", default="")
    s.add_argument("--summary", default="")

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return

    try:
        _dispatch(args)
    except VaultError as e:
        fail(e.code, e.message, e.next_action)
    except Exception as e:
        fail("INTERNAL", str(e))


def _dispatch(args):
    cmd = args.cmd

    if cmd == "init":
        # 一个账号一个目录：默认在当前目录建号；显式 --vault / GAOTAI_VAULT 才走库布局
        if args.vault:
            root = Path(args.vault).resolve()
        elif os.environ.get("GAOTAI_VAULT"):
            root = Path(os.environ["GAOTAI_VAULT"]).resolve()
        else:
            root = Path.cwd()
        aid = args.id or args.name.lower().replace(" ", "-")[:30]
        r = init_vault(root, aid, args.name, positioning=args.positioning, audience=args.audience)
        out({"ok": True, **r, "next": "编辑 .gaotai/account.yaml 填栏目和关注词；然后喂 3-5 篇你自己的文章"})
        return

    v, acc = get_vault(args)

    if cmd == "note":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        path = v.create_note("idea", args.text[:24], {"category": args.category, "tags": tags, "source": "cli"},
                             f"## 原始想法\n\n{args.text}\n\n## AI 补充\n\n（暂无）\n", account=acc)
        out({"ok": True, "path": str(path.relative_to(v.root)), "account": acc.name})

    elif cmd == "hot":
        from core.hot import fetch_raw, filter_for_account, save_raw, load_raw, save_account_hotspots
        date = args.date or local_date()
        shared = v.root.parent / ".gaotai-shared" if v.root.name != "GaotaiVault" else v.root / "shared"
        # 简化：shared 放在 vault 同级
        shared = v.root.parent / ".gaotai-shared"

        if args.refilter:
            raw = load_raw(shared, date)
            if not raw:
                fail("NO_RAW", f"{date} 没有原始数据", "先运行 gaotai hot --fetch-only")
        else:
            boards = acc.data.get("sources")
            raw = fetch_raw(boards)
            # 全部榜单失败 → 不覆盖已有 raw（保住上次成功的数据），并暴露错误
            states = [s.get("state") for s in raw.get("sources", [])]
            if states and all(s != "ok" for s in states):
                errs = "; ".join(f"{s.get('board')}: {s.get('error', s.get('state'))}"
                                 for s in raw.get("sources", [])[:3])
                if all(s == "blocked" for s in states):
                    fail("FETCH_BLOCKED", f"tophub 反爬拦截（{date}）：{errs}",
                         "等 10-30 分钟再抓；当天已抓过可用 gaotai hot --refilter 重筛不重抓")
                fail("FETCH_FAILED", f"热点抓取失败（{date}）：{errs}",
                     "检查网络 / playwright 安装（pip install playwright && playwright install chromium）")
            save_raw(shared, date, raw)

        if args.fetch_only:
            out({"ok": True, "date": date, "sources": raw.get("sources", []), "items_count": len(raw.get("items", []))})
            return

        items = filter_for_account(raw, acc.data)
        paths = save_account_hotspots(acc.dir, date, items)
        out({"ok": True, "date": date, "filtered": len(items), "paths": [str(p.relative_to(v.root)) for p in paths[:10]]})

    elif cmd == "new":
        proj_dir = acc.dir / "projects" / f"{local_date()}-{args.title[:30]}"
        proj_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "title": args.title, "platform": args.platform,
            "dimensions": {"source": args.source, "urgency": args.urgency, "intent": args.intent},
            "created_at": local_date(),
        }
        import yaml
        (proj_dir / "meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
        out({"ok": True, "dir": str(proj_dir.relative_to(v.root)), "next": "写 sources.md → brief.md → draft.md"})

    elif cmd == "learn":
        from core.style import learn_from_own, learn_from_reference, learn_from_diff
        files = [Path(f) for f in args.files]
        if args.diff:
            if len(files) != 2 or not all(f.is_file() for f in files):
                fail("BAD_ARGS", "--diff 需要恰好两个文件：初稿 终稿")
                return
            r = learn_from_diff(v, acc, files[0].read_text("utf-8"), files[1].read_text("utf-8"))
        elif args.reference or (len(files) == 1 and not files[0].is_file()):
            text = args.files[0] if not files[0].is_file() else files[0].read_text("utf-8")
            r = learn_from_reference(v, acc, text, author=args.author)
        elif args.own or len(files) >= 3:
            if not all(f.is_file() for f in files):
                fail("BAD_ARGS", "范文学习需要全部是存在的文件")
                return
            r = learn_from_own(v, acc, files)
        elif len(files) == 2 and all(f.is_file() for f in files):
            fail("AMBIGUOUS_LEARN",
                 "两个文件有歧义：是「初稿+终稿」还是「两篇范文」？",
                 "改稿对比加 --diff；喂自己的范文加 --own")
            return
        elif len(files) == 1 and files[0].is_file():
            r = learn_from_own(v, acc, files)
        else:
            fail("BAD_ARGS", "传文件学风格：多篇范文直接传；两篇用 --own 或 --diff 消歧；参考用 --reference")
            return
        out(r)

    elif cmd == "profile":
        from core.style import get_profile
        out({"ok": True, "account": acc.name, **get_profile(v, acc)})

    elif cmd == "card-build":
        from core.style import build_card
        out(build_card(v, acc))

    elif cmd == "check":
        from core.check import check
        md = Path(args.md).read_text("utf-8")
        dims = {"format": args.fmt, "source": args.source, "audience": args.audience}
        overrides = acc.data.get("overrides", {})
        out({"ok": True, **check(md, dims, overrides)})

    elif cmd == "tone":
        from core.tone import analyze, compare
        md = Path(args.md).read_text("utf-8")
        baseline = None
        prof_path = v.account_path(acc, "style", "profile.yaml")
        if prof_path.is_file():
            import yaml
            prof = yaml.safe_load(prof_path.read_text("utf-8")) or {}
            lang = prof.get("language", {})
            baseline = {"avg_sentence_len": lang.get("avg_sentence_len"), "exclaim_per_1k": lang.get("exclaim_per_1k")}
        before = analyze(md, baseline)
        if args.compare:
            after = analyze(Path(args.compare).read_text("utf-8"), baseline)
            out({"ok": True, "before": {"scores": before["scores"], "grade": before["grade"]},
                 "after": {"scores": after["scores"], "grade": after["grade"]},
                 "comparison": compare(before, after)})
        else:
            out({"ok": True, **before})

    elif cmd == "format":
        from core.format import format_article, paste_shell
        md = Path(args.md).read_text("utf-8")
        theme_dir = Path(__file__).parent / "themes"
        r = format_article(md, args.theme, str(theme_dir))
        out_dir = Path(args.out) if args.out else Path(args.md).parent / "preview"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "paste.html").write_text(paste_shell(r.body_html, Path(args.md).stem, acc.name), "utf-8")
        (out_dir / "article-body.html").write_text(r.body_html, "utf-8")
        out({"ok": True, "dir": str(out_dir), "stats": r.stats,
             "validation": {"errors": len(r.validation.errors), "warnings": len(r.validation.warnings)}})

    elif cmd == "cover":
        from core.cover import render_cover
        md = Path(args.md).read_text("utf-8")
        title = md.split("\n")[0].lstrip("# ").strip() or Path(args.md).stem
        r = render_cover(title, args.platform, args.subtitle, args.column,
                         account_name=acc.name, theme_id=args.theme,
                         out_dir=str(acc.dir / "assets" / "covers"))
        out(r)

    elif cmd == "cards":
        from core.cover import render_cards
        if args.points:
            lines = Path(args.points).read_text("utf-8").strip().split("\n")
            points = [{"title": l.strip()} for l in lines if l.strip()]
        else:
            md = Path(args.md).read_text("utf-8")
            headings = [l.lstrip("# ").strip() for l in md.split("\n") if l.startswith("## ")]
            points = [{"title": h} for h in headings[:6]] or [{"title": Path(args.md).stem}]
        r = render_cards(points, args.platform, acc.name, args.theme,
                         out_dir=str(acc.dir / "assets" / "cards"))
        out(r)

    elif cmd == "send":
        from core.export import build_export
        md = Path(args.md).read_text("utf-8")
        theme_dir = Path(__file__).parent / "themes"
        r = build_export(md, args.title, args.platform, args.theme, str(theme_dir),
                         out_dir=str(Path(args.md).parent / "export"),
                         account_name=acc.name, summary_hook=args.hook, summary_full=args.summary)
        # 记录本篇供反重复检查
        if r.get("ok"):
            from core.evolve import record_article
            meta_path = Path(args.md).parent / "meta.yaml"
            dims = {}
            structure = ""
            if meta_path.is_file():
                import yaml as _y
                m = _y.safe_load(meta_path.read_text("utf-8")) or {}
                dims = m.get("dimensions", {})
                structure = m.get("structure", "")
            record_article(v, acc, args.title, structure=structure, platform=args.platform, dimensions=dims)
        out(r)


if __name__ == "__main__":
    main()