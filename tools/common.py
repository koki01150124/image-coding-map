"""データの読み込みに関する共通処理．

data/ 以下の JSON（ノード，分野，エッジ種別，語彙）と survey/library.json を読み込む関数をまとめる．
標準ライブラリのみに依存する．
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NODES_DIR = DATA / "nodes"
LIBRARY = ROOT / "survey" / "library.json"


def read_json(path):
    """JSON ファイルを読み込む．

    Args:
        path (Path): ファイルのパス．
    Returns:
        Any: 読み込んだ値．
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    """値を整形した JSON として書き出す（UTF-8，末尾改行あり）．

    Args:
        path (Path): 書き出すパス．
        value (Any): 書き出す値．
    Returns:
        None
    """
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_node_files(nodes_dir=NODES_DIR):
    """ノードの JSON ファイルを全て読み込む．

    Args:
        nodes_dir (Path): data/nodes のパス．
    Returns:
        list[tuple[Path, dict]]: (ファイルのパス, ノード) のリスト．ファイル名順．
    """
    return [(p, read_json(p)) for p in sorted(Path(nodes_dir).glob("*.json"))]


def load_vocab(data_dir=DATA):
    """分野・エッジ種別・語彙を読み込む．

    Args:
        data_dir (Path): data ディレクトリのパス．
    Returns:
        dict: {"domains": list[dict], "edge_types": list[dict], "vocab": dict, "rules": list[dict], "patterns": dict}
    """
    data_dir = Path(data_dir)
    return {
        "domains": read_json(data_dir / "domains.json"),
        "edge_types": read_json(data_dir / "edge_types.json"),
        "vocab": read_json(data_dir / "vocab.json"),
        "rules": read_json(data_dir / "classification_rules.json"),
        "patterns": read_json(data_dir / "patterns.json"),
    }


def load_library(path=LIBRARY):
    """survey/library.json（API から取得した書誌情報）を読み込む．

    Args:
        path (Path): library.json のパス．
    Returns:
        dict[str, dict]: 引用キーから文献への辞書．ファイルが無い場合は空の辞書．
    """
    path = Path(path)
    return read_json(path) if path.exists() else {}


def clean_venue(venue):
    """OpenAlex の掲載先名で重複して連結された表記を整理する．

    例: "A/Proceedings - A/Proceedings" → "A"．

    Args:
        venue (str | None): 掲載先名．
    Returns:
        str | None: 整理した掲載先名．
    """
    if not venue:
        return None
    parts = []
    for part in venue.split("/"):
        part = part.strip()
        if part and part not in parts and not any(part in p for p in parts):
            parts.append(part)
    return parts[0] if parts else None


def normalize_author(name):
    """著者名の「姓, 名」の表記を「名 姓」にそろえる（OpenAlex の応答に両方の表記が混在するため）．

    Args:
        name (str): 著者名．
    Returns:
        str: 「名 姓」の表記．カンマが1つでない場合はそのまま返す．
    """
    parts = [p.strip() for p in name.split(",")]
    return f"{parts[1]} {parts[0]}" if len(parts) == 2 and all(parts) else name


def bibliography_from_library(entry):
    """library.json の1件から，ノードの bibliography を作る．

    Args:
        entry (dict): library.json の文献．
    Returns:
        dict: bibliography（title, authors, year, venue, doi, arxiv, url, source）．
    """
    year = entry.get("year")
    url = entry.get("url")
    if url and url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return {
        "title": entry.get("title"),
        "authors": [normalize_author(a) for a in entry.get("authors") or []],
        "year": int(year) if year else None,
        "venue": clean_venue(entry.get("venue")),
        "doi": entry.get("doi"),
        "arxiv": entry.get("arxiv"),
        "url": url,
        "source": "survey/library.json",
    }
