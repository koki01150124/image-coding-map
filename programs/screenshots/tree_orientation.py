"""研究分野樹形図の縦方向・横方向の表示を撮影する（report_009 の図）．

GitHub Pages と同じサブパス（/image-coding-map/）で site/ を配信し，Playwright（Chromium）で撮影する．
事前に `python tools/build_graph.py` で site/data/graph.json を生成しておく．

使い方:
    .venv_tools/bin/python programs/screenshots/tree_orientation.py [出力先]   # 既定は .reports/figures
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
PREFIX = "/image-coding-map"

# (ファイル名, 配色, 幅, 高さ, 方向, 操作) の一覧．操作は "init"（初期表示），"jscc"（結合型 ＞ デジタル型を展開），"all"（すべて展開）
SHOTS = [
    ("report_009_vertical_light_pc_init.png", "light", 1440, 900, "vertical", "init"),
    ("report_009_vertical_light_pc_jscc.png", "light", 1440, 900, "vertical", "jscc"),
    ("report_009_vertical_dark_pc_all.png", "dark", 1440, 900, "vertical", "all"),
    ("report_009_horizontal_light_pc_jscc.png", "light", 1440, 900, "horizontal", "jscc"),
    ("report_009_horizontal_dark_pc_all.png", "dark", 1440, 900, "horizontal", "all"),
    ("report_009_vertical_light_sp_jscc.png", "light", 390, 844, "vertical", "jscc"),
    ("report_009_horizontal_light_sp_jscc.png", "light", 390, 844, "horizontal", "jscc"),
]


class SubpathHandler(http.server.SimpleHTTPRequestHandler):
    """/image-coding-map/ 以下の要求を site/ のファイルに対応させる静的ファイルの配信．"""

    def translate_path(self, path):
        """要求のパスからサブパスを除いてファイルのパスに変換する．

        Args:
            path (str): 要求のパス．
        Returns:
            str: ファイルのパス．
        """
        return super().translate_path(path.replace(PREFIX, "", 1))

    def log_message(self, *args):
        """アクセスログを出力しない．

        Args:
            *args: 未使用．
        Returns:
            None
        """


def serve():
    """site/ を別スレッドで配信する．

    Returns:
        str: サイトの URL（末尾は /image-coding-map/）．
    """
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SubpathHandler, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}{PREFIX}/"


def shoot(browser, url, out, shot):
    """1枚を撮影する．

    Args:
        browser: Playwright のブラウザ．
        url (str): サイトの URL．
        out (Path): 出力先のディレクトリ．
        shot (tuple): SHOTS の要素．
    Returns:
        list[str]: ページで発生したエラー．
    """
    name, scheme, width, height, orientation, action = shot
    page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_selector("g.node")
    page.click("#btn-tree")
    page.wait_for_selector(".tree-node")
    page.click(f"#tree-orient-{orientation}")
    if action == "all":
        page.click("#tree-expand-all")
    if action == "jscc":
        for cid in ("joint_source_channel_coding", "digital_deepjscc"):
            page.locator(f".tree-node.category[data-id={cid}]").click()
    page.screenshot(path=str(out / name))
    page.close()
    return errors


def main():
    """SHOTS のすべてを撮影する．

    Returns:
        int: 終了コード（ページでエラーが発生した場合は1）．
    """
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".reports" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    url = serve()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for shot in tqdm(SHOTS, leave=False):
            errors += shoot(browser, url, out, shot)
        browser.close()
    print(f"[shots] {len(SHOTS)} 枚を {out} に保存した．エラー {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
