"""热点抓取：Playwright 打开 tophub → 全量存 shared/raw → 按账号规则筛选。

只抓 tophub 一个站，它聚合了微博/知乎/头条/B站/百度等几十个榜单。
每个账号在 account.yaml 里配自己抓哪些榜、筛什么词、怎么打分。
"""
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

TZ = timezone(timedelta(hours=8))

# tophub 常用榜单 ID（可在账号配置里覆盖）
DEFAULT_BOARDS = {
    "weibo": {"id": "KqndgxeLl9", "name": "微博热搜"},
    "zhihu": {"id": "mproPpoq6O", "name": "知乎热榜"},
    "baidu": {"id": "Jb0vmloB1G", "name": "百度热点"},
    "toutiao": {"id": "x9ozB4KoXb", "name": "今日头条"},
    "bilibili": {"id": "74KvxwokxM", "name": "B站全站榜"},
}


def fetch_raw(boards: list[dict] | None = None, timeout_ms: int = 30000) -> dict[str, Any]:
    """用 Python Playwright 抓 tophub，返回 {captured_at, sources, items}。

    boards: [{id, name}]，不传则用 DEFAULT_BOARDS 全部。
    需要 pip install playwright && playwright install chromium。
    纯 Python 实现：不依赖 node 模块解析路径，装在哪都能跑。
    """
    if boards is None:
        boards = [{"id": v["id"], "name": v["name"]} for v in DEFAULT_BOARDS.values()]

    captured_at = datetime.now(TZ).isoformat(timespec="seconds")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "captured_at": captured_at,
            "sources": [{"board": b["name"], "id": b["id"], "state": "error", "count": 0,
                         "error": "playwright 未安装：pip install playwright && playwright install chromium"}
                        for b in boards],
            "items": [],
        }

    sources: list[dict] = []
    items: list[dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            )
            for b in boards:
                try:
                    page.goto(f"https://tophub.today/n/{b['id']}",
                              wait_until="networkidle", timeout=timeout_ms)
                    page.wait_for_timeout(1500)
                    # 反爬验证码页识别：不是 empty，是 blocked
                    doc_title = page.title()
                    if "安全验证" in doc_title or ("验证" in doc_title and "热榜" not in doc_title):
                        sources.append({"board": b["name"], "id": b["id"], "state": "blocked",
                                        "count": 0, "error": "tophub 反爬验证码，稍后再试或降低抓取频率"})
                        continue
                    rows = page.evaluate(_ROWS_JS)
                    sources.append({"board": b["name"], "id": b["id"],
                                    "state": "ok" if rows else "empty", "count": len(rows)})
                    for r in rows:
                        items.append({
                            "id": f"{b['id']}-{r['rank']}",
                            "title": r["title"], "url": r.get("url", ""),
                            "board": b["name"], "board_id": b["id"],
                            "heat": r.get("heat", ""), "rank": r["rank"],
                        })
                except Exception as e:
                    sources.append({"board": b["name"], "id": b["id"], "state": "error",
                                    "count": 0, "error": str(e)[:200]})
                # 榜单之间停 2-4 秒，降低反爬触发概率
                page.wait_for_timeout(2000 + random.randint(0, 2000))
            browser.close()
    except Exception as e:
        # 浏览器启动失败等全局错误：所有榜单标 error，不静默
        msg = str(e)[:200]
        known = {s["id"] for s in sources}
        for b in boards:
            if b["id"] not in known:
                sources.append({"board": b["name"], "id": b["id"], "state": "error",
                                "count": 0, "error": msg})
    return {"captured_at": captured_at, "sources": sources, "items": items}


_ROWS_JS = """
() => {
  const out = [];
  document.querySelectorAll('table tbody tr, .ncc-citem').forEach((el, i) => {
    const tds = el.querySelectorAll('td');
    let title = '', heat = '', url = '';
    // 优先行内第一个链接（各榜单 td 布局不一：有的标题在 td[1]，有的在 td[2]）
    const a = el.querySelector('a');
    if (a && a.innerText.trim().length > 2) {
      title = a.innerText.trim();
      url = a.href || '';
    } else {
      for (const td of tds) {
        const t = td.innerText.trim();
        if (t.length > 4 && !/^\\d+[.、]?$/.test(t)) { title = t; break; }
      }
      url = a ? (a.href || '') : '';
    }
    // 热度：最后一个纯数字/万亿单位的 td（排除 "1." 这类序号）
    for (let j = tds.length - 1; j >= 0; j--) {
      const t = tds[j].innerText.trim();
      if (/^\\d+(\\.\\d+)?\\s*[万亿]?$/.test(t)) { heat = t; break; }
    }
    if (title && title.length > 2 && title.length < 100) {
      out.push({ title, heat, url, rank: i + 1 });
    }
  });
  return out;
}
"""


def filter_for_account(
    raw: dict[str, Any],
    account_config: dict[str, Any],
    min_fit: float | None = None,
) -> list[dict[str, Any]]:
    """按账号规则从 raw 中筛选并打分。返回带 fit 的条目列表。"""
    include = [w.lower() for w in account_config.get("topics_include", [])]
    exclude = [w.lower() for w in account_config.get("topics_exclude", [])]
    focus_cats = [c.lower() for c in account_config.get("categories_focus", [])]
    weights = account_config.get("fit_weights", {})
    threshold = min_fit if min_fit is not None else account_config.get("min_fit", 0.45)

    # tophub 原始数据没有 tags/category_hint，这两个维度默认权重为 0，
    # 把权重让给关键词和时效；账号可用 fit_weights 覆盖。
    w_keyword = weights.get("keyword", 0.60)
    w_category = weights.get("category", 0.0)
    w_tag = weights.get("tag", 0.0)
    w_recency = weights.get("recency", 0.25)
    w_column = weights.get("column", 0.15)

    columns = account_config.get("columns", [])
    col_labels = " ".join(f"{c.get('name', '')} {c.get('desc', '')}" for c in columns).lower()

    results = []
    for item in raw.get("items", []):
        title = item.get("title", "").lower()
        tags = [t.lower() for t in item.get("tags", [])]
        cat_hint = item.get("category_hint", "").lower()

        # 排除词命中 → 直接跳过
        if any(w in title for w in exclude):
            continue

        # 关键词匹配：命中 1 个给 0.7，2 个及以上满分（短标题很难命中 3 个）
        kw_matched = sum(1 for w in include if w in title)
        kw_score = min(1.0, 0.7 * kw_matched) if include else 0.5

        # 品类亲和
        cat_score = 1.0 if cat_hint and cat_hint in focus_cats else 0.0

        # 标签匹配
        tag_score = 1.0 if any(t in " ".join(include) for t in tags) else 0.0

        # 栏目相似度（简单字符重叠）
        col_score = _jaccard(title, col_labels) if col_labels else 0.0

        # 时效（rank 越靠前越新）
        rank = item.get("rank", 50)
        recency_score = max(0.0, 1.0 - rank / 50)

        fit = round(
            w_keyword * kw_score + w_category * cat_score + w_tag * tag_score
            + w_column * col_score + w_recency * recency_score,
            2,
        )

        if fit >= threshold:
            results.append({
                **item,
                "fit": fit,
                "fit_detail": {
                    "keyword": round(kw_score, 2),
                    "category": round(cat_score, 2),
                    "tag": round(tag_score, 2),
                    "column": round(col_score, 2),
                    "recency": round(recency_score, 2),
                },
            })

    results.sort(key=lambda x: -x["fit"])
    return results


def _jaccard(a: str, b: str) -> float:
    """字符 bigram Jaccard 相似度。"""
    if not a or not b:
        return 0.0
    sa = {a[i:i+2] for i in range(len(a)-1)}
    sb = {b[i:i+2] for i in range(len(b)-1)}
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def save_raw(shared_dir: Path, date: str, raw: dict[str, Any]) -> Path:
    """存全量原始数据到 shared/hotspots/YYYY-MM-DD/_raw.json。

    部分榜单失败时与已有数据合并：保住上次成功的条目，不被空结果冲掉。
    """
    day_dir = shared_dir / "hotspots" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / "_raw.json"
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            old_items = {it.get("id"): it for it in old.get("items", []) if it.get("id")}
            new_ids = {it.get("id") for it in raw.get("items", [])}
            # 本次没抓到的榜单，保留旧数据里对应条目
            ok_boards = {s.get("board") for s in raw.get("sources", []) if s.get("state") == "ok"}
            for oid, it in old_items.items():
                if oid not in new_ids and it.get("board") not in ok_boards:
                    raw.setdefault("items", []).append(it)
            # sources 合并：本次失败的榜单若旧数据有成功记录，标注 retained
            old_src = {s.get("board"): s for s in old.get("sources", [])}
            for s in raw.get("sources", []):
                if s.get("state") != "ok" and old_src.get(s.get("board"), {}).get("state") == "ok":
                    s["retained_from_previous"] = True
        except (json.JSONDecodeError, OSError):
            pass
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_raw(shared_dir: Path, date: str) -> dict[str, Any] | None:
    path = shared_dir / "hotspots" / date / "_raw.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_account_hotspots(account_dir: Path, date: str, items: list[dict]) -> list[Path]:
    """把筛选后的热点写入账号目录。"""
    from core.vault import serialize_doc, write_atomic
    paths = []
    for item in items:
        cat = item.get("category_hint", "other")
        day_dir = account_dir / "hotspots" / date[:4] / date[:7] / date / cat
        day_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r'[<>:"/\\|?*]', "", item["title"])[:50].strip(".-") or "untitled"
        path = day_dir / f"{stem}.md"
        i = 2
        while path.exists():
            path = day_dir / f"{stem}-{i}.md"
            i += 1
        meta = {
            "type": "hotspot", "v": 1,
            "title": item["title"],
            "raw_id": item.get("id", ""),
            "board": item.get("board", ""),
            "heat": item.get("heat", ""),
            "url": item.get("url", ""),
            "fit": item["fit"],
            "fit_detail": item.get("fit_detail", {}),
            "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
        }
        body = f"## 大概内容\n\n{item.get('summary', '（待补充）')}\n\n## 为什么值得写\n\n{item.get('why', '（待补充）')}\n"
        write_atomic(path, serialize_doc(meta, body))
        paths.append(path)
    return paths