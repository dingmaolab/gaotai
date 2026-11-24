"""稿台核心测试。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vault import Vault, init_vault, parse_doc
from core.check import check
from core.tone import analyze, compare
from core.style import learn_from_own, learn_from_reference, get_profile
from core.format import format_article
from core.export import build_export


def test_vault_init():
    with tempfile.TemporaryDirectory() as d:
        r = init_vault(Path(d), "test-acc", "测试号", positioning="测试定位")
        assert r["vault_created"]
        assert r["account_created"]
        v = Vault(d)
        assert v.exists()
        accs = v.accounts()
        assert len(accs) == 1
        assert accs[0].name == "测试号"
        r2 = init_vault(Path(d), "test-acc", "测试号")
        assert not r2["account_created"]
    print("OK vault init")


def test_note():
    with tempfile.TemporaryDirectory() as d:
        init_vault(Path(d), "test-note", "T")
        v = Vault(d)
        acc = v.resolve_account()
        p = v.create_note("idea", "测试灵感", {"category": "other"}, "## 原始想法\n\n测试灵感\n", account=acc)
        assert p.is_file()
        meta, body = parse_doc(p.read_text("utf-8"))
        assert meta["type"] == "idea"
        assert "测试灵感" in body
    print("OK note")


def test_check_hard_blockers():
    md = "# 标题\n\n这是全网最好的产品，100%有效。我亲眼见证了奇迹。\n"
    r = check(md, {"source": "opinion", "format": "longform"})
    assert r["counts"]["blocker"] > 0, f"should have blockers: {r}"
    ids = [b["id"] for b in r["blockers"]]
    assert "ad-law" in ids
    print("OK check hard blockers")


def test_check_adlaw_ordinal():
    """「第一」的序数用法不是广告法违规；绝对化宣称仍要拦。"""
    ok_md = "# 记录\n\n这是装完之后的第一次真实使用。第一步就错了。第一天修了八个 bug。\n"
    r = check(ok_md, {"source": "self", "format": "longform"})
    ad = [b for b in r["blockers"] if b["id"] == "ad-law"]
    assert not ad, f"序数用法不应拦截: {ad}"
    bad_md = "# 宣传\n\n我们是行业第一的选择，销量第一。\n"
    r2 = check(bad_md, {"source": "opinion", "format": "longform"})
    ad2 = [b for b in r2["blockers"] if b["id"] == "ad-law"]
    assert ad2, "绝对化宣称应拦截"
    print("OK check ad-law ordinal exemption")


def test_check_soft_not_blocking():
    md = "# 感悟\n\n今天天气很好。我出去走了走。感觉不错。\n"
    r = check(md, {"source": "self", "format": "longform", "audience": "self"})
    assert r["counts"]["blocker"] == 0, f"self source should not block: {r['blockers']}"
    print("OK check soft not blocking for self")


def test_tone():
    bad = "在这个信息爆炸的时代，值得注意的是，这不仅是一次升级，更是一次革命。总而言之，希望对你有帮助。"
    good = "这次升级改了三处。加载更快了。权限收紧了。导出格式换了。"
    b = analyze(bad)
    a = analyze(good)
    assert b["scores"]["overall"] < a["scores"]["overall"]
    c = compare(b, a)
    assert c["delta"]["overall"] > 0
    print("OK tone")


def test_style_learn_own():
    with tempfile.TemporaryDirectory() as d:
        init_vault(Path(d), "test-own", "T")
        v = Vault(d)
        acc = v.resolve_account()
        f = Path(d) / "sample.md"
        f.write_text("---\ntitle: 测试\n---\n\n我今天试了一个工具。它很快。但是有个坑。我花了三小时才搞定。\n", "utf-8")
        r = learn_from_own(v, acc, [f])
        assert r["ok"]
        assert r["sample_count"] == 1
        assert r["confidence"] == "low"
        prof = get_profile(v, acc)
        assert prof["confidence"] == "low"
    print("OK style learn own")


def test_style_learn_ref():
    with tempfile.TemporaryDirectory() as d:
        init_vault(Path(d), "test-ref", "T")
        v = Vault(d)
        acc = v.resolve_account()
        r = learn_from_reference(v, acc, "这是别人的文章内容", author="某人", title="某文")
        assert r["ok"]
        assert r["allowed_uses"] == ["structure", "data_discipline"]
        prof = get_profile(v, acc)
        assert prof.get("sample_count", 0) == 0
    print("OK style learn reference (DNA untouched)")


def test_format():
    md = "## 一、测试\n\n这是一段话。**加粗**和*斜体*。\n\n- 列表一\n- 列表二\n"
    r = format_article(md, "minimal")
    assert 'leaf=""' in r.body_html
    assert "<div" not in r.body_html
    assert "<style" not in r.body_html
    assert len(r.validation.errors) == 0, f"errors: {r.validation.errors}"
    print("OK format")


def test_export():
    with tempfile.TemporaryDirectory() as d:
        md = "## 测试\n\n内容。\n"
        r = build_export(md, "测试标题", out_dir=d)
        assert r["ok"]
        assert (Path(d) / "wechat" / "paste.html").is_file()
        assert (Path(d) / "export.zip").is_file()
        # 回归：zip 必须可被标准工具解析（曾因中央目录漏写文件名导致坏包）
        import zipfile
        with zipfile.ZipFile(Path(d) / "export.zip") as z:
            assert z.testzip() is None
            names = z.namelist()
            assert "wechat/paste.html" in names, names
            for n in names:
                assert z.read(n) == (Path(d) / n).read_bytes()
    print("OK export (zip verified)")


def test_dimensions_yaml():
    import yaml
    p = Path(__file__).parent.parent / "core" / "dimensions.yaml"
    rules = yaml.safe_load(p.read_text("utf-8"))
    assert "source" in rules
    assert "urgency" in rules
    assert "intent" in rules
    assert "format" in rules
    assert "hard_blockers" in rules
    for k, v in rules["intent"].items():
        assert "structures" in v, f"intent {k} missing structures"
    print("OK dimensions.yaml valid")


def test_structures_yaml():
    import yaml
    p = Path(__file__).parent.parent / "core" / "structures.yaml"
    structs = yaml.safe_load(p.read_text("utf-8"))
    assert len(structs) >= 14
    for k, v in structs.items():
        assert "beats" in v, f"structure {k} missing beats"
        assert "suits" in v, f"structure {k} missing suits"
    print("OK structures.yaml valid")




def test_evolve():
    from core.evolve import record_article, check_repetition, get_story_bank, add_story, propose_dna_update
    with tempfile.TemporaryDirectory() as d:
        init_vault(Path(d), "test-evolve", "T")
        v = Vault(d)
        acc = v.resolve_account()
        record_article(v, acc, "第一篇", structure="timeline", golden_phrases=["金句A"])
        record_article(v, acc, "第二篇", structure="timeline", golden_phrases=["金句B"])
        rep = check_repetition(v, acc, "timeline", golden_phrases=["金句A"])
        assert len(rep["warnings"]) >= 1
        bank = get_story_bank(v, acc)
        assert "stories" in bank
        r = add_story(v, acc, "stories", {"scene": "测试", "detail": "细节", "feeling": "感受"})
        assert r["ok"]
        props = propose_dna_update(v, acc, [{"type": "avoid", "content": "赋能", "source": "user_feedback"}])
        assert props["needs_confirmation"]
        assert props["proposals"][0]["status"] == "tentative"
    print("OK evolve (recent + story-bank + anti-drift)")


def test_hot_filter_scoring():
    """筛选打分：tophub 无 tags/category 时，关键词命中应能过阈值。"""
    from core.hot import filter_for_account
    raw = {"items": [
        {"id": "a-1", "title": "马斯克回应SpaceX筷子夹飞船", "board": "微博热搜", "rank": 1},
        {"id": "a-2", "title": "DeepSeek发布新模型API价格引热议", "board": "知乎热榜", "rank": 5},
        {"id": "a-3", "title": "某明星八卦恋情曝光", "board": "微博热搜", "rank": 2},
        {"id": "a-4", "title": "纯融资新闻：某公司获A轮", "board": "头条", "rank": 3},
    ]}
    cfg = {
        "topics_include": ["AI", "大模型", "模型", "DeepSeek", "马斯克", "SpaceX"],
        "topics_exclude": ["明星八卦", "纯融资新闻"],
        "categories_focus": ["ai-tech"],
        "columns": [{"name": "躬身试新", "desc": "亲手把新工具用一遍"}],
    }
    r = filter_for_account(raw, cfg)
    titles = [x["title"] for x in r]
    assert any("马斯克" in t for t in titles), f"单词命中应过阈值: {titles}"
    assert any("DeepSeek" in t for t in titles), f"双词命中应高分: {titles}"
    assert not any("八卦" in t for t in titles), "排除词应生效"
    assert not any("融资" in t for t in titles), "排除词应生效"
    assert r[0]["fit"] >= r[-1]["fit"], "应按 fit 降序"
    print("OK hot filter scoring")


def test_hot_rows_js():
    """离线验证 _ROWS_JS 两种表格布局（需 playwright，缺失则跳过）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP hot rows js (playwright not installed)")
        return
    import tempfile
    from core.hot import _ROWS_JS
    html = """<html><body>
<table><tbody>
<tr><td>1.</td><td><a href="https://weibo.com/1">微博标题甲</a></td><td>1234万</td><td>热</td></tr>
</tbody></table>
<table><tbody>
<tr><td>1.</td><td></td><td><a href="https://www.zhihu.com/question/1">知乎标题乙在第三列</a></td><td>x</td></tr>
</tbody></table>
</body></html>"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        p = Path(f.name)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            page = b.new_page()
            page.goto(p.as_uri())
            rows = page.evaluate(_ROWS_JS)
            b.close()
    finally:
        p.unlink()
    assert len(rows) == 2, f"expect 2 rows, got {len(rows)}"
    assert rows[0]["title"] == "微博标题甲" and rows[0]["heat"] == "1234万"
    assert rows[1]["title"] == "知乎标题乙在第三列", "知乎布局（标题在 td[2]）提取失败"
    assert rows[1]["heat"] == "", "序号列不应误判为热度"
    print("OK hot rows js (both layouts)")

def test_check_tool_course():
    """工具课模式：超红线与 0图0表出 warn；不带旗标不受扰；方法论课降级 info。"""
    ok_md = ("# 课\n\n## ① 装\n\n跑一行命令就好。\n\n"
             "| 步骤 | 命令 |\n|---|---|\n| 1 | x |\n\n"
             "![示意](a.png)\n\n## 跟做步骤\n\n1. 做\n")
    r = check(ok_md, {"tool_course": "true"})
    assert not [w for w in r["warnings"] if w["id"].startswith("tool")], r["warnings"]

    fat = "# 课\n\n## ① 装\n\n" + "这是一句用来撑字数的讲解。" * 400 + "\n\n## 跟做步骤\n\n1. 做\n"
    r2 = check(fat, {"tool_course": "true"})
    assert "tool-body-long" in [w["id"] for w in r2["warnings"]]
    assert "tool-no-visual" in [w["id"] for w in r2["warnings"]]

    r3 = check(fat, {})
    assert not [w for w in r3["warnings"] if w["id"].startswith("tool")], "无旗标不扰"

    meth = "# 课\n\n## 一、道理\n\n" + "这是方法论的一长段。" * 400 + "\n\n## 跟做步骤\n\n1. 做\n"
    r4 = check(meth, {"tool_course": "true"})
    assert not [w for w in r4["warnings"] if w["id"] == "tool-body-long"]
    assert any(i["id"] == "tool-no-beats" for i in r4["infos"]), "定位不到→info 不硬拦"
    print("OK check tool-course mode")


if __name__ == "__main__":
    tests = [
        test_vault_init, test_note, test_check_hard_blockers, test_check_adlaw_ordinal,
        test_check_soft_not_blocking, test_check_tool_course,
        test_tone, test_style_learn_own, test_style_learn_ref, test_format, test_export,
        test_dimensions_yaml, test_structures_yaml, test_evolve,
        test_hot_filter_scoring, test_hot_rows_js,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
