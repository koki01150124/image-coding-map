"""data/ のノードを統合し，サイトが読み込む site/data/graph.json を生成する．
併せて tools/stamp_assets.py で JS・CSS の参照に内容のハッシュを付ける．

描画コードはこの graph.json のみを読むため，論文の追加時に JavaScript を変更する必要は無い．

使い方:
    python tools/build_graph.py
"""
import sys
from datetime import date

import stamp_assets
from common import ROOT, load_node_files, load_vocab, write_json

OUT = ROOT / "site" / "data" / "graph.json"


def build_edges(nodes, edge_types):
    """ノードの relations からエッジの一覧を作る．

    source は関係を登録したノード（新しい側），target は参照先である．

    Args:
        nodes (list[dict]): ノード．
        edge_types (list[dict]): エッジ種別の定義．
    Returns:
        list[dict]: {source, target, type, note, evidence} のリスト．
    """
    known = {t["id"] for t in edge_types}
    edges = []
    for node in nodes:
        for rel in node.get("relations", []):
            if rel["type"] in known:
                edges.append({"source": node["id"], "target": rel["target"], "type": rel["type"],
                              "note": rel["note"], "evidence": rel["evidence"]})
    return edges


def build_graph(nodes, vocab):
    """graph.json の内容を作る．

    Args:
        nodes (list[dict]): ノード．
        vocab (dict): load_vocab の戻り値．
    Returns:
        dict: {generated, domains, edge_types, vocab, nodes, edges}
    """
    public_nodes = [{k: v for k, v in n.items()} for n in sorted(nodes, key=lambda n: (n["year"], n["id"]))]
    return {
        "generated": date.today().isoformat(),
        "domains": sorted(vocab["domains"], key=lambda d: d["order"]),
        "edge_types": sorted(vocab["edge_types"], key=lambda t: t["order"]),
        "vocab": vocab["vocab"],
        "patterns": vocab["patterns"],
        "taxonomy": vocab["taxonomy"],
        "nodes": public_nodes,
        "edges": build_edges(nodes, vocab["edge_types"]),
    }


def main():
    """コマンドラインの入口．

    Returns:
        int: 終了コード．
    """
    nodes = [n for _, n in load_node_files()]
    graph = build_graph(nodes, load_vocab())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT, graph)
    print(f"[build] {OUT.relative_to(ROOT)}: nodes={len(graph['nodes'])} edges={len(graph['edges'])}")
    return stamp_assets.main()  # JS・CSS の参照に内容のハッシュを付ける（ブラウザのキャッシュ対策）


if __name__ == "__main__":
    sys.exit(main())
