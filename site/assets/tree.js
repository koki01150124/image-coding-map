// Image Coding Map — 研究分野樹形図（D3 v7 の d3.tree による階層の表示）
//
// 樹形図の線は，分類の親子関係（実線）と，分類への論文の所属（破線）のみを表す．
// 技術的な派生関係は研究系譜図で表す．論文の情報は graph.nodes を参照し，複製しない．

const ROW = 26;          // 行の間隔（px）
const PAD = 44;          // 列の余白（ラベルの右端から次の列まで）
const R_CAT = 7, R_PAPER = 4.5;

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
 *   onSelectPaper(id)，onShowOnMap(id)，onHighlight(ids, label)）．
 * @returns {{render: function(): void, setMatches: function(Set<string>|null): void, fit: function(): void}}
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
  };
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
    d3.tree().nodeSize([ROW, 1]).separation((a, b) => (a.parent === b.parent ? 1 : 1.25))(h);
    // 列の幅は，その深さのラベルの最大幅から決める（ラベルと次の列のノードが重ならない）
    const widths = [];
    h.each((d) => {
      d.lw = deps.textWidth(labelOf(d, counts), d.data.type === "category");
      widths[d.depth] = Math.max(widths[d.depth] || 0, d.lw);
    });
    const xs = [0];
    for (let i = 1; i < widths.length; i++) xs[i] = xs[i - 1] + widths[i - 1] + PAD + 16;
    h.each((d) => { d.px = xs[d.depth]; d.py = d.x; });

    g.selectAll("*").remove();
    // 線は親のラベルの右端から子のノードへ引く（ラベルの文字に重ならない）
    const link = d3.linkHorizontal().x((p) => p[0]).y((p) => p[1]);
    g.append("g").attr("class", "tree-links").selectAll("path").data(h.links()).join("path")
      .attr("class", (l) => `tree-link ${l.target.data.type}`)
      .attr("d", (l) => link({ source: [l.source.px + 12 + l.source.lw + 6, l.source.py], target: [l.target.px - (l.target.data.type === "paper" ? R_PAPER + 2 : R_CAT + 1), l.target.py] }));
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
    nodeG.append("text").attr("class", "tree-label").attr("x", (d) => (d.data.type === "paper" ? 10 : 12)).attr("y", 4)
      .text((d) => labelOf(d, counts));
    nodeG.on("click", (ev, d) => { ev.stopPropagation(); activate(d); })
      .on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); activate(d); } })
      .on("mouseenter", (ev, d) => { if (d.data.type === "paper") g.selectAll(".tree-node.paper").classed("same", (x) => x.data.node.id === d.data.node.id); })
      .on("mouseleave", () => g.selectAll(".tree-node.paper").classed("same", false));
    renderDetail(counts);
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
   * 分類とその直下の項目が見える位置へ移動する（拡大率は保つ）．展開で樹形図が右へ伸びても隠れない．
   * @param {string} id - 分類の ID．
   * @returns {void}
   */
  function reveal(id) {
    const d = g.selectAll(".tree-node").filter((x) => x.data.id === id).datum();
    if (!d) return;
    const { width, height } = container.getBoundingClientRect();
    const t = state.transform ?? d3.zoomIdentity;
    const kids = d.children || [];
    const ys = [d.py, ...kids.map((c) => c.py)];
    const xMax = Math.max(d.px, ...kids.map((c) => c.px)) + 180;
    let tx = t.x, ty = t.y;
    if (t.applyX(d.px) < 30 || t.applyX(xMax) > width - 20) tx = Math.min(40 - t.k * d.px, width - 20 - t.k * xMax);
    if (t.applyX(d.px) + (tx - t.x) < 30) tx = 40 - t.k * d.px;
    const yMid = (Math.min(...ys) + Math.max(...ys)) / 2;
    if (t.applyY(Math.min(...ys)) < 20 || t.applyY(Math.max(...ys)) > height - 20) ty = height / 2 - t.k * yMid;
    if (tx !== t.x || ty !== t.y) svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(t.k));
  }

  /**
   * 選択した分類の説明と所属論文の一覧を描く．
   * @param {Map<string, object[]>} counts - 分類ごとの所属ノード．
   * @returns {void}
   */
  function renderDetail(counts) {
    const controls = el("div", { class: "tree-controls" },
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

  /** 表示中の樹形図が収まるように拡大する．@returns {void} */
  function fit() {
    const box = g.node().getBBox();
    const { width, height } = container.getBoundingClientRect();
    if (!box.width || !width) return;
    // 狭い画面では読める大きさ（0.6倍）を下限とし，根を左端に置く（右側はドラッグで移動する）
    const k = Math.max(Math.min(1.4, (width - 40) / box.width, (height - 40) / box.height), width < 600 ? 0.6 : 0.25);
    const t = d3.zoomIdentity.translate(20 - k * box.x, height / 2 - k * (box.y + box.height / 2)).scale(k);
    svg.call(zoom.transform, t);
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

  return { render, setMatches, fit, reveal, state };
}
