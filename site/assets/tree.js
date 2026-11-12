// Image Coding Map — 研究分野樹形図（D3 v7 の d3.tree による階層の表示）
//
// 樹形図の線は，分類の親子関係（実線）と，分類への論文の所属（破線）のみを表す．
// 技術的な派生関係は研究系譜図で表す．論文の情報は graph.nodes を参照し，複製しない．

const ROW = 26;          // 横方向：行の間隔（px）
const PAD = 44;          // 横方向：列の余白（ラベルの右端から次の列まで）
const R_CAT = 7, R_PAPER = 4.5;
const LINE = 16;         // 縦方向：ラベル1行の高さ（px）
const GAP_SIB = 16;      // 縦方向：兄弟の間隔（ラベルの端から端まで）
const GAP_COUSIN = 30;   // 縦方向：親の異なる隣のノードとの間隔
const GAP_LEVEL = 40;    // 縦方向：階層の間隔（上の階層の最下端から次の階層のノードまで）
const MARGIN = 20;       // 画面の端からの余白（px）

/**
 * 表示方向ごとの配置の定義．描画（render）は両方向で共通とし，ここでは座標・線・ラベルの位置のみを変える．
 * 各ノード d には，ラベルの行 d.lines と，その最大幅 d.lw を事前に設定しておく（wrap が数値の方向では，分類名をその幅で折り返す）．
 *   layout(h, d3): d3.hierarchy の各ノードに表示座標 (d.px, d.py) を設定する．
 *   linkPath(l) : 親子を結ぶ線の SVG パス．
 *   label(d)    : ラベルの位置と向き {x, y, anchor, rotate}．
 *   extent(d)   : ノードとラベルが占める矩形 [x0, y0, x1, y1]（樹形図の座標）．
 *   reveal      : 画面外に出た場合の軸ごとの合わせ方（"start" は始端，"center" は中央）．
 */
export const ORIENTATIONS = {
  // 横方向：上位を左，下位を右．同じ階層は縦に並ぶ（従来の表示）
  horizontal: {
    label_ja: "横方向",
    wrap: null,
    layout(h, d3) {
      d3.tree().nodeSize([ROW, 1]).separation((a, b) => (a.parent === b.parent ? 1 : 1.25))(h);
      // 列の幅は，その深さのラベルの最大幅から決める（ラベルと次の列のノードが重ならない）
      const widths = [];
      h.each((d) => { widths[d.depth] = Math.max(widths[d.depth] || 0, d.lw); });
      const xs = [0];
      for (let i = 1; i < widths.length; i++) xs[i] = xs[i - 1] + widths[i - 1] + PAD + 16;
      h.each((d) => { d.px = xs[d.depth]; d.py = d.x; });
    },
    // 線は親のラベルの右端から子のノードへ引く（ラベルの文字に重ならない）
    linkPath(l) {
      const sx = l.source.px + 12 + l.source.lw + 6, tx = l.target.px - (l.target.data.type === "paper" ? R_PAPER + 2 : R_CAT + 1);
      const mx = (sx + tx) / 2;
      return `M${sx},${l.source.py}C${mx},${l.source.py} ${mx},${l.target.py} ${tx},${l.target.py}`;
    },
    label: (d) => ({ x: d.data.type === "paper" ? 10 : 12, y: 4, anchor: "start", rotate: 0 }),
    extent: (d) => [d.px - R_CAT, d.py - LINE / 2, d.px + 12 + d.lw, d.py + LINE / 2],
    reveal: { x: "start", y: "center" },
  },
  // 縦方向：上位を上，下位を下．同じ階層は横に並ぶ
  vertical: {
    label_ja: "縦方向",
    wrap: 118,   // 分類名を折り返す幅（px）．兄弟が横に並ぶため，長い分類名で横幅が広がり過ぎないようにする
    layout(h, d3) {
      // 兄弟の間隔はラベルの幅から決める（nodeSize を1とし，separation に px 単位の距離を返す）
      d3.tree().nodeSize([1, 1]).separation((a, b) => (footprint(a) + footprint(b)) / 2 + (a.parent === b.parent ? GAP_SIB : GAP_COUSIN))(h);
      // 階層の高さは，その深さで最も下まで伸びるラベル（論文は縦書きのラベル）から決める
      const heights = [];
      h.each((d) => { heights[d.depth] = Math.max(heights[d.depth] || 0, depthExtent(d)); });
      const ys = [0];
      for (let i = 1; i < heights.length; i++) ys[i] = ys[i - 1] + heights[i - 1] + GAP_LEVEL;
      h.each((d) => { d.px = d.x; d.py = ys[d.depth]; });
    },
    // 線は親のラベルの下から，階層の間の空白で折れて子のノードへ引く（ラベルの文字に重ならない）
    linkPath(l) {
      const sy = l.source.py + depthExtent(l.source) + 2, ty = l.target.py - radius(l.target) - 1;
      const my = ty - GAP_LEVEL / 2 + radius(l.target);
      return `M${l.source.px},${sy}V${my}H${l.target.px}V${ty}`;
    },
    label: (d) => (d.data.type === "paper"
      ? { x: R_PAPER + 6, y: 4, anchor: "start", rotate: 90 }
      : { x: 0, y: R_CAT + 15, anchor: "middle", rotate: 0 }),
    extent: (d) => {
      const w = footprint(d) / 2;
      return [d.px - w, d.py - radius(d), d.px + w, d.py + depthExtent(d)];
    },
    reveal: { x: "center", y: "start" },
  },
};

/** 論文の菱形と分類の円の半径．@param {object} d - ノード．@returns {number} */
const radius = (d) => (d.data.type === "paper" ? R_PAPER : R_CAT);
/** 縦方向で兄弟方向（横）に占める幅．論文のラベルは縦書き（回転）のため1行分．@param {object} d @returns {number} */
const footprint = (d) => (d.data.type === "paper" ? LINE : Math.max(d.lw, 2 * R_CAT));
/** 縦方向でノードの中心から下へ伸びる長さ（ラベルを含む）．@param {object} d @returns {number} */
const depthExtent = (d) => (d.data.type === "paper" ? R_PAPER + 6 + d.lw : R_CAT + 4 + LINE * d.lines.length);

/**
 * ラベルを指定の幅で折り返す．「・」の後，「（」の前，「）」の後と空白で優先して改行し，それでも長い部分は文字単位で改行する．
 * @param {string} s - ラベル．
 * @param {number|null} maxWidth - 折り返す幅（px）．null は折り返さない．
 * @param {function(string): number} measure - 文字列の描画幅（px）を返す関数．
 * @returns {string[]} 行．
 */
export function wrapLabel(s, maxWidth, measure) {
  if (!maxWidth || measure(s) <= maxWidth) return [s];
  const pieces = s.split(/(?<=[・）\s])|(?=（)/u).filter(Boolean);
  const lines = [];
  let cur = "";
  const push = (piece) => {
    if (!cur || measure(cur + piece) <= maxWidth) { cur += piece; return; }
    lines.push(cur); cur = piece;
  };
  for (const piece of pieces) {
    if (measure(piece) <= maxWidth) { push(piece); continue; }
    for (const ch of piece) push(ch);  // 区切りの無い長い部分は文字単位で改行する
  }
  if (cur) lines.push(cur);
  return lines;
}

/**
 * 分類の辞書と，祖先をたどる関数を作る．
 * @param {object} taxonomy - research_taxonomy.json の内容．
 * @returns {{byId: Map<string, object>, ancestors: function(string): string[], root: object}}
 */
export function indexTaxonomy(taxonomy) {
  const byId = new Map(taxonomy.categories.map((c) => [c.id, c]));
  const ancestors = (id) => {
    const out = [];
    for (let cur = byId.get(id)?.parent; cur != null && !out.includes(cur); cur = byId.get(cur)?.parent) out.push(cur);
    return out;
  };
  return { byId, ancestors, root: taxonomy.categories.find((c) => c.parent == null) };
}

/**
 * 分類ごとの所属ノード（子孫の分類の所属を含む）を求める．
 * @param {object} taxonomy - 分類体系．
 * @param {object[]} nodes - ノード（絞り込み済み）．
 * @returns {Map<string, object[]>} 分類 ID → ノード（重複なし）．
 */
export function categoryMembers(taxonomy, nodes) {
  const { byId, ancestors } = indexTaxonomy(taxonomy);
  const out = new Map();
  for (const n of nodes) {
    const targets = new Set();
    for (const f of n.research_fields || []) if (byId.has(f)) { targets.add(f); for (const a of ancestors(f)) targets.add(a); }
    for (const t of targets) { if (!out.has(t)) out.set(t, []); out.get(t).push(n); }
  }
  return out;
}

/**
 * 表示用の階層データを作る．展開した分類の下に，子の分類と（showPapers のとき）直接所属する論文を置く．
 * @param {object} taxonomy - 分類体系．
 * @param {object[]} nodes - 表示するノード．
 * @param {Set<string>} expanded - 展開している分類の ID．
 * @param {boolean} showPapers - 論文を葉として表示するか．
 * @returns {object} d3.hierarchy に渡す木（{type, id, cat|node, children}）．
 */
export function buildTree(taxonomy, nodes, expanded, showPapers) {
  const { byId, root } = indexTaxonomy(taxonomy);
  const direct = new Map();
  for (const n of nodes) for (const f of n.research_fields || []) { if (!direct.has(f)) direct.set(f, []); direct.get(f).push(n); }
  const make = (cat) => {
    const item = { type: "category", id: cat.id, cat, hasHidden: false };
    const kids = [...cat.children].map((id) => byId.get(id)).sort((a, b) => a.order - b.order);
    const papers = (direct.get(cat.id) || []).slice().sort((a, b) => a.year - b.year || a.id.localeCompare(b.id));
    if (expanded.has(cat.id)) {
      item.children = kids.map(make);
      if (showPapers) item.children.push(...papers.map((n) => ({ type: "paper", id: `${cat.id}/${n.id}`, node: n, parentCat: cat.id })));
      if (!showPapers && papers.length) item.hasHidden = true;
    } else {
      item.hasHidden = kids.length > 0 || papers.length > 0;
    }
    return item;
  };
  return make(root);
}

/**
 * 研究分野樹形図の表示を作る．
 * @param {object} deps - 依存（container，detail，graph，d3，el，isNodeVisible，domainColor，yearLabel，textWidth，
 *   onSelectPaper(id)，onShowOnMap(id)，onHighlight(ids, label)，selectedPaper()）．
 * @returns {{render: function(): void, setMatches: function(Set<string>|null): void, fit: function(): void,
 *   reveal: function(string): void, setOrientation: function(string): void, markSelectedPaper: function(): void, state: object}}
 */
export function createTreeView(deps) {
  const { container, detail, graph, d3, el } = deps;
  const tax = graph.taxonomy;
  const { byId, ancestors, root } = indexTaxonomy(tax);
  const state = {
    expanded: new Set([root.id, ...root.children]),
    showPapers: true,
    selected: null,
    matches: null,
    transform: null,
    orientation: "vertical",   // 初期表示は縦方向（再読み込みで縦方向に戻る）
  };
  /** 現在の表示方向の定義．@returns {object} */
  const orient = () => ORIENTATIONS[state.orientation];
  let lastLayout = null;
  const svg = d3.select(container).append("svg").attr("class", "tree-svg").attr("role", "img").attr("aria-label", "研究分野樹形図");
  const g = svg.append("g").attr("class", "tree-root");
  const zoom = d3.zoom().scaleExtent([0.25, 3]).on("zoom", (ev) => { state.transform = ev.transform; g.attr("transform", ev.transform); });
  svg.call(zoom).on("dblclick.zoom", null);

  const visibleNodes = () => graph.nodes.filter(deps.isNodeVisible);
  const catColor = (cat) => (cat.domain ? deps.domainColor(cat.domain) : "var(--text-secondary)");
  const labelOf = (d, counts) => {
    if (d.data.type === "paper") {
      const n = d.data.node, k = (n.research_fields || []).length;
      return `${n.short_name}（${deps.yearLabel(n)}）${k > 1 ? `  ◆複数所属 ${k}` : ""}`;
    }
    const c = d.data.cat;
    return `${c.name_ja}（${(counts.get(c.id) || []).length}）`;
  };

  /** 描画する．@returns {void} */
  function render() {
    const nodes = visibleNodes();
    const counts = categoryMembers(tax, nodes);
    const data = buildTree(tax, nodes, state.expanded, state.showPapers);
    const h = d3.hierarchy(data);
    const o = orient();
    h.each((d) => {
      const bold = d.data.type === "category";
      const measure = (s) => deps.textWidth(s, bold);
      d.lines = bold ? wrapLabel(labelOf(d, counts), o.wrap, measure) : [labelOf(d, counts)];
      d.lw = Math.max(...d.lines.map(measure));
    });
    o.layout(h, d3);

    g.selectAll("*").remove();
    svg.attr("data-orientation", state.orientation);
    g.append("g").attr("class", "tree-links").selectAll("path").data(h.links()).join("path")
      .attr("class", (l) => `tree-link ${l.target.data.type}`)
      .attr("d", (l) => o.linkPath(l));
    const nodeG = g.append("g").attr("class", "tree-nodes").selectAll("g").data(h.descendants()).join("g")
      .attr("class", (d) => {
        const cls = [`tree-node ${d.data.type}`];
        if (d.data.type === "category") {
          if (state.expanded.has(d.data.id)) cls.push("expanded");
          if (d.data.hasHidden) cls.push("collapsed");
          if (state.selected === d.data.id) cls.push("selected");
          if (!(counts.get(d.data.id) || []).length) cls.push("empty");
        } else {
          if ((d.data.node.research_fields || []).length > 1) cls.push("multi");
          if (state.matches?.has(d.data.node.id)) cls.push("match");
          if (deps.selectedPaper?.() === d.data.node.id) cls.push("selected");
        }
        return cls.join(" ");
      })
      .attr("transform", (d) => `translate(${d.px},${d.py})`)
      .attr("data-id", (d) => (d.data.type === "paper" ? d.data.node.id : d.data.id))
      .attr("data-type", (d) => d.data.type)
      .attr("tabindex", 0).attr("role", "button");
    nodeG.filter((d) => d.data.type === "category").append("circle").attr("r", R_CAT)
      .style("stroke", (d) => catColor(d.data.cat)).style("fill", (d) => (d.data.hasHidden ? catColor(d.data.cat) : "var(--surface-1)"));
    nodeG.filter((d) => d.data.type === "paper").append("rect").attr("x", -R_PAPER).attr("y", -R_PAPER).attr("width", 2 * R_PAPER).attr("height", 2 * R_PAPER)
      .attr("transform", "rotate(45)").style("fill", (d) => deps.domainColor(d.data.node.domains[0]));
    nodeG.append("text").attr("class", "tree-label")
      .each(function (d) {
        const p = o.label(d);
        const text = d3.select(this).attr("x", p.x).attr("y", p.y).attr("text-anchor", p.anchor).attr("transform", p.rotate ? `rotate(${p.rotate})` : null);
        if (d.lines.length === 1) { text.text(d.lines[0]); return; }
        text.selectAll("tspan").data(d.lines).join("tspan").attr("x", p.x).attr("dy", (_, i) => (i ? LINE : 0)).text((s) => s);
      });
    nodeG.on("click", (ev, d) => { ev.stopPropagation(); activate(d); })
      .on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); activate(d); } })
      .on("mouseenter", (ev, d) => { if (d.data.type === "paper") g.selectAll(".tree-node.paper").classed("same", (x) => x.data.node.id === d.data.node.id); })
      .on("mouseleave", () => g.selectAll(".tree-node.paper").classed("same", false));
    renderDetail(counts);
    lastLayout = h;
    if (!state.transform) fit();
  }

  /**
   * ノードを選択する．分類は選択して展開・折りたたみ，論文は詳細パネルを開く．
   * @param {object} d - d3.hierarchy のノード．
   * @returns {void}
   */
  function activate(d) {
    if (d.data.type === "paper") { deps.onSelectPaper(d.data.node.id); return; }
    const id = d.data.id;
    state.selected = id;
    if (state.expanded.has(id) && id !== root.id) {
      state.expanded.delete(id);
      for (const c of tax.categories) if (ancestors(c.id).includes(id)) state.expanded.delete(c.id);
    } else state.expanded.add(id);
    render();
    reveal(id);
  }

  /**
   * 分類とその直下の項目が見える位置へ移動する（拡大率は保つ）．展開で樹形図が伸びても隠れない．
   * @param {string} id - 分類の ID．
   * @returns {void}
   */
  function reveal(id) {
    const d = lastLayout?.descendants().find((x) => x.data.id === id);
    if (!d) return;
    const { width, height } = container.getBoundingClientRect();
    const t = state.transform ?? d3.zoomIdentity;
    const o = orient();
    const boxes = [d, ...(d.children || [])].map(o.extent);
    const own = o.extent(d);
    const lo = (i) => Math.min(...boxes.map((b) => b[i])), hi = (i) => Math.max(...boxes.map((b) => b[i + 2]));
    const tx = shiftAxis(lo(0), hi(0), own[0], d.px, width, t.x, t.k, o.reveal.x);
    const ty = shiftAxis(lo(1), hi(1), own[1], d.py, height, t.y, t.k, o.reveal.y);
    if (tx !== t.x || ty !== t.y) svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(t.k));
  }

  /**
   * 1つの軸について，範囲 [lo, hi] が画面に入るような平行移動量を求める．
   * @param {number} lo - 範囲の始端（樹形図の座標）．
   * @param {number} hi - 範囲の終端．
   * @param {number} start - 親の分類の始端（範囲が画面より大きい場合に "start" で合わせる位置）．
   * @param {number} center - 親の分類の中心（同じく "center" で合わせる位置）．
   * @param {number} size - 画面の大きさ（px）．
   * @param {number} cur - 現在の平行移動量．
   * @param {number} k - 拡大率．
   * @param {"start"|"center"} mode - 範囲が画面より大きい場合の合わせ方．
   * @returns {number} 平行移動量．
   */
  function shiftAxis(lo, hi, start, center, size, cur, k, mode) {
    const sLo = k * lo + cur, sHi = k * hi + cur;
    if (sLo >= MARGIN && sHi <= size - MARGIN) return cur;
    if (k * (hi - lo) <= size - 2 * MARGIN) return sLo < MARGIN ? MARGIN - k * lo : size - MARGIN - k * hi;
    return mode === "start" ? 2 * MARGIN - k * start : size / 2 - k * center;
  }

  /**
   * 選択した分類の説明と所属論文の一覧を描く．
   * @param {Map<string, object[]>} counts - 分類ごとの所属ノード．
   * @returns {void}
   */
  function renderDetail(counts) {
    const controls = el("div", { class: "tree-controls" },
      orientationControl(),
      el("button", { type: "button", id: "tree-fit", onclick: fit }, "全体表示"),
      el("button", { type: "button", id: "tree-expand-all", onclick: () => { for (const c of tax.categories) state.expanded.add(c.id); render(); fit(); } }, "すべて展開"),
      el("button", { type: "button", id: "tree-reset", onclick: () => { state.expanded = new Set([root.id, ...root.children]); state.selected = null; render(); fit(); } }, "初期表示"),
      el("label", {}, (() => { const b = el("input", { type: "checkbox", id: "tree-show-papers", checked: state.showPapers });
        b.addEventListener("change", () => { state.showPapers = b.checked; render(); }); return b; })(), " 論文を表示"));
    const legend = el("p", { class: "note" }, "線は分類の親子関係（実線）と論文の所属（破線）のみを表す．技術的な発展関係は研究系譜図で確認する．◆複数所属 n は，その論文が n 個の分類に所属することを示す（同じ論文を別の論文として数えない）．");
    if (!state.selected) {
      detail.replaceChildren(controls, legend, el("p", { class: "note" }, "分類をクリックすると，説明と所属する論文の一覧を表示し，下位の分類を展開・折りたたみする．論文をクリックすると詳細パネルを表示する．"));
      return;
    }
    const c = byId.get(state.selected);
    const list = counts.get(c.id) || [];
    const path = [...ancestors(c.id)].reverse().map((id) => byId.get(id).name_ja);
    const item = (n) => {
      const others = (n.research_fields || []).filter((f) => f !== c.id && !ancestors(f).includes(c.id) && !ancestors(c.id).includes(f)).map((f) => byId.get(f)?.name_ja ?? f);
      return el("li", { "data-id": n.id },
        el("a", { class: "tree-paper-link", onclick: () => deps.onSelectPaper(n.id) }, n.short_name), `（${deps.yearLabel(n)}）`,
        others.length ? el("span", { class: "tag tree-multi" }, `他の所属: ${others.join("，")}`) : null, " ",
        el("button", { type: "button", class: "tree-to-map", onclick: () => deps.onShowOnMap(n.id) }, "系譜図で表示"));
    };
    detail.replaceChildren(controls, legend, el("div", { class: "path-box tree-category", "data-category": c.id },
      path.length ? el("div", { class: "note" }, path.join(" ＞ ")) : null,
      el("h2", {}, c.name_ja), el("p", { class: "full-title" }, c.name_en),
      el("p", {}, c.description), el("p", { class: "note" }, `分類基準: ${c.criteria}`),
      c.domain ? el("p", { class: "note" }, el("span", { class: "swatch", style: `background:${deps.domainColor(c.domain)}` }), ` 研究系譜図の分野: ${graph.domains.find((d) => d.id === c.domain).label}`) : el("p", { class: "note" }, "研究系譜図の特定の分野には対応しない（上位・横断的な分類）．"),
      c.children.length ? el("p", { class: "note" }, `下位の分類: ${c.children.map((id) => byId.get(id).name_ja).join("，")}`) : null,
      el("h3", {}, `所属する論文・手法 ${list.length} 件（下位の分類を含む）`),
      list.length ? el("ul", { class: "pt-list tree-list" }, list.map(item))
        : el("p", { class: "note" }, `収録した論文は無い（表示中の絞り込みの範囲）．${c.allow_empty ? "この分類の研究は存在するが，マップには未収録である．" : ""}`),
      list.length ? el("button", { type: "button", id: "tree-highlight", onclick: () => deps.onHighlight(list.map((n) => n.id), `分類: ${c.name_ja}（${list.length} 件）`) }, "研究系譜図で強調") : null));
  }

  /**
   * 表示中の樹形図が収まるように拡大する．横方向は根を左端・上下中央に，縦方向は根を上端・左右中央に置く．
   * @returns {void}
   */
  function fit() {
    const box = g.node().getBBox();
    const { width, height } = container.getBoundingClientRect();
    if (!box.width || !width) return;
    // スマートフォンの画面では読める大きさ（0.6倍）を下限とする（はみ出した部分はドラッグで移動する）．
    // 判定は画面全体の幅で行う（PC で詳細パネルにより描画領域が狭くなった場合は全体を収める）
    const phone = (container.ownerDocument.defaultView?.innerWidth ?? width) < 600;
    const k = Math.max(Math.min(1.4, (width - 2 * MARGIN) / box.width, (height - 2 * MARGIN) / box.height), phone ? 0.6 : 0.25);
    const t = state.orientation === "vertical"
      ? d3.zoomIdentity.translate(width / 2 - k * (box.x + box.width / 2), MARGIN - k * box.y).scale(k)
      : d3.zoomIdentity.translate(MARGIN - k * box.x, height / 2 - k * (box.y + box.height / 2)).scale(k);
    svg.call(zoom.transform, t);
  }

  /**
   * 表示方向を切り替える．展開・選択の状態は保ち，切り替え後に全体が収まるように位置と倍率を合わせる．
   * @param {"vertical"|"horizontal"} orientation - 表示方向．
   * @returns {void}
   */
  function setOrientation(orientation) {
    if (!ORIENTATIONS[orientation] || orientation === state.orientation) return;
    state.orientation = orientation;
    render();
    fit();
  }

  /**
   * 表示方向の切り替え（ラジオボタンの組）を作る．矢印キーでも切り替えられる．
   * @returns {HTMLElement} 切り替えの要素．
   */
  function orientationControl() {
    const keys = ["vertical", "horizontal"];
    const choose = (o) => {
      setOrientation(o);
      detail.querySelector(`#tree-orient-${o}`)?.focus();
    };
    const buttons = keys.map((o) => el("button", {
      type: "button", role: "radio", id: `tree-orient-${o}`, class: "tree-orient-option", "data-orientation": o,
      "aria-checked": String(state.orientation === o), tabindex: state.orientation === o ? "0" : "-1",
      onclick: () => choose(o),
      onkeydown: (ev) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
        if (!step) return;
        ev.preventDefault();
        choose(keys[(keys.indexOf(o) + step + keys.length) % keys.length]);
      },
    }, ORIENTATIONS[o].label_ja));
    return el("div", { class: "tree-orient", role: "radiogroup", "aria-label": "表示方向", id: "tree-orientation" },
      el("span", { class: "tree-orient-title" }, "表示方向："), buttons);
  }

  /**
   * 検索に一致した論文を強調し，その論文が所属する分類を展開する．
   * @param {Set<string>|null} ids - 一致した論文の ID（null で解除）．
   * @returns {void}
   */
  function setMatches(ids) {
    state.matches = ids;
    if (ids) for (const n of graph.nodes) if (ids.has(n.id)) for (const f of n.research_fields || []) for (const a of [f, ...ancestors(f)]) state.expanded.add(a);
    if (ids) state.showPapers = true;
    render();
  }

  /** 詳細パネルで選択中の論文の印を更新する（再描画しない）．@returns {void} */
  function markSelectedPaper() {
    const id = deps.selectedPaper?.();
    g.selectAll(".tree-node.paper").classed("selected", (d) => d.data.node.id === id);
  }

  return { render, setMatches, fit, reveal, setOrientation, markSelectedPaper, state };
}
