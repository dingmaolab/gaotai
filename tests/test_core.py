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
    print("OK export")


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

if __name__ == "__main__":
    tests = [
        test_vault_init, test_note, test_check_hard_blockers, test_check_soft_not_blocking,
        test_tone, test_style_learn_own, test_style_learn_ref, test_format, test_export,
        test_dimensions_yaml, test_structures_yaml, test_evolve,
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