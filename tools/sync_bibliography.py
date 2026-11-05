"""survey/library.json の書誌情報をノードの bibliography に転記する．

書誌情報（タイトル，著者，年，掲載先，DOI，arXiv ID，URL）は API から取得した
survey/library.json を唯一の出典とし，ノードの JSON には手で書かない．

使い方:
    python tools/sync_bibliography.py          # 転記する
    python tools/sync_bibliography.py --check  # 不一致があれば終了コード1（CI 用）
"""
import argparse
import sys

from common import bibliography_from_library, load_library, load_node_files, write_json


def diff_bibliography(nodes, library):
    """bib_key を持つノードについて，library と一致しない bibliography を求める．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        library (dict[str, dict]): library.json の内容．
    Returns:
        tuple[list[tuple[Path, dict, dict]], list[str]]:
            (更新が必要な (パス, ノード, 新しい bibliography) のリスト, エラーのリスト)．
    """
    updates, errors = [], []
    for path, node in nodes:
        key = node.get("bib_key")
        if key is None:
            continue
        if key not in library:
            errors.append(f"{path.name}: bib_key '{key}' が survey/library.json に無い")
            continue
        expected = bibliography_from_library(library[key])
        if node.get("bibliography") != expected:
            updates.append((path, node, expected))
    return updates, errors


def main(argv=None):
    """コマンドラインの入口．

    Args:
        argv (list[str] | None): 引数．
    Returns:
        int: 終了コード．
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="書き換えずに不一致を報告する")
    args = parser.parse_args(argv)

    updates, errors = diff_bibliography(load_node_files(), load_library())
    for e in errors:
        print(f"[error] {e}")
    if args.check:
        for path, _, _ in updates:
            print(f"[error] {path.name}: bibliography が survey/library.json と一致しない（sync_bibliography.py を実行）")
        print(f"[sync] 不一致 {len(updates)} 件，エラー {len(errors)} 件")
        return 1 if (updates or errors) else 0
    for path, node, bib in updates:
        node["bibliography"] = bib
        write_json(path, node)
    print(f"[sync] {len(updates)} 件を更新，エラー {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
