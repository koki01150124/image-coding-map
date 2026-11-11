"""研究分野樹形図の分類体系（data/research_taxonomy.json）と，ノードの research_fields のテスト．"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from common import load_node_files, load_vocab  # noqa: E402
from taxonomy import ancestors, index, members, membership_errors, taxonomy_errors  # noqa: E402


@pytest.fixture(scope="module")
def base():
    """実データを読み込む．

    Returns:
        dict: {"nodes": list[tuple[Path, dict]], "tax": dict, "domains": set[str]}
    """
    v = load_vocab()
    return {"nodes": load_node_files(), "tax": v["taxonomy"], "domains": {d["id"] for d in v["domains"]}}


def tax_with(base, fn):
    """分類体系を変更した複製を作る．@param base fixture．@param fn 変更する関数（分類の辞書を受け取る）．@return dict"""
    tax = copy.deepcopy(base["tax"])
    fn(index(tax))
    return tax


def nodes_with(base, node_id, fields):
    """1件のノードの research_fields を変更した複製を作る．@param base fixture．@param node_id ID．@param fields 分類 ID．@return list"""
    nodes = copy.deepcopy(base["nodes"])
    for _, n in nodes:
        if n["id"] == node_id:
            n["research_fields"] = fields
    return nodes


def subtree_of(base, node_id):
    """ノードが所属する分類と，その祖先の集合．@param base fixture．@param node_id ID．@return set[str]"""
    by_id = index(base["tax"])
    n = next(n for _, n in base["nodes"] if n["id"] == node_id)
    return {x for f in n["research_fields"] for x in [f, *ancestors(f, by_id)]}


def test_real_data_valid(base):
    """実データの分類体系と所属にエラーが無い．"""
    assert taxonomy_errors(base["tax"], base["domains"]) == []
    errors, _ = membership_errors(base["nodes"], base["tax"])
    assert errors == []


def test_three_top_level_areas(base):
    """根の下に，画像圧縮・通信路符号化・画像伝送の3領域がある．"""
    by_id = index(base["tax"])
    root = next(c for c in base["tax"]["categories"] if c["parent"] is None)
    assert root["children"] == ["image_compression", "channel_coding", "image_transmission"]
    assert by_id["image_transmission"]["name_en"].startswith("Image Transmission")


def test_duplicate_category_id(base):
    """重複した分類 ID を検出する．"""
    tax = copy.deepcopy(base["tax"])
    tax["categories"].append(copy.deepcopy(tax["categories"][-1]))
    assert any("重複" in e for e in taxonomy_errors(tax, base["domains"]))


def test_cycle_detection(base):
    """親子関係の循環を検出する（LDPC 符号 → 誤り訂正符号 → LDPC 符号）．"""
    def f(by_id):
        by_id["error_correcting_codes"]["parent"] = "ldpc_codes"
        by_id["ldpc_codes"]["children"] = ["error_correcting_codes"]
    errors = taxonomy_errors(tax_with(base, f), base["domains"])
    assert any("循環" in e for e in errors)


def test_missing_parent_and_child(base):
    """存在しない親・子への参照を検出する．"""
    def f(by_id):
        by_id["turbo_codes"]["parent"] = "no_such_parent"
        by_id["polar_codes"]["children"] = ["no_such_child"]
    errors = taxonomy_errors(tax_with(base, f), base["domains"])
    assert any("no_such_parent" in e for e in errors) and any("no_such_child" in e for e in errors)


def test_parent_children_mismatch(base):
    """parent と children の不整合を検出する．"""
    errors = taxonomy_errors(tax_with(base, lambda b: b["channel_coding"]["children"].remove("information_theory")), base["domains"])
    assert any("information_theory" in e and "children" in e for e in errors)


def test_child_domain_must_match_parent(base):
    """分野を持つ分類の子が別の分野を持つ場合を検出する．"""
    errors = taxonomy_errors(tax_with(base, lambda b: b["ldpc_codes"].update(domain="lic")), base["domains"])
    assert any("ldpc_codes" in e and "親" in e for e in errors)


def test_undefined_category_reference(base):
    """存在しない分類への所属を検出する．"""
    errors, _ = membership_errors(nodes_with(base, "necst", ["no_such_category"]), base["tax"])
    assert any("存在しない分類" in e for e in errors)


def test_member_conditions(base):
    """DDCM を DeepJSCC の配下に置くと，所属の条件（通信路を含む共同学習・アナログ）で検出する．"""
    errors, _ = membership_errors(nodes_with(base, "ddcm", ["analog_deepjscc"]), base["tax"])
    assert any("joint_source_channel_coding" in e for e in errors)
    assert any("analog_deepjscc" in e and "transmission" in e for e in errors)


def test_domain_consistency(base):
    """分類の分野がノードの domains に無い場合（JPEG を LDPC 符号に）を検出する．"""
    errors, _ = membership_errors(nodes_with(base, "jpeg", ["ldpc_codes"]), base["tax"])
    assert any("domains に無い" in e for e in errors)
    assert any("主分野" in e for e in errors)


def test_ancestor_and_descendant(base):
    """分類とその祖先の両方への所属を検出する．"""
    errors, _ = membership_errors(nodes_with(base, "minnen_joint", ["learned_entropy_models", "learned_compression"]), base["tax"])
    assert any("祖先" in e for e in errors)


def test_multi_membership_counted_once(base):
    """複数分類に所属する論文は各分類に現れ，共通の祖先では1件として数える．"""
    nodes = [n for _, n in base["nodes"]]
    m = members(base["tax"], nodes)
    assert "ntscc" in m["analog_deepjscc"] and "ntscc" in m["learned_compression"]
    assert len(m["image_coding"]) == len(nodes) == len(set(m["image_coding"]))
    assert m["image_transmission"].count("d2jscc") == 1  # 分離型と結合型の両方に所属


def test_academic_constraints(base):
    """order_007 の分類上の注意がデータに反映されている．"""
    assert "image_compression" in subtree_of(base, "jpeg") and "channel_coding" in subtree_of(base, "gallager_ldpc")
    jl = subtree_of(base, "sscc_jpeg_ldpc")
    assert "separate_source_channel_coding" in jl and "traditional_compression" not in jl
    for nid in ("ddcm", "turbo_ddcm", "robust_turbo_ddcm"):
        assert "joint_source_channel_coding" not in subtree_of(base, nid)
    assert "digital_deepjscc" in subtree_of(base, "bfr_cae")
    assert {"learned_compression", "joint_source_channel_coding"} <= subtree_of(base, "ntscc")  # LIC と DeepJSCC は排他的でない
    assert {"learned_compression", "generative_compression"} <= subtree_of(base, "hific")
    assert "information_theory" in subtree_of(base, "shannon1948") and "separate_source_channel_coding" not in subtree_of(base, "shannon1948")
