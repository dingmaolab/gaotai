"""内容库读写：目录约定、markdown 前后言、原子写、账号管理。

所有内容都是纯 markdown，Obsidian / VSCode 能直接打开，也能 git 版本化。
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

TZ = timezone(timedelta(hours=8))  # Asia/Shanghai


def now() -> datetime:
    return datetime.now(TZ)


def local_date() -> str:
    return now().strftime("%Y-%m-%d")


def local_timestamp() -> str:
    return now().isoformat(timespec="seconds")


def write_atomic(path: Path, text: str) -> None:
    """先写临时文件再改名，避免中途崩溃留下半个文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


FRONT_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def parse_doc(text: str) -> tuple[dict[str, Any], str]:
    """拆出 YAML 前后言和正文。没有前后言时 meta 为空。"""
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2)


def serialize_doc(meta: dict[str, Any], body: str) -> str:
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000).rstrip("\n")
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_title(title: str, limit: int = 60) -> str:
    """去掉文件名非法字符，压缩空白。中文保留。"""
    t = _BAD_CHARS.sub("", title).strip()
    t = re.sub(r"\s+", "-", t)
    t = t.strip(".-")
    return t[:limit] or "untitled"


@dataclass
class Account:
    id: str
    name: str
    data: dict[str, Any]
    dir: Path


class Vault:
    """内容库。所有路径都在 root 之下。"""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    # ---------- 基础 ----------

    def exists(self) -> bool:
        return (self.root / "vault.yaml").exists() or (self.root / ".gaotai" / "account.yaml").is_file()

    @property
    def config(self) -> dict[str, Any]:
        try:
            return yaml.safe_load((self.root / "vault.yaml").read_text(encoding="utf-8")) or {}
        except FileNotFoundError:
            return {}

    def account_path(self, acc: Account, *parts: str) -> Path:
        return acc.dir.joinpath(*parts)

    # ---------- 账号 ----------

    def accounts(self) -> list[Account]:
        # 单账号模式：root 本身就是账号目录（一个账号一个目录）
        f = self.root / ".gaotai" / "account.yaml"
        if not f.is_file():
            f = self.root / "account.yaml"
        if f.is_file():
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                data = {}
            return [Account(id=str(data.get("id") or self.root.name),
                            name=str(data.get("name") or self.root.name), data=data, dir=self.root)]
        adir = self.root / "accounts"
        if not adir.is_dir():
            return []
        out: list[Account] = []
        for d in sorted(adir.iterdir()):
            # 优先 .gaotai/account.yaml，兼容旧版 account.yaml
            f = d / ".gaotai" / "account.yaml"
            if not f.is_file():
                f = d / "account.yaml"
            if not f.is_file():
                continue
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            out.append(Account(id=d.name, name=str(data.get("name") or d.name), data=data, dir=d))
        return out

    def resolve_account(self, ident: str | None = None) -> Account:
        accs = self.accounts()
        if not accs:
            raise VaultError("NO_ACCOUNT", "内容库里还没有账号", "先运行 init 建库并建第一个账号")
        if not ident:
            return accs[0]
        for a in accs:
            if a.id == ident:
                return a
        # 允许用中文名匹配
        for a in accs:
            if a.name == ident:
                return a
        raise VaultError("ACCOUNT_NOT_FOUND", f"找不到账号：{ident}", f"现有账号：{', '.join(a.id for a in accs)}")

    def create_account(
        self,
        account_id: str,
        name: str,
        positioning: str = "",
        audience: str = "",
        tone_hint: str = "",
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", account_id):
            raise VaultError("BAD_ACCOUNT_ID", "账号 id 只能用小写字母、数字、连字符，2-41 位", "例如 lingqilulu")
        adir = self.root / "accounts" / account_id
        return self.create_account_at(adir, account_id, name, positioning, audience, tone_hint)

    def create_account_at(
        self,
        adir: Path,
        account_id: str,
        name: str,
        positioning: str = "",
        audience: str = "",
        tone_hint: str = "",
    ) -> dict[str, Any]:
        """在指定目录建账号骨架。单账号模式下 adir 就是内容库根。"""
        gaotai_dir = adir / ".gaotai"
        f = gaotai_dir / "account.yaml"
        if f.exists():
            raise VaultError("ACCOUNT_EXISTS", f"账号已存在：{account_id}", "换一个 id，或直接编辑 .gaotai/account.yaml")
        data = {
            "id": account_id,
            "name": name,
            "positioning": positioning,
            "audience": audience,
            "topics_include": [],
            "topics_exclude": [],
            "categories_focus": [],
            "columns": [],
            "hotspot_policy": "fast",
            "tone_hint": tone_hint or "躬身实践、坦诚讲卡点、不吹不黑；慢一点，但想清楚",
        }
        write_atomic(f, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000))

        # 子目录 + .gitkeep（保持空目录可被 git 追踪）
        subdirs = [
            "ideas", "projects", "hotspots",
            "style/exemplars", "style/references", "style/lessons", "style/diffs",
            "assets/covers", "assets/cards",
        ]
        for sub in subdirs:
            d = adir / sub
            d.mkdir(parents=True, exist_ok=True)
            keep = d / ".gitkeep"
            if not keep.exists():
                keep.write_text("", encoding="utf-8")

        # state.yaml — Agent 每次会话开始读的当前状态摘要
        state = {
            "account_id": account_id,
            "name": name,
            "confidence": "none",
            "sample_count": 0,
            "recent_articles": 0,
            "total_ideas": 0,
            "total_projects": 0,
            "updated_at": local_timestamp(),
        }
        write_atomic(gaotai_dir / "state.yaml", yaml.safe_dump(state, allow_unicode=True, sort_keys=False))

        # AGENTS.md — 账号级 Agent 入口（渐进式加载指引）
        agents_md = _account_agents_md(name, positioning, audience)
        write_atomic(adir / "AGENTS.md", agents_md)

        # CLAUDE.md — 引用 AGENTS.md
        write_atomic(adir / "CLAUDE.md", "@AGENTS.md\n")

        # .gitignore
        gitignore = "__pycache__/\n*.pyc\n.DS_Store\nThumbs.db\n*.log\npreview/\nexport/\n"
        write_atomic(adir / ".gitignore", gitignore)

        # README.md — 给人看
        readme = (
            f"# {name}\n\n"
            "稿台账号目录。\n\n"
            "- 配置：`.gaotai/account.yaml`\n"
            "- 风格：`style/dna.md`\n"
            "- 灵感：`ideas/`\n"
            "- 稿子：`projects/`\n\n"
            "在对话里说「记一下」「写一篇」「审一下」即可。\n"
        )
        write_atomic(adir / "README.md", readme)

        try:
            rel = str(adir.relative_to(self.root)).replace(chr(92), "/")
        except ValueError:
            rel = "."
        return {"id": account_id, "dir": rel}

    # ---------- 灵感 / 热点 ----------

    def create_note(
        self,
        kind: str,           # idea | hotspot
        title: str,
        meta: dict[str, Any],
        body: str,
        account: Account | None = None,
        date: str | None = None,
    ) -> Path:
        date = date or local_date()
        y, ym, ymd = date[:4], date[:7], date
        category = str(meta.get("category") or "other")
        if kind == "idea":
            if account is None:
                raise VaultError("NEED_ACCOUNT", "灵感必须归属一个账号")
            base = account.dir / "ideas" / y / ym / ymd / category
        else:
            base = self.root / "hotspots" / y / ym / ymd / category
        base.mkdir(parents=True, exist_ok=True)
        stem = sanitize_title(title)
        target = base / f"{stem}.md"
        i = 2
        while target.exists():
            target = base / f"{stem}-{i}.md"
            i += 1
        doc = serialize_doc({"type": kind, "v": 1, "title": title, **meta}, body)
        write_atomic(target, doc)
        return target

    def list_notes(self, kind: str, account: Account | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if kind == "idea":
            if account is None:
                return []
            base = account.dir / "ideas"
        else:
            base = self.root / "hotspots"
        if not base.is_dir():
            return []
        files = sorted(base.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: list[dict[str, Any]] = []
        for f in files[:limit]:
            try:
                meta, body = parse_doc(f.read_text(encoding="utf-8"))
            except OSError:
                continue
            if meta.get("type") != kind:
                continue
            out.append({
                "path": str(f.relative_to(self.root)).replace("\\", "/"),
                "meta": meta,
                "body": body,
            })
        return out



def _account_agents_md(name: str, positioning: str, audience: str) -> str:
    """生成账号级 AGENTS.md，指导 Agent 渐进式加载上下文。"""
    pos = positioning or "（待填写）"
    aud = audience or "（待填写）"
    return f"""# {name} · Agent 指引

## 你是谁

你在为「{name}」工作。
- 定位：{pos}
- 读者：{aud}

## 会话开始时

1. 读  了解当前状态（置信度、最近文章数、灵感数）
2. 根据用户意图决定下一步，**不要一次读完所有文件**

## 按需加载

| 你要做什么 | 读什么 | 不读什么 |
|---|---|---|
| 记灵感 | 无需读文件，直接 note | 其他一切 |
| 抓热点 |  的过滤规则 | style/ |
| 写稿 |  +  | exemplars/, lessons/ |
| 审稿 |  | dna.md, exemplars/ |
| 学风格 |  或  | projects/ |
| 反重复 |  | 其他 style/ |
| 导出 | 无需额外读 | style/ |
| 参考对比 |  | exemplars/ |

## 纪律

1. 不编造：没来源的数字不写，没核实的事实不写成肯定句
2. 不越权：风格硬规则必须用户确认；不自动发布
3. 不啰嗦：记灵感就是一个命令
4. 材料决定能说到哪：材料不足就收窄判断
5. 编辑不改事实强度
6. 作者仍是说话的人：不因命中词库删除个人表达

## 文件地图


"""


class VaultError(Exception):
    def __init__(self, code: str, message: str, next_action: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.next_action = next_action


def find_account_root(start: Path | None = None) -> Path | None:
    """从 start 向上找账号目录（含 .gaotai/account.yaml，兼容旧版 account.yaml）。

    一个账号一个目录：cd 进账号目录（或其子目录）就是给这个号干活。
    """
    p = (start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / ".gaotai" / "account.yaml").is_file() or (d / "account.yaml").is_file():
            return d
    return None


def resolve_vault(cli_vault: str | None = None, cwd: Path | None = None) -> Path:
    """内容库位置：--vault > GAOTAI_VAULT > 当前账号目录 > ./GaotaiVault > ~/GaotaiVault"""
    if cli_vault:
        return Path(cli_vault).resolve()
    env = os.environ.get("GAOTAI_VAULT")
    if env:
        return Path(env).resolve()
    acc_root = find_account_root(cwd)
    if acc_root:
        return acc_root
    here = (cwd or Path.cwd()) / "GaotaiVault"
    if here.exists():
        return here.resolve()
    return Path.home() / "GaotaiVault"


def init_vault(root: Path, account_id: str, name: str, **kw) -> dict[str, Any]:
    """建账号；重复执行不会覆盖已有文件。

    两种布局：
    - root 已是内容库（有 vault.yaml/accounts/）→ 传统多账号布局，账号建在 accounts/<id>/
    - 否则 → 一个账号一个目录：root 本身就是账号目录
    """
    root.mkdir(parents=True, exist_ok=True)
    legacy = (root / "vault.yaml").exists() or (root / "accounts").is_dir()
    if legacy:
        for d in ("accounts", "hotspots", "assets"):
            (root / d).mkdir(exist_ok=True)
        vy = root / "vault.yaml"
        vault_created = False
        if not vy.exists():
            vault_created = True
            write_atomic(vy, yaml.safe_dump({
                "schema_version": 1,
                "name": "稿台内容库",
                "timezone": "Asia/Shanghai",
                "categories": [
                    {"id": "ai-tech", "name": "AI 与科技"},
                    {"id": "emotion-society", "name": "情感与社会"},
                    {"id": "workplace", "name": "职场与成长"},
                    {"id": "lifestyle", "name": "生活方式"},
                    {"id": "money", "name": "财经与商业"},
                    {"id": "opinion", "name": "观点与评论"},
                    {"id": "other", "name": "其他"},
                ],
                "hotspot": {"daily_times": ["08:30", "12:30", "20:30"], "window_days": 7, "min_fit": 0.45},
            }, allow_unicode=True, sort_keys=False, width=1000))
        v = Vault(root)
        existing = {a.id for a in v.accounts()}
        acc = None
        if account_id not in existing:
            acc = v.create_account(account_id, name, kw.get("positioning", ""), kw.get("audience", ""), kw.get("tone_hint", ""))
        return {"vault": str(root), "vault_created": vault_created, "account_created": acc is not None, "account": acc}

    # 单账号模式：当前目录就是账号目录
    v = Vault(root.parent)
    gaotai_dir = root / ".gaotai"
    if (gaotai_dir / "account.yaml").exists():
        return {"vault": str(root), "vault_created": False, "account_created": False,
                "account": {"id": account_id, "dir": "."}}
    acc = v.create_account_at(root, account_id, name, kw.get("positioning", ""), kw.get("audience", ""), kw.get("tone_hint", ""))
    return {"vault": str(root), "vault_created": True, "account_created": True, "account": acc}