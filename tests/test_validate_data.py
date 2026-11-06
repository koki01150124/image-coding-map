"""tools/validate_data.py と tools/build_graph.py のテスト．"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_graph  # noqa: E402
import validate_data  # noqa: E402
from common import DATA, load_library, load_node_files, load_vocab, read_json  # noqa: E402


@pytest.fixture(scope="module")
def base():
    """実データ（ノード，語彙，スキーマ，ライブラリ）を読み込む．

    Returns:
        dict: {"nodes": list[tuple[Path, dict]], "vocab": dict, "schema": dict, "library": dict}
    """
    return {"nodes": load_node_files(), "vocab": load_vocab(), "schema": read_json(DATA / "schema" / "node.schema.json"),
            "library": load_library()}


def run(base, nodes):
    """差し替えたノードで検証を実行する．

    Args:
        base (dict): fixture の値．
        nodes (list[tuple[Path, dict]]): ノード．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    return validate_data.validate(nodes, base["vocab"], base["schema"], base["library"])


def modified(base, node_id, fn):
    """1件のノードを変更した複製を作る．

    Args:
        base (dict): fixture の値．
        node_id (str): 変更するノードID．
        fn (callable): ノードの辞書を受け取り変更する関数．
    Returns:
        list[tuple[Path, dict]]: 変更後のノード．
    """
    nodes = copy.deepcopy(base["nodes"])
    for _, n in nodes:
        if n["id"] == node_id:
            fn(n)
    return nodes


def test_real_data_is_valid(base):
    """実データにエラーが無い．"""
    errors, _ = run(base, base["nodes"])
    assert errors == []


def test_schema_violation(base):
    """必須キーの欠落をスキーマ違反として検出する．"""
    errors, _ = run(base, modified(base, "necst", lambda n: n.pop("training")))
    assert any("スキーマ違反" in e and "training" in e for e in errors)


def test_duplicate_id(base):
    """重複 ID を検出する．"""
    nodes = copy.deepcopy(base["nodes"])
    path, node = nodes[0]
    nodes.append((path.with_name("copy.json"), copy.deepcopy(node)))
    errors, _ = run(base, nodes)
    assert any("重複" in e for e in errors)


def test_missing_reference(base):
    """存在しない参照先を検出する．"""
    rel = {"target": "no_such_node", "type": "related", "note": "x", "evidence": {"kind": "abstract", "detail": "x"}}
    errors, _ = run(base, modified(base, "necst", lambda n: n["relations"].append(rel)))
    assert any("no_such_node" in e for e in errors)


def test_unknown_edge_type(base):
    """未定義のエッジ種別を検出する．"""
    rel = {"target": "deepjscc", "type": "inspired_by", "note": "x", "evidence": {"kind": "abstract", "detail": "x"}}
    errors, _ = run(base, modified(base, "necst", lambda n: n["relations"].append(rel)))
    assert any("inspired_by" in e for e in errors)


def test_self_reference(base):
    """自己参照を検出する．"""
    rel = {"target": "necst", "type": "related", "note": "x", "evidence": {"kind": "abstract", "detail": "x"}}
    errors, _ = run(base, modified(base, "necst", lambda n: n["relations"].append(rel)))
    assert any("自己参照" in e for e in errors)


def test_lineage_cycle(base):
    """系譜関係の循環（DDCM → Turbo-DDCM → DDCM）を検出する．"""
    rel = {"target": "turbo_ddcm", "type": "derived_from", "note": "x", "evidence": {"kind": "abstract", "detail": "x"}}
    errors, _ = run(base, modified(base, "ddcm", lambda n: n["relations"].append(rel)))
    assert any("循環" in e for e in errors)


def test_compared_with_cycle_is_allowed(base):
    """比較対象の関係は系譜ではないため，循環しても許容する．"""
    rel = {"target": "robust_turbo_ddcm", "type": "compared_with", "note": "x", "evidence": {"kind": "abstract", "detail": "x"}}
    errors, _ = run(base, modified(base, "ddcm", lambda n: n["relations"].append(rel)))
    assert not any("循環" in e for e in errors)


def test_bibliography_mismatch(base):
    """survey/library.json と異なる書誌情報を検出する．"""
    errors, _ = run(base, modified(base, "necst", lambda n: n["bibliography"].update(title="捏造したタイトル")))
    assert any("一致しない" in e for e in errors)


def test_year_must_be_first_public(base):
    """年代軸の年が初出年と異なる場合を検出する（NECST を正式掲載年 2019 にした場合）．"""
    errors, _ = run(base, modified(base, "necst", lambda n: n.update(year=2019)))
    assert any("初出年" in e for e in errors)


def test_first_public_after_arxiv(base):
    """初出年が arXiv 初版の年より後である場合を検出する．"""
    def f(n):
        n["publication"]["first_public"] = {"venue": "ICML", "year": 2019, "evidence": "x"}
        n["year"] = 2019
    errors, _ = run(base, modified(base, "necst", f))
    assert any("arXiv 初版" in e for e in errors)


def test_formal_before_first_public(base):
    """正式掲載年が初出年より前である場合を検出する．"""
    errors, _ = run(base, modified(base, "necst", lambda n: n["publication"]["formal"].update(year=2010)))
    assert any("正式掲載年" in e for e in errors)


def test_unpublished_must_not_have_publication(base):
    """未公開研究に初出・正式掲載を書いた場合を検出する．"""
    def f(n):
        n["publication"]["first_public"] = {"venue": "arXiv", "year": 2026, "evidence": "x"}
    errors, _ = run(base, modified(base, "bfr_cae", f))
    assert any("初出・正式掲載を持たない" in e for e in errors)


def test_scheme_year_follows_first_use(base):
    """構成例の年が，比較対象として用いた論文の最小の年と異なる場合を検出する．"""
    errors, _ = run(base, modified(base, "sscc_bpg_ldpc", lambda n: n.update(year=2023)))
    assert any("構成例の year" in e for e in errors)


def test_duplicate_preprint_and_formal(base):
    """プレプリントと正式掲載版を別ノードにした場合（同じ arXiv ID）を検出する．"""
    nodes = copy.deepcopy(base["nodes"])
    path, node = next((p, n) for p, n in nodes if n["id"] == "necst")
    dup = copy.deepcopy(node)
    dup.update(id="necst_icml", bib_key=None, kind="unpublished")
    nodes.append((path.with_name("necst_icml.json"), dup))
    errors, _ = run(base, nodes)
    assert any("重複" in e and "arXiv" in e for e in errors)


def test_lineage_target_newer_is_error(base):
    """系譜の元（派生元）が派生先より新しい場合を検出する．"""
    rel = {"target": "robust_turbo_ddcm", "type": "builds_on", "note": "x", "evidence": {"kind": "abstract", "detail": "x"}}
    errors, _ = run(base, modified(base, "necst", lambda n: n["relations"].append(rel)))
    assert any("方が新しい" in e for e in errors)


def test_rule_generative_not_jscc(base):
    """通信路を含む共同学習を行わない Robust Turbo-DDCM を DeepJSCC に分類した場合を検出する．"""
    errors, _ = run(base, modified(base, "robust_turbo_ddcm", lambda n: n["domains"].append("digital_jscc")))
    assert any("jscc_requires_joint_training" in e for e in errors)


def test_rule_analog_digital(base):
    """アナログ型 DeepJSCC にデジタルの区分を付けた場合を検出する．"""
    errors, _ = run(base, modified(base, "deepjscc", lambda n: n.update(transmission="digital")))
    assert any("analog_jscc_is_analog" in e for e in errors)


def test_rule_shannon_not_sscc(base):
    """情報理論の基礎研究（Shannon 1948）を SSCC に分類した場合を検出する．"""
    errors, _ = run(base, modified(base, "shannon1948", lambda n: n["domains"].append("sscc")))
    assert any("sscc_needs_concrete_scheme" in e for e in errors)


def test_rule_scheme_primary_sscc(base):
    """構成例の主分野が SSCC でない場合を検出する．"""
    errors, _ = run(base, modified(base, "sscc_jpeg_ldpc", lambda n: n.update(domains=["traditional", "sscc"])))
    assert any("scheme_is_sscc" in e for e in errors)


def test_no_old_project_name():
    """旧名称（image-compression-map／Image Compression Map）に依存するファイルが残っていない（作業履歴を除く）．"""
    skip = {".git", ".ai", ".orders", ".reports", ".logs", ".venv_tools", "__pycache__", ".pytest_cache", "vendor", "survey"}
    hits = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or set(p.relative_to(ROOT).parts) & skip or p.suffix in {".png", ".pdf"}:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "image-compression-map" in text or "Image Compression Map" in text:
            hits.append(str(p.relative_to(ROOT)))
    assert hits == [str(Path(__file__).relative_to(ROOT))]


def test_paper_requires_bib_key(base):
    """論文（kind=paper）に bib_key が無い場合を検出する．"""
    errors, _ = run(base, modified(base, "necst", lambda n: n.update(bib_key=None)))
    assert any("bib_key" in e for e in errors)


def test_build_graph_edges(base):
    """graph.json のエッジが全ノードの relations と一致し，参照先が全て存在する．"""
    nodes = [n for _, n in base["nodes"]]
    graph = build_graph.build_graph(nodes, base["vocab"])
    ids = {n["id"] for n in graph["nodes"]}
    assert len(graph["edges"]) == sum(len(n["relations"]) for n in nodes)
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])


def test_academic_constraints(base):
    """order の学術的な注意点がデータに反映されている．"""
    by_id = {n["id"]: n for _, n in base["nodes"]}
    # JPEG は画像圧縮，LDPC は通信路符号，JPEG＋LDPC は SSCC
    assert by_id["jpeg"]["domains"][0] == "traditional"
    assert by_id["gallager_ldpc"]["domains"][0] == "channel_coding"
    assert by_id["sscc_jpeg_ldpc"]["domains"][0] == "sscc"
    # 生成・拡散型を DeepJSCC の配下に置かない
    for nid in ("ddcm", "turbo_ddcm", "robust_turbo_ddcm"):
        assert not {"analog_jscc", "digital_jscc"} & set(by_id[nid]["domains"])
    # Robust Turbo-DDCM と BFR-CAE は共通課題（related）のみで，派生関係ではない
    rels = [(r["target"], r["type"]) for r in by_id["bfr_cae"]["relations"]] + \
           [(r["target"], r["type"]) for r in by_id["robust_turbo_ddcm"]["relations"]]
    assert ("robust_turbo_ddcm", "related") in rels
    assert not any(t in ("bfr_cae", "robust_turbo_ddcm") and k in ("derived_from", "builds_on") for t, k in rels)
    # BFR-CAE はデジタル型 DeepJSCC（BSC を含む共同学習），アナログとデジタルを区別する
    assert by_id["bfr_cae"]["domains"][0] == "digital_jscc" and "BSC" in by_id["bfr_cae"]["channel_models"]
    assert by_id["deepjscc"]["transmission"] == "analog" and by_id["necst"]["transmission"] == "digital"
    # LIC と DeepJSCC は排他的ではない（両方に属する論文がある）
    assert any({"lic", "analog_jscc"} <= set(n["domains"]) for n in by_id.values())
    # Shannon 1948 は情報理論の基礎研究であり，SSCC の実装方式と混同しない
    assert by_id["shannon1948"]["domains"] == ["channel_coding"]
    assert not any(r["target"] == "shannon1948" for n in by_id.values() if n["kind"] == "scheme" for r in n["relations"])
    # 構成例と個別の論文を区別する
    assert all(n["bib_key"] is None for n in by_id.values() if n["kind"] == "scheme")
    # 未公開研究は発表年を持たない
    assert by_id["bfr_cae"]["year_basis"] == "unpublished_placement" and by_id["bfr_cae"]["publication"]["first_public"] is None


def test_assets_are_stamped():
    """index.html と app.js の JS・CSS の参照に，現在の内容のハッシュが付いている（古いファイルのキャッシュ対策）．"""
    import stamp_assets
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    for name in ("app.js", "style.css"):
        assert f'assets/{name}?v={stamp_assets.short_hash(ROOT / "site" / "assets" / name)}"' in html
    for name in ("layout.js", "patterns.js"):
        assert f'"./{name}?v={stamp_assets.short_hash(ROOT / "site" / "assets" / name)}"' in app
