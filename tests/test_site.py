"""site/ の表示テスト（Playwright，Chromium）．

site/ を GitHub Pages と同じくサブパス（/image-coding-map/）の静的ファイルとして配信し，
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
PREFIX = "/image-coding-map/"


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
    lineage = {e["id"] for e in graph["edge_types"] if e["lineage"]}
    # 初期表示は技術的な発展関係（derived_from，builds_on）のみ
    assert pg.locator("path.edge").count() == sum(1 for e in graph["edges"] if e["type"] in lineage)
    assert pg.locator("path.edge.related, path.edge.compared_with").count() == 0
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
    """エッジ種別のボタンで表示を切り替えられる（初期は非表示の比較対象・共通研究課題を表示できる）．"""
    pg, _ = page
    open_map(pg, base_url)
    assert pg.get_attribute("button[data-edge-type=compared_with]", "aria-pressed") == "false"
    pg.click("button[data-edge-type=compared_with]")
    pg.click("button[data-edge-type=related]")
    assert pg.locator("path.edge").count() == len(graph["edges"])
    pg.click("button[data-edge-type=derived_from]")
    assert pg.locator("path.edge.derived_from").count() == 0


def test_year_slider(page, base_url, graph):
    """年スライダーで指定した年までの論文だけを表示する．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.eval_on_selector("#year-slider", "el => { el.value = '2018'; el.dispatchEvent(new Event('input')); }")
    assert pg.locator("g.node").count() == sum(1 for n in graph["nodes"] if n["year"] <= 2018)
    assert pg.inner_text("#year-out") == "〜2018"


def test_compare_and_lineage_path(page, base_url):
    """URL で比較を指定し，比較表と技術的系譜（初期状態）を表示できる．"""
    pg, errors = page
    open_map(pg, base_url + "#compare=robust_turbo_ddcm,ddcm,bfr_cae")
    pg.wait_for_selector("#compare-view:not([hidden])")
    assert pg.locator(".compare-table thead th").count() == 4
    assert pg.get_attribute(".path-mode button[data-mode=lineage]", "aria-pressed") == "true"
    box = pg.locator(".path-box[data-pair='robust_turbo_ddcm,ddcm']")
    assert "直系の技術的系譜" in box.inner_text()  # DDCM → Turbo-DDCM → Robust Turbo-DDCM
    # BFR-CAE と Robust Turbo-DDCM は共通課題のみで，技術的系譜は存在しない
    assert "技術的系譜は存在しない" in pg.locator(".path-box[data-pair='robust_turbo_ddcm,bfr_cae']").inner_text()
    box.locator("button").click()
    assert pg.locator("path.edge.path-on").count() == 2
    assert pg.locator("g.node.path-on").count() == 3
    assert pg.locator("path.edge.path-rel").count() == 0
    assert errors == []


def test_blindsc_deepjscc_lineage_vs_related(page, base_url):
    """BlindSC と DeepJSCC（Bourtsoulatze）: 技術的系譜は無く，関連経路では比較対象を含むつながりとして示す．"""
    pg, errors = page
    open_map(pg, base_url + "#compare=blindsc,deepjscc")
    pg.wait_for_selector("#compare-view:not([hidden])")
    box = pg.locator(".path-box")
    assert "技術的系譜は存在しない" in box.inner_text()
    assert box.locator("button").count() == 0
    pg.click(".path-mode button[data-mode=related]")
    text = pg.locator(".path-box").inner_text()
    assert "比較対象" in text and "派生関係ではない" in text
    pg.locator(".path-box button").click()
    assert pg.locator("path.edge.path-rel").count() >= 2
    assert pg.locator("path.edge.path-on").count() == 0
    assert "関連経路" in pg.inner_text("#focus-note")
    assert errors == []


def test_lineage_never_uses_non_lineage_edges(page, base_url, graph):
    """全ての論文の組で，技術的系譜は derived_from・builds_on のみを用い，派生元 → 派生先の向きが年の順と矛盾しない．
    関連経路は4種類の関係を探索できる．"""
    pg, _ = page
    open_map(pg, base_url)
    res = pg.evaluate("""() => {
      const ids = ICM.state.graph.nodes.map((n) => n.id);
      const lin = new Set(), rel = new Set(), bad = [];
      let pairs = 0, linFound = 0;
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        pairs++;
        const l = ICM.findTechnicalLineage(ids[i], ids[j]);
        if (l) { linFound++; for (const s of l.steps) {
          lin.add(s.edge.type);
          const from = ICM.state.byId.get(s.from), to = ICM.state.byId.get(s.to);
          if (s.edge.target !== s.from || s.edge.source !== s.to || from.year > to.year) bad.push([ids[i], ids[j], s.edge]);
        } }
        const r = ICM.findRelatedPath(ids[i], ids[j]);
        if (r) for (const s of r.steps) rel.add(s.edge.type);
      }
      return { lin: [...lin], rel: [...rel], bad, pairs, linFound };
    }""")
    lineage = {e["id"] for e in graph["edge_types"] if e["lineage"]}
    assert set(res["lin"]) <= lineage and res["linFound"] > 0
    assert res["bad"] == []
    assert set(res["rel"]) == {e["id"] for e in graph["edge_types"]}


def test_publication_years_in_panel(page, base_url):
    """初出年と正式掲載年を区別して表示する（NECST: arXiv 2018，ICML 2019）．"""
    pg, _ = page
    open_map(pg, base_url + "#necst")
    pg.wait_for_selector("#panel:not([hidden])")
    body = pg.inner_text("#panel-body")
    assert "年代軸の年: 2018（最初の公開年）" in body
    assert "初出: 2018（arXiv）" in body
    assert "正式掲載: 2019（International Conference on Machine Learning（ICML））" in body


def test_unpublished_has_no_publication_year(page, base_url):
    """未公開の BFR-CAE は研究開発年を発表年として表示しない．"""
    pg, _ = page
    open_map(pg, base_url + "#bfr_cae")
    pg.wait_for_selector("#panel:not([hidden])")
    body = pg.inner_text("#panel-body")
    assert "発表年: 未公開" in body and "発表年ではない" in body
    assert "初出:" not in body
    assert pg.get_attribute("g.node[data-id=bfr_cae]", "aria-label").endswith("（未公開）")


def test_period_select(page, base_url, graph):
    """表示期間「2015年以降」で該当する論文だけを表示し，年スライダーと併用できる．"""
    pg, _ = page
    open_map(pg, base_url)
    pg.select_option("#period-select", "2015")
    assert pg.locator("g.node").count() == sum(1 for n in graph["nodes"] if n["year"] >= 2015)
    pg.eval_on_selector("#year-slider", "el => { el.value = '2020'; el.dispatchEvent(new Event('input')); }")
    assert pg.locator("g.node").count() == sum(1 for n in graph["nodes"] if 2015 <= n["year"] <= 2020)
    pg.select_option("#period-select", "")
    assert pg.locator("g.node").count() == sum(1 for n in graph["nodes"] if n["year"] <= 2020)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_no_overlap_and_contrast(page, base_url, scheme):
    """ノードとラベルが互いに重ならず，ラベルの文字色と背景の対比が十分である（ライト・ダーク）．"""
    pg, errors = page
    pg.emulate_media(color_scheme=scheme)
    open_map(pg, base_url)
    res = pg.evaluate(r"""() => {
      const boxes = [];
      for (const g of document.querySelectorAll("g.node")) {
        const id = g.dataset.id, p = ICM.state.layout.pos.get(id), r = 9;
        boxes.push({ id, kind: "node", x0: p.x - r, y0: p.y - r, x1: p.x + r, y1: p.y + r });
      }
      for (const t of document.querySelectorAll("text.label")) {
        const b = t.getBBox();
        boxes.push({ id: t.dataset.id, kind: "label", x0: b.x, y0: b.y + 2, x1: b.x + b.width, y1: b.y + b.height - 2 });
      }
      const hits = [];
      for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        if (a.id === b.id) continue;
        if (a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1) hits.push([a.id, a.kind, b.id, b.kind]);
      }
      const lum = (c) => { const v = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number).map((x) => x / 255).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
      const fg = getComputedStyle(document.querySelector("text.label")).fill;
      const bg = getComputedStyle(document.querySelector(".stage")).backgroundColor;
      const [l1, l2] = [lum(fg), lum(bg)].sort((x, y) => y - x);
      return { hits, contrast: (l1 + 0.05) / (l2 + 0.05) };
    }""")
    assert res["hits"] == []
    assert res["contrast"] >= 4.5
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
