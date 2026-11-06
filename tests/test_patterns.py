"""改良パターン・採用技術の定義，ノードの参照，判定と集計のテスト．"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate_data  # noqa: E402
from common import load_node_files, load_vocab  # noqa: E402
from patterns import count_table, pattern_status  # noqa: E402


@pytest.fixture(scope="module")
def base():
    """実データを読み込む．

    Returns:
        dict: {"nodes": list[tuple[Path, dict]], "vocab": dict}
    """
    return {"nodes": load_node_files(), "vocab": load_vocab()}


def p_errors(base, nodes=None, defs=None):
    """パターンの検証のみを実行する．

    Args:
        base (dict): fixture の値．
        nodes (list | None): 差し替えるノード．
        defs (dict | None): 差し替えるパターン定義．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    return validate_data.pattern_errors(nodes or base["nodes"], defs or base["vocab"]["patterns"], base["vocab"]["edge_types"])


def modified(base, node_id, fn):
    """1件のノードを変更した複製を作る．

    Args:
        base (dict): fixture の値．
        node_id (str): ノード ID．
        fn (callable): ノードを変更する関数．
    Returns:
        list[tuple[Path, dict]]: ノード．
    """
    nodes = copy.deepcopy(base["nodes"])
    for _, n in nodes:
        if n["id"] == node_id:
            fn(n)
    return nodes


def pattern(base, axis_id, pid):
    """パターン定義を返す．@param base fixture．@param axis_id 軸．@param pid パターン ID．@return dict"""
    axis = next(a for a in base["vocab"]["patterns"]["axes"] if a["id"] == axis_id)
    return next(p for p in axis["patterns"] if p["id"] == pid)


def node(base, nid):
    """ノードを返す．@param base fixture．@param nid ノード ID．@return dict"""
    return next(n for _, n in base["nodes"] if n["id"] == nid)


def test_real_data_consistent(base):
    """パターン定義とノードの参照が整合している（全ノードが patterns を持つ）．"""
    errors, _ = p_errors(base)
    assert errors == []
    assert all("patterns" in n for _, n in base["nodes"])


def test_undefined_pattern_id(base):
    """未定義のパターン ID を検出する．"""
    item = {"id": "no_such_pattern", "evidence": {"kind": "node_field", "detail": "x"}}
    errors, _ = p_errors(base, modified(base, "necst", lambda n: n["patterns"]["improvements"]["items"].append(item)))
    assert any("未定義" in e and "no_such_pattern" in e for e in errors)


def test_duplicate_pattern_in_node(base):
    """同じノード内の重複したパターンを検出する．"""
    def f(n):
        n["patterns"]["techniques"]["items"].append(copy.deepcopy(n["patterns"]["techniques"]["items"][0]))
    errors, _ = p_errors(base, modified(base, "necst", f))
    assert any("重複" in e for e in errors)


def test_duplicate_pattern_definition(base):
    """パターン定義の重複 ID を検出する．"""
    defs = copy.deepcopy(base["vocab"]["patterns"])
    defs["axes"][0]["patterns"].append(copy.deepcopy(defs["axes"][0]["patterns"][0]))
    errors, _ = p_errors(base, defs=defs)
    assert any("重複" in e and "patterns.json" in e for e in errors)


def test_invalid_condition_syntax(base):
    """非該当の条件の書式の誤りを検出する．"""
    defs = copy.deepcopy(base["vocab"]["patterns"])
    defs["axes"][1]["patterns"][1]["not_applicable_if"] = [{"field": "training", "startswith": "学習なし"}]
    errors, _ = p_errors(base, defs=defs)
    assert any("書式" in e for e in errors)


def test_items_on_not_applicable_axis(base):
    """対象外の軸に該当を挙げた場合を検出する．"""
    item = {"id": "entropy_model", "evidence": {"kind": "node_field", "detail": "x"}}
    errors, _ = p_errors(base, modified(base, "shannon1948", lambda n: n["patterns"]["improvements"]["items"].append(item)))
    assert any("not_applicable" in e for e in errors)


def test_from_must_be_lineage(base):
    """改良元が系譜の関係に無い場合を検出する．"""
    def f(n):
        n["patterns"]["improvements"]["items"][0]["from"] = "jpeg"
    errors, _ = p_errors(base, modified(base, "minnen_joint", f))
    assert any("改良元" in e for e in errors)


def test_item_conflicts_with_condition(base):
    """非該当の条件（学習なし）に一致するノードに学習型の技術を付けた場合を検出する．"""
    item = {"id": "learned_autoencoder", "evidence": {"kind": "node_field", "detail": "x"}}
    errors, _ = p_errors(base, modified(base, "jpeg", lambda n: n["patterns"]["techniques"]["items"].append(item)))
    assert any("非該当の条件" in e for e in errors)


def test_unknown_vs_not_applicable(base):
    """未判定と非該当を区別する．"""
    em = pattern(base, "improvements", "entropy_model")
    la = pattern(base, "techniques", "learned_autoencoder")
    assert pattern_status(node(base, "minnen_joint"), "improvements", em) == "yes"
    assert pattern_status(node(base, "deepjscc"), "improvements", em) == "no"          # 判定済みで挙げていない
    assert pattern_status(node(base, "shannon1948"), "improvements", em) == "no"       # 対象外
    assert pattern_status(node(base, "jpeg"), "improvements", em) == "unknown"         # 未判定
    assert pattern_status(node(base, "gallager_ldpc"), "improvements", em) == "unknown"  # 部分判定で挙げていない
    assert pattern_status(node(base, "gallager_ldpc"), "techniques", la) == "no"       # 非該当の条件（学習なし）
    assert pattern_status(node(base, "deepjscc"), "techniques", pattern(base, "techniques", "hyperprior")) == "unknown"


def test_count_table_multi_domain(base):
    """複数分野のノードは各分野に計上し，行の合計は重複を除く．"""
    papers = [n for _, n in base["nodes"] if n["kind"] == "paper"]
    domains = [d["id"] for d in base["vocab"]["domains"]]
    t = count_table(papers, base["vocab"]["patterns"], "improvements", domains)
    assert "ntscc" in t["cells"][("entropy_model", "lic")]["yes"]
    assert "ntscc" in t["cells"][("entropy_model", "analog_jscc")]["yes"]
    cell_sum = sum(len(v["yes"]) for (p, _), v in t["cells"].items() if p == "entropy_model")
    assert t["row_total"]["entropy_model"] == cell_sum - 1 == 7


def test_count_table_matches_raw(base):
    """セルの集計値が元データ（各ノードの items）から独立に数えた値と一致する．"""
    papers = [n for _, n in base["nodes"] if n["kind"] == "paper"]
    domains = [d["id"] for d in base["vocab"]["domains"]]
    for axis in ("improvements", "techniques"):
        t = count_table(papers, base["vocab"]["patterns"], axis, domains)
        for (pid, d), v in t["cells"].items():
            expected = sorted(n["id"] for n in papers if d in n["domains"] and any(i["id"] == pid for i in n["patterns"][axis]["items"]))
            assert sorted(v["yes"]) == expected
