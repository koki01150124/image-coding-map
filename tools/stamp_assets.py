"""サイトの JS・CSS の参照に内容のハッシュを付け，ブラウザに古いファイルが残る問題を防ぐ．

GitHub Pages はファイルを一定時間（max-age=600）キャッシュさせるため，更新直後に HTML だけが新しく，
app.js が古いまま読み込まれることがある（例: 新しいボタンが表示されるが，対応する処理が無く反応しない）．
参照に `?v=<内容のハッシュ>` を付けると，内容が変わったファイルは別の URL となり，必ず取り直される．

処理の順序（同じ内容なら何度実行しても結果は変わらない）:
    1. app.js の import（./layout.js，./patterns.js，./tree.js）に，各ファイルのハッシュを付ける
    2. index.html の style.css と app.js の参照に，各ファイルのハッシュを付ける

使い方:
    python tools/stamp_assets.py      # build_graph.py からも呼ばれる
"""
import hashlib
import re
import sys

from common import ROOT

SITE = ROOT / "site"
ASSETS = SITE / "assets"


def short_hash(path):
    """ファイルの内容の短いハッシュ（SHA-256 の先頭10文字）．

    Args:
        path (Path): ファイル．
    Returns:
        str: ハッシュ．
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def stamp(text, name, digest, prefix):
    """text 中の参照 `<prefix><name>` と `<prefix><name>?v=...` を `<prefix><name>?v=<digest>` に置き換える．

    Args:
        text (str): 対象の文字列．
        name (str): ファイル名（例: "layout.js"）．
        digest (str): ハッシュ．
        prefix (str): 参照の前置き（例: "./"，"assets/"）．
    Returns:
        tuple[str, int]: (置き換えた文字列, 置き換えた数)．
    """
    pattern = re.compile(re.escape(prefix + name) + r'(\?v=[0-9a-f]+)?(?=")')
    return pattern.subn(f"{prefix}{name}?v={digest}", text)


def main():
    """app.js と index.html の参照を更新する．

    Returns:
        int: 終了コード（参照が見つからない場合は1）．
    """
    app = ASSETS / "app.js"
    text = app.read_text(encoding="utf-8")
    for module in ("layout.js", "patterns.js", "tree.js"):
        text, n = stamp(text, module, short_hash(ASSETS / module), "./")
        if n == 0:
            print(f"[stamp] app.js に ./{module} の import が無い")
            return 1
    if text != app.read_text(encoding="utf-8"):
        app.write_text(text, encoding="utf-8")
    index = SITE / "index.html"
    html = index.read_text(encoding="utf-8")
    for name in ("style.css", "app.js"):
        html, n = stamp(html, name, short_hash(ASSETS / name), "assets/")
        if n == 0:
            print(f"[stamp] index.html に assets/{name} の参照が無い")
            return 1
    if html != index.read_text(encoding="utf-8"):
        index.write_text(html, encoding="utf-8")
    print(f"[stamp] app.js?v={short_hash(app)} style.css?v={short_hash(ASSETS / 'style.css')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
