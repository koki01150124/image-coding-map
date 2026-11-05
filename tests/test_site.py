"""site/ の表示テスト（Playwright，Chromium）．

site/ を GitHub Pages と同じくサブパス（/image-compression-map/）の静的ファイルとして配信し，
主要な機能が動作し，コンソールにエラーが出ないことを確認する．
事前に python tools/build_graph.py で site/data/graph.json を生成しておく．
"""
import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PREFIX = "/image-compression-map/"


class _Handler(http.server.SimpleHTTPRequestHandler):
    """サブパスを site/ に対応させる静的ファイルサーバー．"""

    def translate_path(self, path):
        """URL のパスをファイルのパスに変換する．

        Args:
            path (str): URL のパス．
        Returns:
            str: ファイルのパス（サブパス外は存在しないパス）．
        """
        path = path.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith(PREFIX):
            return str(SITE / "__not_found__")
        rel = path[len(PREFIX):] or "index.html"
        return str(SITE / rel)

    def log_message(self, *args):
        """ログを出力しない．"""


@pytest.fixture(scope="module")
def base_url():
    """テスト用の静的ファイルサーバーを起動する．

    Yields:
        str: サイトの URL．
    """
    assert (SITE / "data" / "graph.json").exists(), "先に python tools/build_graph.py を実行する"
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}{PREFIX}"
    server.shutdown()


@pytest.fixture(scope="module")
def graph():
    """graph.json を読み込む．

    Returns:
        dict: graph.json の内容．
    """
    return json.loads((SITE / "data" / "graph.json").read_text(encoding="utf-8"))


@pytest.fixture()
def page(base_url):
    """ページを開き，コンソールのエラーを記録する．

    Yields:
        tuple[Page, list[str]]: (ページ, エラーの一覧)．
    """
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        yield pg, errors
        browser.close()


def open_map(pg, url):
    """マップを開き，描画の完了を待つ．

    Args:
        pg (Page): ページ．
        url (str): URL．
    Returns:
        None
    """
    pg.goto(url)
    pg.wait_for_selector("body[data-ready=true]", state="attached", timeout=15000)


def test_render_all_nodes_and_edges(page, base_url, graph):
    """全ノード・全エッジ・分野の列・年の行が描画され，エラーが無い．"""
    pg, errors = page
    open_map(pg, base_url)
    assert pg.locator("g.node").count() == len(graph["nodes"])
    assert pg.locator("path.edge").count() == len(graph["edges"])
    assert pg.locator("g.col").count() == len(graph["domains"])
    assert pg.locator("g.row").count() == len({n["year"] for n in graph["nodes"]})
    assert pg.locator("path.region").count() == len(graph["domains"])
    assert errors == []


def test_select_by_url_hash_and_external_links(page, base_url):
    """URL のハッシュで論文を選択し，詳細パネルに外部リンクが表示される．"""
    pg, errors = page
    open_map(pg, base_url + "#necst")
    pg.wait_for_selector("#panel:not([hidden])")
    body = pg.inner_text("#panel-body")
    assert "NECST" in body and "Neural Joint Source-Channel Coding" in body
    assert pg.locator("#panel-body a[href='https://arxiv.org/abs/1811.07557']").count() == 1
    assert pg.locator("g.node.selected[data-id=necst]").count() == 1
    assert errors == []


def test_unverified_fields_are_marked(page, base_url):
    """未確認の項目が「未確認」と表示される．"""
    pg, _ = page
    open_map(pg, base_url + "#d2jscc")
    pg.wait_for_selector("#panel:not([hidden])")
    assert pg.locator("#panel-body .unverified").count() >= 1


def test_click_node_and_hash(page, base_url):
    """ノードをクリックすると選択され，URL のハッシュが更新される．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.click("#btn-fit")
    pg.wait_for_timeout(700)
    pg.locator("g.node[data-id=deepjscc] .core").click()
    pg.wait_for_selector("#panel:not([hidden])")
    assert pg.evaluate("location.hash") == "#deepjscc"


def test_search(page, base_url):
    """検索で一致する論文が強調され，件数が表示される．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.fill("#search-input", "BSC")
    assert "件" in pg.inner_text("#search-count")
    assert pg.locator("g.node.match").count() >= 4
    assert pg.locator("g.node.match[data-id=blindsc]").count() == 1


def test_domain_filter(page, base_url, graph):
    """分野のボタンで論文を非表示にできる（複数分野の論文は他の分野が表示中なら残る）．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.click("button[data-domain=generative]")
    only_gen = [n for n in graph["nodes"] if n["domains"] == ["generative"]]
    expected = len(graph["nodes"]) - len(only_gen)
    assert pg.locator("g.node").count() == expected
    assert pg.locator("g.node[data-id=ddcm]").count() == 0
    assert pg.locator("g.node[data-id=hific]").count() == 1


def test_edge_type_toggle(page, base_url, graph):
    """エッジ種別のボタンで表示を切り替えられる．"""
    pg, _ = page
    open_map(pg, base_url)
    n_cmp = sum(1 for e in graph["edges"] if e["type"] == "compared_with")
    pg.click("button[data-edge-type=compared_with]")
    assert pg.locator("path.edge.compared_with").count() == 0
    assert pg.locator("path.edge").count() == len(graph["edges"]) - n_cmp


def test_year_slider(page, base_url, graph):
    """年スライダーで指定した年までの論文だけを表示する．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.eval_on_selector("#year-slider", "el => { el.value = '2018'; el.dispatchEvent(new Event('input')); }")
    assert pg.locator("g.node").count() == sum(1 for n in graph["nodes"] if n["year"] <= 2018)
    assert pg.inner_text("#year-out") == "〜2018"


def test_compare_and_lineage_path(page, base_url):
    """URL で比較を指定し，比較表と系譜の経路を表示できる．"""
    pg, errors = page
    open_map(pg, base_url + "#compare=robust_turbo_ddcm,ddcm,bfr_cae")
    pg.wait_for_selector("#compare-view:not([hidden])")
    assert pg.locator(".compare-table thead th").count() == 4
    text = pg.inner_text("#compare-view")
    assert "直系の系譜" in text  # Robust Turbo-DDCM → Turbo-DDCM → DDCM
    pg.locator(".path-box button").first.click()
    assert pg.locator("path.edge.path-on").count() == 2
    assert pg.locator("g.node.path-on").count() == 3
    assert errors == []


def test_theme_toggle(page, base_url):
    """配色ボタンでライト・ダークを切り替えられる．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.click("#btn-theme")
    assert pg.evaluate("document.documentElement.dataset.theme") == "light"
    pg.click("#btn-theme")
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark"


def test_export_svg_and_png(page, base_url, tmp_path):
    """SVG と PNG を書き出せる．"""
    pg, errors = page
    open_map(pg, base_url)
    pg.click("#export-menu summary")
    with pg.expect_download() as d:
        pg.click("#btn-svg")
    svg_path = tmp_path / "map.svg"
    d.value.save_as(svg_path)
    svg = svg_path.read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "NECST" in svg
    pg.click("#export-menu summary")
    with pg.expect_download() as d:
        pg.click("#btn-png")
    png_path = tmp_path / "map.png"
    d.value.save_as(png_path)
    assert png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert errors == []


def test_zoom_by_wheel(page, base_url):
    """マウスホイールで拡大・縮小できる．"""
    pg, _ = page
    open_map(pg, base_url)
    before = pg.get_attribute("g.zoom-root", "transform")
    pg.mouse.move(700, 500)
    pg.mouse.wheel(0, -400)
    pg.wait_for_timeout(300)
    assert pg.get_attribute("g.zoom-root", "transform") != before
