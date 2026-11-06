"""改良パターン・採用技術の判定と集計．

ノードとパターンの組の状態を以下の3値で判定する（site/assets/patterns.js と同じ規則）．
    yes      該当: ノードの patterns.<軸>.items に挙げられている
    no       非該当: 軸の判定が assessed（挙げていないものは非該当）か not_applicable であるか，
             パターン定義の not_applicable_if の条件に一致する
    unknown  未判定: 上記以外（partial で挙げていない，または unassessed）

パターン表のセルは「分野 × パターン」の該当ノード数であり，複数分野のノードは各分野に計上する．
"""
from collections import defaultdict

from common import DATA, read_json

PATTERNS_FILE = DATA / "patterns.json"


def load_patterns(path=PATTERNS_FILE):
    """パターン定義を読み込む．

    Args:
        path (Path): data/patterns.json のパス．
    Returns:
        dict: パターン定義（axes 等）．
    """
    return read_json(path)


def condition_matches(node, cond):
    """非該当の条件に一致するかを判定する．

    Args:
        node (dict): ノード．
        cond (dict): {field, prefix | equals | in}．
    Returns:
        bool: 一致すれば True．
    """
    value = node.get(cond["field"])
    if "prefix" in cond:
        return isinstance(value, str) and value.startswith(cond["prefix"])
    if "equals" in cond:
        return value == cond["equals"]
    if "in" in cond:
        return value in cond["in"]
    return False  # 書式の誤りは validate_data.pattern_definition_errors が検出する


def pattern_status(node, axis_id, pattern):
    """ノードとパターンの組の状態（yes／no／unknown）を返す．

    Args:
        node (dict): ノード．
        axis_id (str): "improvements" または "techniques"．
        pattern (dict): パターン定義．
    Returns:
        str: "yes"，"no"，"unknown"．
    """
    axis = node.get("patterns", {}).get(axis_id, {"assessment": "unassessed", "items": []})
    if any(it["id"] == pattern["id"] for it in axis["items"]):
        return "yes"
    if axis["assessment"] in ("assessed", "not_applicable"):
        return "no"
    if any(condition_matches(node, c) for c in pattern.get("not_applicable_if", [])):
        return "no"
    return "unknown"


def count_table(nodes, defs, axis_id, domains):
    """パターン表の集計を行う．

    Args:
        nodes (list[dict]): 集計対象のノード（絞り込み済み）．
        defs (dict): パターン定義．
        axis_id (str): 軸の ID．
        domains (list[str]): 列（分野 ID）．
    Returns:
        dict: {"cells": {(pattern, domain): {"yes": [ids], "unknown": [ids]}},
               "row_total": {pattern: 重複を除いた該当数}, "col_total": {domain: 重複を除いた該当ノード数},
               "total": 重複を除いた該当ノード数}
    """
    axis = next(a for a in defs["axes"] if a["id"] == axis_id)
    cells = defaultdict(lambda: {"yes": [], "unknown": []})
    rows, cols, total = defaultdict(set), defaultdict(set), set()
    for p in axis["patterns"]:
        for n in nodes:
            st = pattern_status(n, axis_id, p)
            for d in n["domains"]:
                if d not in domains:
                    continue
                if st == "yes":
                    cells[(p["id"], d)]["yes"].append(n["id"])
                    rows[p["id"]].add(n["id"])
                    cols[d].add(n["id"])
                    total.add(n["id"])
                elif st == "unknown":
                    cells[(p["id"], d)]["unknown"].append(n["id"])
    return {"cells": dict(cells), "row_total": {k: len(v) for k, v in rows.items()},
            "col_total": {k: len(v) for k, v in cols.items()}, "total": len(total)}
