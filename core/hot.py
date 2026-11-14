"""热点抓取：Playwright 打开 tophub → 全量存 shared/raw → 按账号规则筛选。

只抓 tophub 一个站，它聚合了微博/知乎/头条/B站/百度等几十个榜单。
每个账号在 account.yaml 里配自己抓哪些榜、筛什么词、怎么打分。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
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
    "bilibili": {"id": "74KvxwokqM", "name": "B站全站榜"},
}


def fetch_raw(boards: list[dict] | None = None, timeout_ms: int = 30000) -> dict[str, Any]:
    """用 Playwright 抓 tophub，返回 {captured_at, sources, items}。

    boards: [{id, name}]，不传则用 DEFAULT_BOARDS 全部。
    需要 playwright 已安装（pip install playwright && playwright install chromium）。
    """
    if boards is None:
        boards = [{"id": v["id"], "name": v["name"]} for v in DEFAULT_BOARDS.values()]

    # 生成临时 JS 脚本让 playwright 执行
    js_code = _build_js(boards, timeout_ms)
    script_path = Path(__file__).parent / "_hot_fetch.js"
    script_path.write_text(js_code, encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "run", str(script_path)],
            capture_output=True, text=True, timeout=timeout_ms // 1000 * len(boards) + 30,
            cwd=str(Path(__file__).parent),
        )
        # playwright run 不一定可用，改用 node 直接跑
        if result.returncode != 0:
            result = subprocess.run(
                ["node", str(script_path)],
                capture_output=True, text=True, timeout=timeout_ms // 1000 * len(boards) + 30,
            )
        if result.returncode != 0:
            return {
                "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
                "sources": [{"board": b["name"], "id": b["id"], "state": "error", "count": 0,
                             "error": result.stderr[:200]} for b in boards],
                "items": [],
            }
        data = json.loads(result.stdout)
        return data
    except FileNotFoundError:
        return {
            "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "sources": [{"board": b["name"], "id": b["id"], "state": "error", "count": 0,
                         "error": "playwright/node not found"} for b in boards],
            "items": [],
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {
            "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "sources": [{"board": b["name"], "id": b["id"], "state": "timeout", "count": 0,
                         "error": str(e)[:200]} for b in boards],
            "items": [],
        }
    finally:
        try:
            script_path.unlink()
        except OSError:
            pass


def _build_js(boards: list[dict], timeout_ms: int) -> str:
    boards_json = json.dumps(boards, ensure_ascii=False)
    return f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const boards = {boards_json};
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage({{
    viewport: {{ width: 1400, height: 900 }},
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'
  }});
  const sources = [];
  const items = [];
  for (const b of boards) {{
    try {{
      await page.goto('https://tophub.today/n/' + b.id, {{ waitUntil: 'networkidle', timeout: {timeout_ms} }});
      await page.waitForTimeout(1500);
      const rows = await page.evaluate(() => {{
        const out = [];
        document.querySelectorAll('table tbody tr, .ncc-citem').forEach((el, i) => {{
          const a = el.querySelector('a');
          const tds = el.querySelectorAll('td');
          let title = '', heat = '', url = '';
          if (tds.length >= 2) {{
            title = (tds[1]?.innerText || '').trim();
            heat = (tds[2]?.innerText || '').trim();
            url = tds[1]?.querySelector('a')?.href || '';
          }} else if (a) {{
            title = a.innerText.trim();
            url = a.href;
          }}
          if (title && title.length > 2 && title.length < 100) {{
            out.push({{ title, heat, url, rank: i + 1 }});
          }}
        }});
        return out;
      }});
      sources.push({{ board: b.name, id: b.id, state: rows.length ? 'ok' : 'empty', count: rows.length }});
      for (const r of rows) {{
        items.push({{
          id: b.id + '-' + r.rank,
          title: r.title,
          url: r.url,
          board: b.name,
          board_id: b.id,
          heat: r.heat,
          rank: r.rank,
        }});
      }}
    }} catch (e) {{
      sources.push({{ board: b.name, id: b.id, state: 'error', count: 0, error: e.message.slice(0, 200) }});
    }}
  }}
  await browser.close();
  console.log(JSON.stringify({{
    captured_at: new Date().toISOString(),
    sources,
    items,
  }}));
}})();
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

    w_keyword = weights.get("keyword", 0.35)
    w_category = weights.get("category", 0.20)
    w_tag = weights.get("tag", 0.20)
    w_recency = weights.get("recency", 0.10)
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

        # 关键词匹配（字面包含 + 模糊）
        kw_matched = sum(1 for w in include if w in title)
        kw_score = min(1.0, kw_matched / max(1, min(3, len(include)))) if include else 0.5

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
    """存全量原始数据到 shared/hotspots/YYYY-MM-DD/_raw.json。"""
    day_dir = shared_dir / "hotspots" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / "_raw.json"
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