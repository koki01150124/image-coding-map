"""ノードデータの検証．

検証の内容:
    1. JSON スキーマ（data/schema/node.schema.json）
    2. ID とファイル名の一致，重複 ID
    3. 分野・エッジ種別が定義済みであること
    4. 関係の参照先の存在，自己参照，重複
    5. 系譜関係（lineage が true のエッジ種別）の循環
    6. 発表年と書誌情報の年の整合（異なる場合は year_note が必要）
    7. 論文の書誌情報が survey/library.json と一致すること

使い方:
    python tools/validate_data.py   # エラーがあれば終了コード1
"""
import sys
from collections import defaultdict

from common import DATA, load_library, load_node_files, load_vocab, read_json
from sync_bibliography import diff_bibliography


def schema_errors(nodes, schema):
    """JSON スキーマによる検証．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        schema (dict): JSON スキーマ．
    Returns:
        list[str]: エラーのリスト．
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema がインストールされていない（pip install -r requirements_tools.txt）"]
    validator = Draft202012Validator(schema)
    errors = []
    for path, node in nodes:
        for err in sorted(validator.iter_errors(node), key=lambda e: list(e.path)):
            loc = "/".join(str(p) for p in err.path) or "(root)"
            errors.append(f"{path.name}: スキーマ違反 {loc}: {err.message}")
    return errors


def identity_errors(nodes):
    """ID とファイル名の一致と，重複 ID を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
    Returns:
        list[str]: エラーのリスト．
    """
    errors, seen = [], {}
    for path, node in nodes:
        nid = node.get("id")
        if nid != path.stem:
            errors.append(f"{path.name}: id '{nid}' がファイル名と一致しない")
        if nid in seen:
            errors.append(f"{path.name}: id '{nid}' が {seen[nid]} と重複")
        seen.setdefault(nid, path.name)
    return errors


def relation_errors(nodes, edge_types):
    """関係の参照先・種別・自己参照・重複を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        edge_types (list[dict]): エッジ種別の定義．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors, warnings = [], []
    ids = {n["id"] for _, n in nodes}
    by_id = {n["id"]: n for _, n in nodes}
    types = {t["id"]: t for t in edge_types}
    undirected_pairs = set()
    for _, node in nodes:
        nid, seen = node["id"], set()
        for rel in node.get("relations", []):
            tgt, typ = rel.get("target"), rel.get("type")
            if typ not in types:
                errors.append(f"{nid}: 未定義のエッジ種別 '{typ}'")
                continue
            if tgt == nid:
                errors.append(f"{nid}: 自己参照の関係（{typ}）")
                continue
            if tgt not in ids:
                errors.append(f"{nid}: 関係の参照先 '{tgt}' が存在しない（{typ}）")
                continue
            if (tgt, typ) in seen:
                errors.append(f"{nid}: '{tgt}' への {typ} が重複")
            seen.add((tgt, typ))
            if not types[typ]["directed"]:
                pair = (frozenset((nid, tgt)), typ)
                if pair in undirected_pairs:
                    warnings.append(f"{nid}: '{tgt}' との {typ} が両方向に登録されている")
                undirected_pairs.add(pair)
            if types[typ]["lineage"] and by_id[tgt]["year"] > node["year"]:
                warnings.append(f"{nid}（{node['year']}）: 系譜の元 '{tgt}'（{by_id[tgt]['year']}）の方が新しい")
    return errors, warnings


def find_lineage_cycles(nodes, edge_types):
    """系譜関係（lineage が true のエッジ）の有向グラフの循環を検出する．

    エッジの向きは「新しい手法 → 元の手法」である．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        edge_types (list[dict]): エッジ種別の定義．
    Returns:
        list[list[str]]: 検出した循環（ノードIDの列）のリスト．
    """
    lineage = {t["id"] for t in edge_types if t["lineage"]}
    graph = defaultdict(list)
    for _, node in nodes:
        for rel in node.get("relations", []):
            if rel.get("type") in lineage:
                graph[node["id"]].append(rel["target"])
    color, cycles = {}, []

    def visit(u, stack):
        """深さ優先探索で循環を探す．

        Args:
            u (str): 現在のノード．
            stack (list[str]): 探索中の経路．
        Returns:
            None
        """
        color[u] = "gray"
        stack.append(u)
        for v in graph.get(u, []):
            if color.get(v) == "gray":
                cycles.append(stack[stack.index(v):] + [v])
            elif v not in color:
                visit(v, stack)
        stack.pop()
        color[u] = "black"

    for _, node in nodes:
        if node["id"] not in color:
            visit(node["id"], [])
    return cycles


def bibliography_errors(nodes, library):
    """発表年・書誌情報の整合を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        library (dict[str, dict]): library.json の内容．
    Returns:
        list[str]: エラーのリスト．
    """
    errors = []
    for path, node in nodes:
        bib = node.get("bibliography", {})
        if node.get("kind") == "paper" and not node.get("bib_key"):
            errors.append(f"{path.name}: 論文（kind=paper）は survey/library.json の bib_key が必要")
        if bib.get("year") != node.get("year") and not node.get("year_note"):
            errors.append(f"{path.name}: year（{node.get('year')}）が書誌情報の年（{bib.get('year')}）と異なるが year_note が無い")
    updates, sync_errors = diff_bibliography(nodes, library)
    errors += sync_errors
    errors += [f"{p.name}: bibliography が survey/library.json と一致しない" for p, _, _ in updates]
    return errors


def validate(nodes, vocab, schema, library):
    """全ての検証を実行する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        vocab (dict): load_vocab の戻り値．
        schema (dict): JSON スキーマ．
        library (dict[str, dict]): library.json の内容．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors = schema_errors(nodes, schema) + identity_errors(nodes)
    if errors:
        return errors, []
    domain_ids = {d["id"] for d in vocab["domains"]}
    for path, node in nodes:
        for d in node["domains"]:
            if d not in domain_ids:
                errors.append(f"{path.name}: 未定義の分野 '{d}'")
    rel_errors, warnings = relation_errors(nodes, vocab["edge_types"])
    errors += rel_errors
    errors += ["系譜関係の循環: " + " -> ".join(c) for c in find_lineage_cycles(nodes, vocab["edge_types"])]
    errors += bibliography_errors(nodes, library)
    return errors, warnings


def main():
    """コマンドラインの入口．

    Returns:
        int: 終了コード（エラーがあれば1）．
    """
    nodes = load_node_files()
    errors, warnings = validate(nodes, load_vocab(), read_json(DATA / "schema" / "node.schema.json"), load_library())
    for w in warnings:
        print(f"[warn]  {w}")
    for e in errors:
        print(f"[error] {e}")
    n_edges = sum(len(n.get("relations", [])) for _, n in nodes)
    print(f"[validate] nodes={len(nodes)} edges={n_edges} errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
