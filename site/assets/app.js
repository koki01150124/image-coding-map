// Image Coding Map — 描画と操作（D3 v7）
//
// data/graph.json のみを読み込み，論文の内容・分野・エッジ種別は全てデータから決まる．
// 論文を追加する場合に本ファイルを変更する必要は無い．
import { computeLayout, regionPath, edgePath, LAYOUT } from "./layout.js";
import { patternStatus, countTable, heatLevel } from "./patterns.js";

const d3 = window.d3;
const MAX_COMPARE = 3;
const THEMES = ["auto", "light", "dark"];
const THEME_LABEL = { auto: "自動", light: "ライト", dark: "ダーク" };

const state = {
  graph: null,
  byId: new Map(),
  layout: null,
  hiddenDomains: new Set(),
  hiddenEdgeTypes: new Set(),
  yearMin: -Infinity,
  yearMax: Infinity,
  pathMode: "lineage",
  selected: null,
  compare: [],
  path: null,
  matches: null,
  matchLabel: null,
  patternAxis: "improvements",
  patternKinds: new Set(["paper"]),
  patternCell: null,
  themeMode: "auto",
  zoom: null,
  playTimer: null,
};

const $ = (id) => document.getElementById(id);
const els = {
  graph: $("graph"), panel: $("panel"), panelBody: $("panel-body"), tooltip: $("tooltip"), status: $("status"),
  search: $("search-input"), searchList: $("search-list"), searchCount: $("search-count"),
  domainLegend: $("domain-legend"), edgeLegend: $("edge-legend"), year: $("year-slider"), yearOut: $("year-out"),
  play: $("btn-play"), focusNote: $("focus-note"), list: $("list-view"), compare: $("compare-view"),
  btnList: $("btn-list"), btnCompare: $("btn-compare"), btnTheme: $("btn-theme"),
  patterns: $("pattern-view"), btnPatterns: $("btn-patterns"),
};

// ---------------------------------------------------------------- 汎用

/**
 * DOM 要素を作る（文字列の子は textContent として扱うため HTML として解釈されない）．
 * @param {string} tag - タグ名．
 * @param {object} attrs - 属性．on* は イベント，class は className として扱う．
 * @param {...(Node|string|null)} children - 子要素．
 * @returns {HTMLElement} 作成した要素．
 */
function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "class") e.className = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c != null) e.append(c instanceof Node ? c : String(c));
  return e;
}

/** URL が http(s) の場合のみ返す．@param {string|null} u @returns {string|null} */
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
/** 分野ID → 分野．@param {string} id @returns {object} */
const domainOf = (id) => state.graph.domains.find((d) => d.id === id);
/** エッジ種別ID → 定義．@param {string} id @returns {object} */
const edgeTypeOf = (id) => state.graph.edge_types.find((t) => t.id === id);
/** 語彙のラベル．@param {string} kind @param {string} id @returns {string} */
const vocabLabel = (kind, id) => state.graph.vocab[kind]?.[id] ?? id;
/**
 * 一覧・ツールチップ用の年の表示（未公開研究は発表年として表示しない）．
 * @param {object} n - ノード．
 * @returns {string}
 */
function yearLabel(n) {
  if (n.year_basis === "unpublished_placement") return "未公開";
  if (n.year_basis === "scheme_first_use") return `構成例・${n.year}〜`;
  return String(n.year);
}

/**
 * 詳細パネル・比較表用の年の説明（年代軸の基準，初出，正式掲載）．
 * @param {object} n - ノード．
 * @returns {HTMLElement}
 */
function yearDetail(n) {
  const pub = n.publication || {};
  const line = (label, p) => el("div", {}, `${label}: `, p ? `${p.year}（${p.venue}）` : unverified(),
    p ? el("span", { class: "note" }, ` 根拠: ${p.evidence}`) : null);
  const parts = [];
  if (n.year_basis === "unpublished_placement") {
    parts.push(el("div", {}, "発表年: 未公開"), el("div", { class: "note" }, `年代軸の位置: ${n.year}（${vocabLabel("year_basis", n.year_basis)}）`));
  } else if (n.year_basis === "scheme_first_use") {
    parts.push(el("div", {}, `年代軸の年: ${n.year}（${vocabLabel("year_basis", n.year_basis)}）`));
  } else {
    parts.push(el("div", {}, `年代軸の年: ${n.year}（${vocabLabel("year_basis", n.year_basis)}）`), line("初出", pub.first_public));
    if (n.kind !== "software") parts.push(line("正式掲載", pub.formal));
  }
  if (n.year_note) parts.push(el("div", { class: "note" }, n.year_note));
  return el("div", {}, parts);
}

/** 未確認の表示．@returns {HTMLElement} */
const unverified = () => el("span", { class: "unverified" }, "未確認");

/**
 * 状態表示を一定時間出す．
 * @param {string} msg - 表示する文．
 * @param {number} ms - 表示時間（0 の場合は消さない）．
 * @returns {void}
 */
function setStatus(msg, ms = 2500) {
  els.status.textContent = msg;
  if (ms) setTimeout(() => { if (els.status.textContent === msg) els.status.textContent = ""; }, ms);
}

// ---------------------------------------------------------------- データ

/**
 * graph.json を読み込み，索引を作る．
 * @returns {Promise<void>}
 */
async function loadGraph() {
  const res = await fetch("data/graph.json", { cache: "no-cache" });
  if (!res.ok) throw new Error(`graph.json を読み込めない（HTTP ${res.status}）`);
  state.graph = await res.json();
  state.byId = new Map(state.graph.nodes.map((n) => [n.id, n]));
}

/** ノードが現在の絞り込みで表示されるか．@param {object} n @returns {boolean} */
const isNodeVisible = (n) => n.year >= state.yearMin && n.year <= state.yearMax && n.domains.some((d) => !state.hiddenDomains.has(d));
/** エッジが表示されるか．@param {object} e @returns {boolean} */
const isEdgeVisible = (e) => !state.hiddenEdgeTypes.has(e.type) && isNodeVisible(state.byId.get(e.source)) && isNodeVisible(state.byId.get(e.target));

/**
 * 分野の色を CSS 変数として注入する（ライト・ダークの両方）．
 * @param {object[]} domains - 分野の定義．
 * @returns {void}
 */
function injectDomainColors(domains) {
  const light = domains.map((d) => `--d-${d.id}: ${d.color.light};`).join(" ");
  const dark = domains.map((d) => `--d-${d.id}: ${d.color.dark};`).join(" ");
  const css = `:root { ${light} }
@media (prefers-color-scheme: dark) { :root:where(:not([data-theme="light"])) { ${dark} } }
:root[data-theme="dark"] { ${dark} }`;
  document.head.append(el("style", { id: "domain-colors" }, css));
}
/** 分野の色の CSS 値．@param {string} id @returns {string} */
const domainColor = (id) => `var(--d-${id})`;

// ---------------------------------------------------------------- 描画

const measureCtx = document.createElement("canvas").getContext("2d");
/**
 * ラベルの描画幅を実測する．
 * @param {string} s - ラベル．
 * @returns {number} 幅（px）．
 */
function measureLabel(s) {
  measureCtx.font = `11.5px ${getComputedStyle(document.body).fontFamily}`;
  return measureCtx.measureText(s).width;
}

let svg, root, layers;

/**
 * SVG の骨格とズーム操作を作る．
 * @returns {void}
 */
function setupSvg() {
  svg = d3.select(els.graph).append("svg").attr("role", "img").attr("aria-label", "研究系譜マップ");
  const defs = svg.append("defs");
  defs.append("marker").attr("id", "arrow").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5)
    .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto-start-reverse")
    .append("path").attr("class", "arrow-head").attr("d", "M0,0L10,5L0,10z");
  defs.append("marker").attr("id", "arrow-hl").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5)
    .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto-start-reverse")
    .append("path").attr("d", "M0,0L10,5L0,10z").style("fill", "var(--highlight)");
  defs.append("marker").attr("id", "arrow-rel").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5)
    .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto-start-reverse")
    .append("path").attr("d", "M0,0L10,5L0,10z").style("fill", "var(--path-related)");
  root = svg.append("g").attr("class", "zoom-root");
  layers = {};
  for (const name of ["bands", "regions", "rows", "edges", "nodes", "labels"]) layers[name] = root.append("g").attr("class", `layer-${name}`);
  state.zoom = d3.zoom().scaleExtent([0.15, 5]).on("zoom", (ev) => root.attr("transform", ev.transform));
  svg.call(state.zoom).on("dblclick.zoom", null);
  svg.on("click", (ev) => { if (ev.target === svg.node()) select(null); });
}

/**
 * 分野の列（背景）と年の行（軸）を描く．
 * @returns {void}
 */
function renderFrame() {
  const L = state.layout;
  const bands = layers.bands.selectAll("g.col").data(L.columns, (c) => c.id).join((enter) => {
    const g = enter.append("g").attr("class", "col");
    g.append("rect").attr("class", (c, i) => `col-band${i % 2 ? " alt" : ""}`);
    g.append("rect").attr("class", "col-mark").attr("height", 4).attr("rx", 2);
    g.append("text").attr("class", "col-label").attr("text-anchor", "middle");
    return g;
  });
  bands.select(".col-band").attr("x", (c) => c.x0).attr("y", 0).attr("width", (c) => c.x1 - c.x0).attr("height", L.height);
  bands.select(".col-mark").attr("x", (c) => c.x0 + 16).attr("y", 40).attr("width", (c) => c.x1 - c.x0 - 32).style("fill", (c) => domainColor(c.id));
  bands.select(".col-label").attr("x", (c) => c.cx).attr("y", 30).text((c) => c.label);

  const rows = layers.rows.selectAll("g.row").data(L.rows, (r) => r.year).join((enter) => {
    const g = enter.append("g").attr("class", "row");
    g.append("line").attr("class", "row-line");
    g.append("text").attr("class", "row-label").attr("text-anchor", "end");
    return g;
  });
  rows.select(".row-line").attr("x1", LAYOUT.axisWidth - 4).attr("x2", L.width).attr("y1", (r) => r.y1).attr("y2", (r) => r.y1);
  rows.select(".row-label").attr("x", LAYOUT.axisWidth - 10).attr("y", (r) => r.cy + 4).text((r) => r.year);
}

/**
 * 分野の範囲（凸包）を描く．範囲の重なりが分野の重なりを表す．
 * @returns {void}
 */
function renderRegions() {
  const L = state.layout;
  const data = state.graph.domains.map((d) => ({
    id: d.id,
    path: regionPath(state.graph.nodes.filter((n) => n.domains.includes(d.id) && isNodeVisible(n)).map((n) => n.id), L.pos, L.width, L.height, d3),
  })).filter((d) => d.path && !state.hiddenDomains.has(d.id));
  layers.regions.selectAll("path.region").data(data, (d) => d.id).join("path")
    .attr("class", "region").attr("data-domain", (d) => d.id).attr("d", (d) => d.path)
    .style("fill", (d) => domainColor(d.id)).style("stroke", (d) => domainColor(d.id));
}

/**
 * エッジを描く．系譜（derived_from，builds_on）は元の手法から新しい手法への矢印とする．
 * @returns {void}
 */
function renderEdges() {
  const L = state.layout;
  const edges = state.graph.edges.filter(isEdgeVisible);
  const key = (e) => `${e.source}>${e.target}>${e.type}`;
  const pathOf = (e) => edgePath(L.pos.get(e.target), L.pos.get(e.source), LAYOUT.radius + 2);
  const g = layers.edges.selectAll("g.edge-g").data(edges, key).join((enter) => {
    const gg = enter.append("g").attr("class", "edge-g");
    gg.append("path").attr("class", (e) => `edge ${e.type}`);
    gg.append("path").attr("class", "edge-hit")
      .on("mousemove", (ev, e) => showEdgeTooltip(ev, e)).on("mouseleave", hideTooltip)
      .on("click", (ev, e) => { ev.stopPropagation(); select(e.source, { zoomTo: false }); });
    return gg;
  });
  g.select("path.edge").attr("d", pathOf).attr("data-key", key)
    .attr("marker-end", (e) => (edgeTypeOf(e.type).lineage ? "url(#arrow)" : null));
  g.select("path.edge-hit").attr("d", pathOf);
}

/**
 * ノード（形・外周の分野リング）とラベルを描く．
 * @returns {void}
 */
function renderNodes() {
  const L = state.layout;
  const r = LAYOUT.radius;
  const nodes = state.graph.nodes.filter(isNodeVisible);
  const arc = d3.arc().innerRadius(r + 2).outerRadius(r + 6);
  const pie = d3.pie().value(1).sort(null);
  const g = layers.nodes.selectAll("g.node").data(nodes, (n) => n.id).join((enter) => {
    const gg = enter.append("g").attr("tabindex", 0).attr("role", "button");
    gg.append("circle").attr("class", "halo").attr("r", r + 9).style("fill", "none");
    gg.each(function (n) {
      const node = d3.select(this);
      if (n.domains.length > 1) {
        node.selectAll("path.ring").data(pie(n.domains)).join("path").attr("class", "ring").attr("d", arc)
          .style("fill", (a) => domainColor(a.data));
      }
      const shape = n.kind === "standard" || n.kind === "software"
        ? node.append("rect").attr("x", -r).attr("y", -r).attr("width", 2 * r).attr("height", 2 * r).attr("rx", 3)
        : node.append("circle").attr("r", r);
      shape.attr("class", "core").style("fill", domainColor(n.domains[0]));
    });
    gg.on("click", (ev, n) => { ev.stopPropagation(); select(n.id); })
      .on("keydown", (ev, n) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n.id); } })
      .on("mousemove", (ev, n) => showNodeTooltip(ev, n)).on("mouseleave", hideTooltip);
    return gg;
  });
  g.attr("class", (n) => `node ${n.kind}`).attr("data-id", (n) => n.id)
    .attr("aria-label", (n) => `${n.short_name}（${yearLabel(n)}）`)
    .attr("transform", (n) => `translate(${L.pos.get(n.id).x},${L.pos.get(n.id).y})`);
  layers.labels.selectAll("text.label").data(nodes, (n) => n.id).join("text")
    .attr("class", "label").attr("data-id", (n) => n.id)
    .attr("x", (n) => L.pos.get(n.id).x + r + 8).attr("y", (n) => L.pos.get(n.id).y + 4)
    .text((n) => n.short_name);
}

/**
 * 表示全体を更新する（絞り込みの変更時）．
 * @returns {void}
 */
function renderAll() {
  renderRegions();
  renderEdges();
  renderNodes();
  applyFocus();
  if (els.patterns && !els.patterns.hidden) renderPatterns();
}

// ---------------------------------------------------------------- 強調・選択

/**
 * 選択・経路・検索・比較の状態に応じて強調と減光を適用する．
 * @returns {void}
 */
function applyFocus() {
  const sel = state.selected;
  const path = state.path;
  let keepNodes = null, keepEdges = null;
  if (path) {
    keepNodes = new Set(path.nodes);
    keepEdges = new Set(path.edges);
  } else if (sel) {
    keepNodes = new Set([sel]);
    keepEdges = new Set();
    for (const e of state.graph.edges.filter(isEdgeVisible)) {
      if (e.source === sel || e.target === sel) { keepNodes.add(e.source); keepNodes.add(e.target); keepEdges.add(`${e.source}>${e.target}>${e.type}`); }
    }
  } else if (state.matches) {
    keepNodes = state.matches;
    keepEdges = new Set();
  }
  layers.nodes.selectAll("g.node")
    .classed("dim", (n) => keepNodes != null && !keepNodes.has(n.id))
    .classed("selected", (n) => n.id === sel && !path)
    .classed("path-on", (n) => path != null && path.mode === "lineage" && keepNodes.has(n.id))
    .classed("path-rel", (n) => path != null && path.mode === "related" && keepNodes.has(n.id))
    .classed("compare", (n) => state.compare.includes(n.id) && n.id !== sel)
    .classed("match", (n) => state.matches != null && state.matches.has(n.id));
  layers.labels.selectAll("text.label").classed("dim", (n) => keepNodes != null && !keepNodes.has(n.id));
  layers.edges.selectAll("path.edge")
    .classed("dim", function () { return keepEdges != null && !keepEdges.has(this.dataset.key); })
    .classed("path-on", function () { return path != null && path.mode === "lineage" && keepEdges.has(this.dataset.key); })
    .classed("path-rel", function () { return path != null && path.mode === "related" && keepEdges.has(this.dataset.key); })
    .attr("marker-end", function (e) {
      if (!edgeTypeOf(e.type).lineage) return null;
      if (path == null || !keepEdges.has(this.dataset.key)) return "url(#arrow)";
      return path.mode === "lineage" ? "url(#arrow-hl)" : "url(#arrow-rel)";
    });
  updateFocusNote();
}

/**
 * 強調の状態を説明する注記を更新する．
 * @returns {void}
 */
function updateFocusNote() {
  const note = els.focusNote;
  note.replaceChildren();
  let text = null;
  if (state.path) text = state.path.label;
  else if (state.selected) text = `選択中: ${state.byId.get(state.selected).short_name}（直接の関係のみ強調）`;
  else if (state.matches) text = state.matchLabel ?? `検索: ${state.matches.size} 件を強調`;
  note.hidden = !text;
  if (!text) return;
  note.append(text, el("button", { type: "button", onclick: clearFocus }, "解除"));
}

/** 選択・経路・検索の強調を全て解除する．@returns {void} */
function clearFocus() {
  state.path = null;
  state.matches = null;
  state.matchLabel = null;
  els.search.value = "";
  els.searchCount.textContent = "";
  select(null);
}

/**
 * ノードを選択して詳細パネルを開く（null で解除）．
 * @param {string|null} id - ノードID．
 * @param {{zoomTo?: boolean, updateHash?: boolean}} opts - ズームするか，URL を更新するか．
 * @returns {void}
 */
function select(id, { zoomTo = false, updateHash = true } = {}) {
  state.selected = id && state.byId.has(id) ? id : null;
  if (state.selected) state.path = null;
  if (state.selected && !isNodeVisible(state.byId.get(state.selected))) revealNode(state.byId.get(state.selected));
  applyFocus();
  renderPanel();
  if (updateHash) writeHash();
  if (state.selected && zoomTo) {
    const ids = new Set([state.selected]);
    for (const e of state.graph.edges.filter(isEdgeVisible)) {
      if (e.source === state.selected) ids.add(e.target);
      if (e.target === state.selected) ids.add(e.source);
    }
    zoomToNodes([...ids], 1.3);
  }
}

/**
 * 絞り込みで隠れているノードを表示できるよう，分野と年の絞り込みを緩める．
 * @param {object} n - ノード．
 * @returns {void}
 */
function revealNode(n) {
  if (n.year > state.yearMax) setYearMax(Infinity);
  if (!n.domains.some((d) => !state.hiddenDomains.has(d))) state.hiddenDomains.delete(n.domains[0]);
  syncLegend();
  renderAll();
}

/**
 * 指定したノードが収まるようにズームする．
 * @param {string[]} ids - ノードID．空の場合は全体．
 * @param {number} maxScale - 最大の拡大率．
 * @param {boolean} fitWhole - 全体の場合に高さも収めるか（false では幅に合わせて上端から表示）．
 * @returns {void}
 */
function zoomToNodes(ids, maxScale = 1.2, fitWhole = true) {
  const L = state.layout;
  const pts = (ids.length ? ids : state.graph.nodes.filter(isNodeVisible).map((n) => n.id)).map((id) => L.pos.get(id));
  const { width, height } = els.graph.getBoundingClientRect();
  if (!pts.length || !width) return;
  const all = !ids.length;
  const x0 = all ? 0 : d3.min(pts, (p) => p.x) - 120, x1 = all ? L.width : d3.max(pts, (p) => p.x) + 160;
  const y0 = all ? 0 : d3.min(pts, (p) => p.y) - 80, y1 = all ? L.height : d3.max(pts, (p) => p.y) + 80;
  const panelW = els.panel.hidden ? 0 : Math.min(460, width * 0.4);
  const fitH = all && !fitWhole ? Infinity : (height - 20) / (y1 - y0);
  const k = Math.min(maxScale, (width - panelW - 20) / (x1 - x0), fitH);
  const ty = all && !fitWhole ? 10 - k * y0 : height / 2 - k * (y0 + y1) / 2;
  const t = d3.zoomIdentity.translate((width - panelW) / 2 - k * (x0 + x1) / 2, ty).scale(k);
  svg.transition().duration(450).call(state.zoom.transform, t);
}

// ---------------------------------------------------------------- ツールチップ

/**
 * ツールチップの位置を合わせる．
 * @param {MouseEvent} ev - マウスイベント．
 * @returns {void}
 */
function placeTooltip(ev) {
  const box = els.graph.getBoundingClientRect();
  const tt = els.tooltip;
  let x = ev.clientX - box.left + 14, y = ev.clientY - box.top + 14;
  if (x + tt.offsetWidth > box.width - 8) x = ev.clientX - box.left - tt.offsetWidth - 14;
  if (y + tt.offsetHeight > box.height - 8) y = ev.clientY - box.top - tt.offsetHeight - 14;
  tt.style.left = `${x}px`;
  tt.style.top = `${y}px`;
}

/** ノードのツールチップ．@param {MouseEvent} ev @param {object} n @returns {void} */
function showNodeTooltip(ev, n) {
  els.tooltip.replaceChildren(
    el("div", { class: "tt-title" }, `${n.short_name}（${yearLabel(n)}）`),
    el("div", {}, n.bibliography.title ?? vocabLabel("kind", n.kind)),
    el("div", { class: "tt-sub" }, n.domains.map((d) => domainOf(d).short).join(" ／ ")),
  );
  els.tooltip.hidden = false;
  placeTooltip(ev);
}

/** エッジのツールチップ．@param {MouseEvent} ev @param {object} e @returns {void} */
function showEdgeTooltip(ev, e) {
  const s = state.byId.get(e.source), t = state.byId.get(e.target);
  const verb = { derived_from: "は次を改良・発展", builds_on: "は次の技術・モデルを利用", related: "と次は共通の研究課題", compared_with: "は次を比較対象とした" }[e.type] ?? "→";
  els.tooltip.replaceChildren(
    el("div", { class: "tt-title" }, `${edgeTypeOf(e.type).label}`),
    el("div", {}, `${s.short_name} ${verb}: ${t.short_name}`),
    el("div", {}, e.note),
    el("div", { class: "tt-sub" }, `根拠（${vocabLabel("evidence", e.evidence.kind)}）: ${e.evidence.detail}`),
  );
  els.tooltip.hidden = false;
  placeTooltip(ev);
}
/** ツールチップを隠す．@returns {void} */
function hideTooltip() { els.tooltip.hidden = true; }

// ---------------------------------------------------------------- 詳細パネル

/**
 * 値または未確認の表示を返す．
 * @param {*} v - 値（null は未確認）．
 * @param {function} fmt - 値を表示に変換する関数．
 * @returns {Node|string}
 */
function orUnverified(v, fmt = (x) => x) {
  if (v == null) return unverified();
  if (Array.isArray(v) && v.length === 0) return "該当なし";
  return fmt(v);
}

/** 文字列の配列を箇条書きにする．@param {string[]|null} items @returns {Node} */
const bulletList = (items) => (items == null ? unverified() : items.length ? el("ul", {}, items.map((s) => el("li", {}, s))) : el("span", {}, "該当なし"));

/**
 * 論文への外部リンクを作る．
 * @param {object} n - ノード．
 * @returns {HTMLElement}
 */
function linkButtons(n) {
  const b = n.bibliography;
  const links = [];
  const seen = new Set();
  const add = (label, url) => {
    if (!safeUrl(url) || seen.has(url)) return;
    seen.add(url);
    links.push(el("a", { href: url, target: "_blank", rel: "noopener" }, label));
  };
  add("原論文", b.url);
  if (b.arxiv) add(`arXiv:${b.arxiv}`, `https://arxiv.org/abs/${b.arxiv}`);
  if (b.doi && !/^10\.48550\/arxiv/i.test(b.doi)) add("DOI", `https://doi.org/${b.doi}`);
  if (n.code_url) add("コード", n.code_url);
  if (b.title) add("Google Scholar", `https://scholar.google.com/scholar?q=${encodeURIComponent(`"${b.title}"`)}`);
  return links.length ? el("div", { class: "links" }, links) : el("p", { class: "note" }, "外部リンク: なし（論文として公開されていない）");
}

/**
 * 関係の一覧（出る関係・入る関係）を作る．
 * @param {object} n - ノード．
 * @returns {HTMLElement[]}
 */
function relationSections(n) {
  const out = state.graph.edges.filter((e) => e.source === n.id);
  const inc = state.graph.edges.filter((e) => e.target === n.id);
  const item = (e, otherId, prefix) => el("li", { class: "rel-item" },
    `${prefix}`, el("a", { onclick: () => select(otherId, { zoomTo: true }) }, state.byId.get(otherId).short_name),
    `：${e.note} `, el("span", { class: "ev" }, `［${vocabLabel("evidence", e.evidence.kind)}］`));
  const sections = [];
  for (const t of state.graph.edge_types) {
    const o = out.filter((e) => e.type === t.id), i = inc.filter((e) => e.type === t.id);
    if (!o.length && !i.length) continue;
    const reverse = { derived_from: "改良・発展先 ← ", builds_on: "利用された先 ← ", related: "", compared_with: "比較された先 ← " }[t.id];
    sections.push(el("h3", {}, t.label), el("ul", {}, o.map((e) => item(e, e.target, "")), i.map((e) => item(e, e.source, reverse))));
  }
  return sections.length ? sections : [el("h3", {}, "関係"), el("p", { class: "note" }, "登録された関係は無い．")];
}

/**
 * 詳細パネルを描く．
 * @returns {void}
 */
function renderPanel() {
  const n = state.selected ? state.byId.get(state.selected) : null;
  els.panel.hidden = !n;
  if (!n) return;
  const b = n.bibliography;
  const inCompare = state.compare.includes(n.id);
  els.panelBody.replaceChildren(
    el("h2", {}, n.short_name),
    b.title ? el("p", { class: "full-title" }, b.title) : null,
    el("div", {}, n.domains.map((d, i) => el("span", { class: "tag" }, el("span", { class: "swatch", style: `background:${domainColor(d)}` }), `${domainOf(d).label}${i === 0 && n.domains.length > 1 ? "（主）" : ""}`)),
      (n.tags || []).map((t) => el("span", { class: "tag" }, `#${t}`))),
    linkButtons(n),
    el("dl", {},
      el("dt", {}, "種別"), el("dd", {}, vocabLabel("kind", n.kind)),
      el("dt", {}, "年"), el("dd", {}, yearDetail(n)),
      el("dt", {}, "著者"), el("dd", {}, orUnverified(b.authors, (a) => a.join(", "))),
      el("dt", {}, "掲載先（登録した版）"), el("dd", {}, orUnverified(b.venue)),
      el("dt", {}, "DOI"), el("dd", {}, orUnverified(b.doi)),
      el("dt", {}, "arXiv"), el("dd", {}, orUnverified(b.arxiv)),
      el("dt", {}, "情報源表現"), el("dd", {}, orUnverified(n.source_representation)),
      el("dt", {}, "通信路モデル"), el("dd", {}, orUnverified(n.channel_models, (c) => c.map((x) => vocabLabel("channel_models", x)).join("，"))),
      el("dt", {}, "区分"), el("dd", {}, orUnverified(n.transmission, (t) => vocabLabel("transmission", t))),
      el("dt", {}, "通信路を含む共同学習"), el("dd", {}, orUnverified(n.joint_channel_training, (b) => (b ? "あり" : "なし"))),
      el("dt", {}, "学習方法"), el("dd", {}, orUnverified(n.training)),
      el("dt", {}, "評価指標"), el("dd", {}, orUnverified(n.metrics, (m) => m.join("，"))),
    ),
    el("h3", {}, "主要な技術的貢献"), bulletList(n.contributions),
    el("h3", {}, "長所"), bulletList(n.strengths),
    el("h3", {}, "制約・弱点"), bulletList(n.limitations),
    ...relationSections(n),
    ...patternSections(n),
    el("h3", {}, "確認した範囲"),
    el("p", { class: "note" }, `${vocabLabel("read_level", n.verification.read_level)}．${n.verification.notes}`),
    el("p", { class: "note" }, `書誌情報の出典: ${b.source}`),
    el("div", { class: "panel-actions" },
      el("button", { type: "button", onclick: () => toggleCompare(n.id) }, inCompare ? "比較から外す" : `比較に追加（${state.compare.length}/${MAX_COMPARE}）`),
      el("button", { type: "button", onclick: () => copyLink(n.id) }, "この論文へのリンクをコピー"),
    ),
  );
}

/**
 * 論文への直接リンクをクリップボードにコピーする．
 * @param {string} id - ノードID．
 * @returns {Promise<void>}
 */
async function copyLink(id) {
  const url = `${location.origin}${location.pathname}#${id}`;
  try { await navigator.clipboard.writeText(url); setStatus("リンクをコピーした"); } catch { setStatus(url, 6000); }
}

// ---------------------------------------------------------------- 凡例・絞り込み

/**
 * 分野とエッジ種別の凡例（絞り込みボタン）を作る．
 * @returns {void}
 */
function buildLegend() {
  els.domainLegend.replaceChildren(...state.graph.domains.map((d) => {
    const count = state.graph.nodes.filter((n) => n.domains.includes(d.id)).length;
    const btn = el("button", { type: "button", class: "chip", "data-domain": d.id, "aria-pressed": "true", title: `${d.description}（クリックで表示/非表示，ホバーで範囲を強調）` },
      el("span", { class: "swatch", style: `background:${domainColor(d.id)}` }), `${d.short} ${count}`);
    btn.addEventListener("click", () => { toggleSet(state.hiddenDomains, d.id); syncLegend(); renderAll(); writeHash(); });
    btn.addEventListener("mouseenter", () => layers.regions.selectAll("path.region").classed("emph", (r) => r.id === d.id));
    btn.addEventListener("mouseleave", () => layers.regions.selectAll("path.region").classed("emph", false));
    return el("li", {}, btn);
  }));
  els.edgeLegend.replaceChildren(...state.graph.edge_types.map((t) => {
    const sample = `<svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" class="edge ${t.id}"/></svg>`;
    const btn = el("button", { type: "button", class: "chip", "data-edge-type": t.id, "aria-pressed": "true", title: t.description });
    btn.innerHTML = sample;
    btn.append(`${t.label}（${state.graph.edges.filter((e) => e.type === t.id).length}）`);
    btn.addEventListener("click", () => { toggleSet(state.hiddenEdgeTypes, t.id); syncLegend(); renderAll(); });
    return el("li", {}, btn);
  }));
}

/** 集合の要素の有無を反転する．@param {Set} s @param {*} v @returns {void} */
function toggleSet(s, v) { if (s.has(v)) s.delete(v); else s.add(v); }

/** 凡例ボタンの押下状態を状態に合わせる．@returns {void} */
function syncLegend() {
  els.domainLegend.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(!state.hiddenDomains.has(b.dataset.domain))));
  els.edgeLegend.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(!state.hiddenEdgeTypes.has(b.dataset.edgeType))));
}

/**
 * 年スライダーの値を設定する．
 * @param {number} y - 表示する最後の年（Infinity は全期間）．
 * @returns {void}
 */
function setYearMax(y) {
  const years = state.layout.rows.map((r) => r.year);
  const max = years[years.length - 1];
  state.yearMax = y >= max ? Infinity : y;
  els.year.value = String(Math.min(y, max));
  els.yearOut.textContent = state.yearMax === Infinity ? "全期間" : `〜${state.yearMax}`;
}

/** 年スライダーと再生ボタンを準備する．@returns {void} */
function setupYearSlider() {
  const years = state.layout.rows.map((r) => r.year);
  els.year.min = String(years[0]);
  els.year.max = String(years[years.length - 1]);
  els.year.step = "1";
  setYearMax(Infinity);
  els.year.addEventListener("input", () => { stopPlay(); setYearMax(Number(els.year.value)); renderAll(); });
  els.play.addEventListener("click", () => (state.playTimer ? stopPlay() : startPlay(years.filter((y) => y >= state.yearMin))));
}

/** 年を進めながら表示する．@param {number[]} years @returns {void} */
function startPlay(years) {
  let i = 0;
  els.play.textContent = "■ 停止";
  const step = () => {
    setYearMax(years[i]);
    renderAll();
    i += 1;
    if (i >= years.length) stopPlay();
  };
  step();
  state.playTimer = setInterval(step, 650);
}
/** 再生を止める．@returns {void} */
function stopPlay() {
  clearInterval(state.playTimer);
  state.playTimer = null;
  els.play.textContent = "▶ 再生";
}

/** 表示期間の選択肢（開始年）．データの年の範囲に含まれるものだけを用いる．@type {number[]} */
const PERIOD_STARTS = [2015, 2020];

/**
 * 表示期間（指定した年以降）の選択を準備する．選択すると該当期間の論文が収まるように拡大する．
 * @returns {void}
 */
function setupPeriod() {
  const sel = $("period-select");
  const years = state.layout.rows.map((r) => r.year);
  const opts = [el("option", { value: "" }, "全期間")];
  for (const y of PERIOD_STARTS) if (y > years[0] && y <= years[years.length - 1]) opts.push(el("option", { value: String(y) }, `${y}年以降`));
  sel.replaceChildren(...opts);
  sel.addEventListener("change", () => setPeriod(sel.value ? Number(sel.value) : -Infinity));
}

/**
 * 表示期間の開始年を設定する．
 * @param {number} y - 開始年（-Infinity は全期間）．
 * @returns {void}
 */
function setPeriod(y) {
  stopPlay();
  state.yearMin = y;
  $("period-select").value = Number.isFinite(y) ? String(y) : "";
  if (state.yearMax < y) setYearMax(Infinity);
  renderAll();
  const ids = state.graph.nodes.filter(isNodeVisible).map((n) => n.id);
  if (Number.isFinite(y)) zoomToNodes(ids, 1.2);
  else zoomToNodes([], 1.2, false);
}

// ---------------------------------------------------------------- 検索

/**
 * ノードの検索用の文字列を作る．
 * @param {object} n - ノード．
 * @returns {string} 小文字化した文字列．
 */
function searchText(n) {
  const b = n.bibliography;
  return [n.id, n.short_name, ...(n.aliases || []), ...(n.tags || []), b.title, ...(b.authors || []), b.venue, b.arxiv, b.doi,
    n.source_representation, n.training, ...(n.contributions || []), ...(n.channel_models || [])].filter(Boolean).join(" ").toLowerCase();
}

/** 検索欄を準備する．@returns {void} */
function setupSearch() {
  els.searchList.replaceChildren(...state.graph.nodes.map((n) => el("option", { value: n.short_name }, n.bibliography.title ?? "")));
  const run = () => {
    const q = els.search.value.trim().toLowerCase();
    if (!q) { state.matches = null; els.searchCount.textContent = ""; applyFocus(); return; }
    const exact = state.graph.nodes.find((n) => n.short_name.toLowerCase() === q);
    if (exact) { state.matches = null; els.searchCount.textContent = ""; select(exact.id, { zoomTo: true }); return; }
    const terms = q.split(/\s+/);
    state.matches = new Set(state.graph.nodes.filter((n) => terms.every((t) => searchText(n).includes(t))).map((n) => n.id));
    state.matchLabel = null;
    els.searchCount.textContent = `${state.matches.size} 件`;
    state.selected = null;
    state.path = null;
    renderPanel();
    applyFocus();
  };
  els.search.addEventListener("input", run);
  els.search.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && state.matches?.size) select([...state.matches][0], { zoomTo: true });
    if (ev.key === "Escape") clearFocus();
  });
}

// ---------------------------------------------------------------- 比較と系譜の経路

/**
 * 比較対象に追加・削除する．
 * @param {string} id - ノードID．
 * @returns {void}
 */
function toggleCompare(id) {
  const i = state.compare.indexOf(id);
  if (i >= 0) state.compare.splice(i, 1);
  else if (state.compare.length >= MAX_COMPARE) { setStatus(`比較は最大 ${MAX_COMPARE} 件である`); return; }
  else state.compare.push(id);
  els.btnCompare.textContent = `比較（${state.compare.length}）`;
  renderPanel();
  applyFocus();
  writeHash();
  if (!els.compare.hidden) renderCompare();
}

/**
 * 幅優先探索で最短経路を求める．
 * @param {string} from - 始点．
 * @param {string} to - 終点．
 * @param {function(string): Array<{next: string, edge: object}>} neighbors - 隣接を返す関数．
 * @returns {Array<{id: string, edge: object|null}>|null} 経路（始点から終点）．無い場合は null．
 */
function bfs(from, to, neighbors) {
  const prev = new Map([[from, null]]);
  const queue = [from];
  while (queue.length) {
    const u = queue.shift();
    if (u === to) break;
    for (const { next, edge } of neighbors(u)) {
      if (prev.has(next)) continue;
      prev.set(next, { u, edge });
      queue.push(next);
    }
  }
  if (!prev.has(to)) return null;
  const path = [];
  for (let v = to; v != null; v = prev.get(v)?.u) path.unshift({ id: v, edge: prev.get(v)?.edge ?? null });
  return path;
}

/** 系譜（lineage）のエッジ種別の集合．@returns {Set<string>} */
const lineageTypes = () => new Set(state.graph.edge_types.filter((t) => t.lineage).map((t) => t.id));

/**
 * 技術的系譜の経路を求める（derived_from・builds_on のみ）．
 * (1) 一方が他方の派生元・利用元である直系の経路（新しい手法 → 元の手法の向きにたどる），
 * (2) 共通の派生元（祖先）を持つ場合の，祖先から両者への2本の経路，の順に探す．
 * @param {string} a - 論文A．
 * @param {string} b - 論文B．
 * @returns {{kind: "direct"|"common", steps: Array<{from: string, to: string, edge: object}>, ancestor?: string}|null}
 *   steps の from は派生元（古い側），to は派生先（新しい側）．経路が無い場合は null．
 */
function findTechnicalLineage(a, b) {
  const lin = lineageTypes();
  const edges = state.graph.edges.filter((e) => lin.has(e.type));
  const up = (u) => edges.filter((e) => e.source === u).map((e) => ({ next: e.target, edge: e }));
  const asSteps = (path) => path.slice(1).map((s, i) => ({ from: s.id, to: path[i].id, edge: s.edge }));
  const direct = bfs(a, b, up) || bfs(b, a, up);
  if (direct) return { kind: "direct", steps: asSteps(direct).reverse() };
  // 共通の祖先: 両者から上へたどった距離の和が最小のもの
  const dist = (start) => {
    const d = new Map([[start, 0]]);
    const q = [start];
    while (q.length) {
      const u = q.shift();
      for (const { next } of up(u)) if (!d.has(next)) { d.set(next, d.get(u) + 1); q.push(next); }
    }
    return d;
  };
  const da = dist(a), db = dist(b);
  const common = [...da.keys()].filter((x) => x !== a && x !== b && db.has(x)).sort((x, y) => da.get(x) + db.get(x) - da.get(y) - db.get(y) || x.localeCompare(y));
  if (!common.length) return null;
  const anc = common[0];
  const pa = asSteps(bfs(a, anc, up)).reverse(), pb = asSteps(bfs(b, anc, up)).reverse();
  return { kind: "common", ancestor: anc, steps: [...pa, ...pb], branches: [pa, pb] };
}

/**
 * 関連経路を求める（4種類の関係を向きを無視してたどる最短経路）．
 * @param {string} a - 論文A．
 * @param {string} b - 論文B．
 * @returns {{steps: Array<{from: string, to: string, edge: object}>}|null} steps は a から b への順．
 */
function findRelatedPath(a, b) {
  const edges = state.graph.edges;
  const nb = (u) => edges.filter((e) => e.source === u || e.target === u).map((e) => ({ next: e.source === u ? e.target : e.source, edge: e }));
  const path = bfs(a, b, nb);
  if (!path) return null;
  return { steps: path.slice(1).map((s, i) => ({ from: path[i].id, to: s.id, edge: s.edge })) };
}

/**
 * 1段の関係を文で表す（向きのある関係は「派生元 → 派生先」を明示する）．
 * @param {object} edge - エッジ．
 * @returns {HTMLElement}
 */
function stepText(edge) {
  const s = state.byId.get(edge.source).short_name, t = state.byId.get(edge.target).short_name;
  const text = {
    derived_from: `${t} → ${s}（${s} が ${t} を改良・発展）`,
    builds_on: `${t} → ${s}（${s} が ${t} の技術・モデルを利用）`,
    related: `${s} ― ${t}（共通研究課題．派生関係ではない）`,
    compared_with: `${s} ― ${t}（${s} が ${t} を比較対象とした．派生関係ではない）`,
  }[edge.type];
  return el("li", { class: `step-${edge.type}` }, el("span", { class: "step-type" }, `［${edgeTypeOf(edge.type).label}］`), " ", text);
}

/**
 * 経路をマップ上で強調する．
 * @param {Array<{from: string, to: string, edge: object}>} steps - 経路の各段．
 * @param {"lineage"|"related"} mode - 経路の種類．
 * @param {string} label - 注記に表示する文．
 * @returns {void}
 */
function showPathOnMap(steps, mode, label) {
  const ids = [...new Set(steps.flatMap((s) => [s.from, s.to]))];
  for (const id of ids) {
    const n = state.byId.get(id);
    if (!isNodeVisible(n)) revealNode(n);
  }
  for (const s of steps) state.hiddenEdgeTypes.delete(s.edge.type);
  syncLegend();
  renderAll();
  state.path = { mode, nodes: ids, edges: steps.map((s) => `${s.edge.source}>${s.edge.target}>${s.edge.type}`), label };
  state.selected = null;
  renderPanel();
  setView(null);
  applyFocus();
  zoomToNodes(ids, 1.3);
}

/**
 * 2論文の経路の説明を作る（現在の経路の種類に応じる）．
 * @param {object} a - 論文A．
 * @param {object} b - 論文B．
 * @returns {HTMLElement}
 */
function pathBox(a, b) {
  const label = `${a.short_name} ⇔ ${b.short_name}`;
  const box = (...children) => el("div", { class: `path-box path-${state.pathMode}`, "data-pair": `${a.id},${b.id}` }, el("strong", {}, label), " ", ...children);
  if (state.pathMode === "lineage") {
    const res = findTechnicalLineage(a.id, b.id);
    if (!res) return box(el("p", { class: "note no-lineage" }, "技術的系譜は存在しない（改良・発展，技術・モデルの利用の関係で結ばれていない）．関連経路に切り替えると，比較対象・共通研究課題を含むつながりを確認できる．"));
    const head = res.kind === "direct" ? "直系の技術的系譜（派生元 → 派生先）"
      : `共通の派生元 ${state.byId.get(res.ancestor).short_name} から両者へ発展した技術的系譜`;
    const lists = res.kind === "direct" ? [el("ol", { class: "path-chain" }, res.steps.map((s) => stepText(s.edge)))]
      : res.branches.map((br) => el("ol", { class: "path-chain" }, br.map((s) => stepText(s.edge))));
    return box(el("span", { class: "note" }, `（${head}）`), ...lists,
      el("button", { type: "button", onclick: () => showPathOnMap(res.steps, "lineage", `技術的系譜: ${label}（${head}）`) }, "マップ上で表示"));
  }
  const res = findRelatedPath(a.id, b.id);
  if (!res) return box(el("p", { class: "note" }, "登録された関係ではつながっていない．"));
  const nonLineage = res.steps.filter((s) => !edgeTypeOf(s.edge.type).lineage).length;
  const head = nonLineage
    ? `関連経路（${res.steps.length} 段，うち比較対象・共通研究課題 ${nonLineage} 段．経路全体としては技術的な継承を意味しない）`
    : `関連経路（${res.steps.length} 段．すべて改良・発展または技術・モデルの利用の関係であり，技術的系譜と同じつながり）`;
  return box(el("span", { class: "note" }, `（${head}）`), el("ol", { class: "path-chain" }, res.steps.map((s) => stepText(s.edge))),
    el("button", { type: "button", onclick: () => showPathOnMap(res.steps, "related", `関連経路: ${label}（比較対象・共通研究課題を含む）`) }, "マップ上で表示"));
}

/** 比較表の行の定義．@type {Array<[string, function(object): (Node|string)]>} */
const COMPARE_ROWS = [
  ["タイトル", (n) => orUnverified(n.bibliography.title)],
  ["著者", (n) => orUnverified(n.bibliography.authors, (a) => a.join(", "))],
  ["年", (n) => yearDetail(n)],
  ["掲載先（登録した版）", (n) => orUnverified(n.bibliography.venue)],
  ["種別", (n) => vocabLabel("kind", n.kind)],
  ["分野", (n) => n.domains.map((d) => domainOf(d).label).join("，")],
  ["情報源表現", (n) => orUnverified(n.source_representation)],
  ["通信路モデル", (n) => orUnverified(n.channel_models, (c) => c.join("，"))],
  ["区分", (n) => orUnverified(n.transmission, (t) => vocabLabel("transmission", t))],
  ["通信路を含む共同学習", (n) => orUnverified(n.joint_channel_training, (b) => (b ? "あり" : "なし"))],
  ["主要な貢献", (n) => bulletList(n.contributions)],
  ["学習方法", (n) => orUnverified(n.training)],
  ["評価指標", (n) => orUnverified(n.metrics, (m) => m.join("，"))],
  ["長所", (n) => bulletList(n.strengths)],
  ["制約・弱点", (n) => bulletList(n.limitations)],
  ["確認した範囲", (n) => vocabLabel("read_level", n.verification.read_level)],
];

/** 比較画面を描く．@returns {void} */
function renderCompare() {
  const nodes = state.compare.map((id) => state.byId.get(id));
  const head = el("div", { class: "compare-head" }, el("strong", {}, `比較（${nodes.length}/${MAX_COMPARE}）`),
    el("span", { class: "note" }, "詳細パネルの「比較に追加」で論文を選ぶ．"),
    nodes.length ? el("button", { type: "button", onclick: () => { state.compare = []; toggleCompareCount(); renderCompare(); applyFocus(); writeHash(); } }, "全て外す") : null);
  if (!nodes.length) { els.compare.replaceChildren(head); return; }
  const table = el("table", { class: "compare-table" },
    el("thead", {}, el("tr", {}, el("th", {}, ""), nodes.map((n) => el("th", {}, el("a", { onclick: () => { setView(null); select(n.id, { zoomTo: true }); } }, n.short_name), " ",
      el("button", { type: "button", onclick: () => toggleCompare(n.id), title: "比較から外す" }, "×"))))),
    el("tbody", {}, COMPARE_ROWS.map(([label, f]) => el("tr", {}, el("th", { scope: "row" }, label), nodes.map((n) => el("td", {}, f(n)))))));
  const paths = [];
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) paths.push(pathBox(nodes[i], nodes[j]));
  const modeSwitch = el("div", { class: "path-mode", role: "radiogroup", "aria-label": "経路の種類" },
    ...[["lineage", "技術的系譜", "改良・発展と技術・モデルの利用のみ（向きあり）"], ["related", "関連経路", "4種類すべての関係（比較対象・共通研究課題を含む）"]].map(([id, lab, desc]) =>
      el("button", { type: "button", "data-mode": id, "aria-pressed": String(state.pathMode === id), title: desc,
        onclick: () => { state.pathMode = id; renderCompare(); } }, lab)),
    el("span", { class: "note" }, state.pathMode === "lineage" ? "派生元 → 派生先の向きで表示する．比較対象・共通研究課題は含めない．" : "比較対象・共通研究課題を含む．技術的な継承とは限らない．"));
  els.compare.replaceChildren(head, table, el("h3", {}, "経路"), modeSwitch, ...(nodes.length > 1 ? paths : [el("p", { class: "note" }, "経路の表示には2件以上を選ぶ．")]));
}
/** 比較ボタンの件数表示を更新する．@returns {void} */
function toggleCompareCount() { els.btnCompare.textContent = `比較（${state.compare.length}）`; }

// ---------------------------------------------------------------- 一覧表

/** 表示中の論文の一覧表を描く．@returns {void} */
function renderList() {
  const nodes = state.graph.nodes.filter(isNodeVisible);
  els.list.replaceChildren(
    el("p", { class: "note" }, `表示中の ${nodes.length} 件（分野・年の絞り込みを反映）`),
    el("table", {},
      el("thead", {}, el("tr", {}, ["初出年", "正式掲載", "略称", "タイトル", "分野", "区分", "通信路モデル"].map((h) => el("th", {}, h)))),
      el("tbody", {}, nodes.map((n) => el("tr", {},
        el("td", {}, yearLabel(n)),
        el("td", {}, n.publication?.formal ? `${n.publication.formal.year}（${n.publication.formal.venue}）` : "－"),
        el("td", {}, el("a", { onclick: () => { setView(null); select(n.id, { zoomTo: true }); } }, n.short_name)),
        el("td", {}, n.bibliography.title ?? vocabLabel("kind", n.kind)),
        el("td", {}, n.domains.map((d) => domainOf(d).short).join("，")),
        el("td", {}, orUnverified(n.transmission, (t) => vocabLabel("transmission", t))),
        el("td", {}, orUnverified(n.channel_models, (c) => c.join("，"))))))));
}

/**
 * 表示（マップ／一覧表／比較）を切り替える．
 * @param {"list"|"compare"|null} view - 表示する画面（null はマップ）．
 * @returns {void}
 */
function setView(view) {
  els.list.hidden = view !== "list";
  els.compare.hidden = view !== "compare";
  els.patterns.hidden = view !== "patterns";
  els.btnList.setAttribute("aria-pressed", String(view === "list"));
  els.btnCompare.setAttribute("aria-pressed", String(view === "compare"));
  els.btnPatterns.setAttribute("aria-pressed", String(view === "patterns"));
  if (view === "list") renderList();
  if (view === "compare") renderCompare();
  if (view === "patterns") renderPatterns();
}

// ---------------------------------------------------------------- パターン表

/** パターン表で選べる種別の区分．@type {Array<[string, string[]]>} */
const PATTERN_KIND_GROUPS = [["論文", ["paper"]], ["標準規格・ソフトウェア", ["standard", "software"]], ["構成例", ["scheme"]], ["未公開研究", ["unpublished"]]];

/** パターン表の軸の定義．@param {string} id @returns {object} */
const patternAxis = (id) => state.graph.patterns.axes.find((a) => a.id === id);

/**
 * パターン表の集計対象（マップの年・期間・分野の絞り込みと，種別の選択を反映）．
 * @returns {{nodes: object[], domains: object[]}}
 */
function patternScope() {
  return {
    nodes: state.graph.nodes.filter((n) => isNodeVisible(n) && state.patternKinds.has(n.kind)),
    domains: state.graph.domains.filter((d) => !state.hiddenDomains.has(d.id)),
  };
}

/** 現在の絞り込みの説明．@returns {string} */
function filterSummary() {
  const parts = [];
  if (Number.isFinite(state.yearMin)) parts.push(`${state.yearMin}年以降`);
  if (state.yearMax !== Infinity) parts.push(`${state.yearMax}年まで`);
  if (state.hiddenDomains.size) parts.push(`非表示の分野 ${state.hiddenDomains.size} 件`);
  return parts.length ? `マップの絞り込みを反映: ${parts.join("，")}` : "マップの絞り込み: なし（全期間・全分野）";
}

/**
 * パターン表を描く．
 * @returns {void}
 */
function renderPatterns() {
  const axis = patternAxis(state.patternAxis);
  const { nodes, domains } = patternScope();
  const table = countTable(nodes, axis, domains.map((d) => d.id));
  const axisButtons = el("div", { class: "path-mode", role: "radiogroup", "aria-label": "表の種類" },
    ...state.graph.patterns.axes.map((a) => el("button", { type: "button", "data-axis": a.id, "aria-pressed": String(a.id === axis.id), title: a.description,
      onclick: () => { state.patternAxis = a.id; state.patternCell = null; renderPatterns(); } }, a.id === "improvements" ? "改良パターン表" : "採用技術表")));
  const kindBoxes = el("div", { class: "kind-filter" }, el("span", { class: "legend-title" }, "集計対象"),
    ...PATTERN_KIND_GROUPS.map(([label, kinds]) => {
      const box = el("input", { type: "checkbox", "data-kinds": kinds.join(","), checked: kinds.every((k) => state.patternKinds.has(k)) });
      box.addEventListener("change", () => { for (const k of kinds) { if (box.checked) state.patternKinds.add(k); else state.patternKinds.delete(k); } state.patternCell = null; renderPatterns(); });
      return el("label", {}, box, ` ${label}（${state.graph.nodes.filter((n) => kinds.includes(n.kind)).length}）`);
    }));
  const notes = el("ul", { class: "note pattern-notes" },
    el("li", {}, axis.description),
    el("li", {}, "複数分野に属する論文は各分野に計上する（重複集計）．行・列の合計は重複を除いた件数である．"),
    el("li", {}, "セルの数は確認済みのデータに基づく該当件数である．0 は確認済みのデータに該当例が無いことを示し，その研究が存在しないことを意味しない．"),
    el("li", {}, "「未判定 n」は，根拠が不足して判定できないノードの数である（非該当とは区別する）．"),
    el("li", {}, filterSummary()));
  const head = el("tr", {}, el("th", { scope: "col", class: "pt-rowhead" }, axis.label),
    ...domains.map((d) => el("th", { scope: "col" }, el("span", { class: "swatch", style: `background:${domainColor(d.id)}` }), ` ${d.short}`)),
    el("th", { scope: "col" }, "合計"));
  const rows = [...axis.patterns].sort((x, y) => x.order - y.order).map((p) => el("tr", {},
    el("th", { scope: "row", class: "pt-rowhead" }, el("button", { type: "button", class: "pt-label", title: `${p.definition}\n判断基準: ${p.criteria}`,
      onclick: () => selectPatternCell(p.id, null) }, p.label)),
    ...domains.map((d) => patternCell(table, p, d)),
    el("td", { class: "pt-total" }, String(table.rowTotal.get(p.id) ?? 0))));
  const foot = el("tr", { class: "pt-foot" }, el("th", { scope: "row", class: "pt-rowhead" }, "合計（重複を除く）"),
    ...domains.map((d) => el("td", { class: "pt-total" }, String(table.colTotal.get(d.id) ?? 0))),
    el("td", { class: "pt-total" }, String(table.total)));
  els.patterns.replaceChildren(
    el("div", { class: "compare-head" }, el("strong", {}, "パターン表"), axisButtons),
    kindBoxes, notes,
    el("div", { class: "pt-scroll" }, el("table", { class: "pattern-table", "data-axis": axis.id }, el("thead", {}, head), el("tbody", {}, rows, foot))),
    el("div", { id: "pattern-detail" }));
  if (state.patternCell) renderPatternDetail();
}

/**
 * パターン表の1セルを作る．
 * @param {object} table - countTable の結果．
 * @param {object} p - パターン定義．
 * @param {object} d - 分野．
 * @returns {HTMLElement}
 */
function patternCell(table, p, d) {
  const c = table.cells.get(`${p.id}|${d.id}`) ?? { yes: [], unknown: [] };
  const n = c.yes.length, u = c.unknown.length;
  const selected = state.patternCell && state.patternCell.pattern === p.id && state.patternCell.domain === d.id;
  return el("td", { class: `pt-cell heat-${heatLevel(n)}${selected ? " pt-selected" : ""}` },
    el("button", { type: "button", "data-pattern": p.id, "data-domain": d.id, "data-count": String(n), "data-unknown": String(u),
      "aria-label": `${p.label} × ${d.label}: 該当 ${n} 件，未判定 ${u} 件`, onclick: () => selectPatternCell(p.id, d.id) },
      el("span", { class: "pt-count" }, String(n)), u ? el("span", { class: "pt-unknown" }, `未判定 ${u}`) : null));
}

/**
 * セル（または行）を選択して該当論文の一覧を表示する．
 * @param {string} pattern - パターン ID．
 * @param {string|null} domain - 分野 ID（null は表示中の全分野）．
 * @returns {void}
 */
function selectPatternCell(pattern, domain) {
  state.patternCell = { pattern, domain };
  renderPatterns();
  $("pattern-detail")?.scrollIntoView({ block: "nearest" });
}

/**
 * 選択したセルの該当・未判定の論文一覧を描く．
 * @returns {void}
 */
function renderPatternDetail() {
  const axis = patternAxis(state.patternAxis);
  const p = axis.patterns.find((x) => x.id === state.patternCell.pattern);
  const { nodes, domains } = patternScope();
  const doms = state.patternCell.domain ? [state.patternCell.domain] : domains.map((d) => d.id);
  const inScope = nodes.filter((n) => n.domains.some((d) => doms.includes(d)));
  const yes = inScope.filter((n) => patternStatus(n, axis.id, p) === "yes");
  const unknown = inScope.filter((n) => patternStatus(n, axis.id, p) === "unknown");
  const where = state.patternCell.domain ? domainOf(state.patternCell.domain).label : "表示中の全分野";
  const item = (n) => {
    const it = n.patterns[axis.id].items.find((x) => x.id === p.id);
    return el("li", {}, el("a", { onclick: () => { setView(null); select(n.id, { zoomTo: true }); } }, n.short_name), `（${yearLabel(n)}）`,
      it ? el("span", { class: "ev" }, ` 根拠: ${it.evidence.detail}${it.from ? `（改良元: ${state.byId.get(it.from).short_name}）` : ""}`) : null);
  };
  $("pattern-detail").replaceChildren(el("div", { class: "path-box pattern-detail" },
    el("strong", {}, `${p.label} × ${where}`), el("p", { class: "note" }, `定義: ${p.definition} 判断基準: ${p.criteria}`),
    el("h3", {}, `該当 ${yes.length} 件`), yes.length ? el("ul", { class: "pt-list" }, yes.map(item)) : el("p", { class: "note" }, "確認済みのデータに該当例は無い（研究の不存在を意味しない）．"),
    unknown.length ? el("details", {}, el("summary", {}, `未判定 ${unknown.length} 件`), el("ul", { class: "pt-list" }, unknown.map((n) => el("li", {}, n.short_name)))) : null,
    yes.length ? el("button", { type: "button", id: "btn-pattern-highlight", onclick: () => highlightPattern(yes.map((n) => n.id), `パターン: ${p.label} × ${where}（${yes.length} 件）`) }, "研究マップ上で強調") : null));
}

/**
 * パターン表で選んだ論文をマップ上で強調する．
 * @param {string[]} ids - ノード ID．
 * @param {string} label - 注記の文．
 * @returns {void}
 */
function highlightPattern(ids, label) {
  state.path = null;
  state.selected = null;
  state.matches = new Set(ids);
  state.matchLabel = label;
  renderPanel();
  setView(null);
  applyFocus();
  zoomToNodes(ids, 1.3);
}

/**
 * 詳細パネルの改良パターン・採用技術の欄を作る．
 * @param {object} n - ノード．
 * @returns {HTMLElement[]}
 */
function patternSections(n) {
  const out = [];
  for (const axis of state.graph.patterns.axes) {
    const a = n.patterns?.[axis.id];
    const status = state.graph.patterns.assessment[a?.assessment ?? "unassessed"];
    const items = (a?.items ?? []).map((it) => {
      const p = axis.patterns.find((x) => x.id === it.id);
      return el("li", { class: "rel-item" }, el("span", { class: "tag" }, p?.label ?? it.id), " ",
        el("span", { class: "ev" }, `${it.evidence.detail}${it.from ? `（改良元: ${state.byId.get(it.from)?.short_name ?? it.from}）` : ""}`));
    });
    out.push(el("h3", {}, axis.label), el("p", { class: "note" }, `${status}${a?.note ? `．${a.note}` : ""}`),
      items.length ? el("ul", { class: "pattern-items" }, items) : el("p", { class: "note" }, "該当として挙げたパターンは無い．"));
  }
  return out;
}

// ---------------------------------------------------------------- 書き出し

/**
 * 計算済みのスタイルをインラインに写した SVG の複製を作る（全体の範囲）．
 * @returns {SVGSVGElement}
 */
function serializableSvg() {
  const src = svg.node();
  const clone = src.cloneNode(true);
  const props = ["fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity", "font-size", "font-weight", "font-family", "paint-order"];
  const a = src.querySelectorAll("*"), b = clone.querySelectorAll("*");
  a.forEach((node, i) => {
    const cs = getComputedStyle(node);
    b[i].setAttribute("style", props.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(";"));
  });
  const L = state.layout;
  clone.querySelector(".zoom-root").removeAttribute("transform");
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("viewBox", `0 0 ${L.width} ${L.height}`);
  clone.setAttribute("width", L.width);
  clone.setAttribute("height", L.height);
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("width", L.width);
  bg.setAttribute("height", L.height);
  bg.setAttribute("fill", getComputedStyle(document.documentElement).getPropertyValue("--surface-1").trim());
  clone.insertBefore(bg, clone.firstChild);
  return clone;
}

/** ファイルとして保存する．@param {string} name @param {Blob} blob @returns {void} */
function download(name, blob) {
  const a = el("a", { href: URL.createObjectURL(blob), download: name });
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

/** SVG を保存する．@returns {void} */
function exportSvg() {
  const text = new XMLSerializer().serializeToString(serializableSvg());
  download("image-coding-map.svg", new Blob([text], { type: "image/svg+xml" }));
  $("export-menu").open = false;
}

/** PNG を保存する（2倍の解像度）．@returns {Promise<void>} */
async function exportPng() {
  const clone = serializableSvg();
  const text = new XMLSerializer().serializeToString(clone);
  const img = new Image();
  img.src = URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
  await img.decode();
  const scale = 2, L = state.layout;
  const canvas = el("canvas", { width: L.width * scale, height: L.height * scale });
  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0);
  URL.revokeObjectURL(img.src);
  canvas.toBlob((blob) => download("image-coding-map.png", blob), "image/png");
  $("export-menu").open = false;
}

// ---------------------------------------------------------------- 配色・URL

/** 配色の切り替えを準備する．@returns {void} */
function setupTheme() {
  const saved = localStorage.getItem("icm-theme");
  if (THEMES.includes(saved)) state.themeMode = saved;
  const apply = () => {
    if (state.themeMode === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = state.themeMode;
    els.btnTheme.textContent = `配色: ${THEME_LABEL[state.themeMode]}`;
  };
  apply();
  els.btnTheme.addEventListener("click", () => {
    state.themeMode = THEMES[(THEMES.indexOf(state.themeMode) + 1) % THEMES.length];
    localStorage.setItem("icm-theme", state.themeMode);
    apply();
  });
}

/**
 * URL のハッシュに選択・比較の状態を書く（例: #necst，#necst&compare=necst,blindsc）．
 * @returns {void}
 */
function writeHash() {
  const parts = [];
  if (state.selected) parts.push(state.selected);
  if (state.compare.length) parts.push(`compare=${state.compare.join(",")}`);
  const hash = parts.length ? `#${parts.join("&")}` : "";
  if (location.hash !== hash) history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
}

/**
 * URL のハッシュから選択・比較の状態を読む．
 * @returns {void}
 */
function readHash() {
  const raw = decodeURIComponent(location.hash.slice(1));
  if (!raw) return;
  let selectId = null;
  for (const part of raw.split("&")) {
    if (part.startsWith("compare=")) state.compare = part.slice(8).split(",").filter((id) => state.byId.has(id)).slice(0, MAX_COMPARE);
    else if (state.byId.has(part)) selectId = part;
    else setStatus(`ID「${part}」の論文は見つからない`, 4000);
  }
  toggleCompareCount();
  if (state.compare.length && !selectId) setView("compare");
  if (selectId) select(selectId, { zoomTo: true, updateHash: false });
  else applyFocus();
}

// ---------------------------------------------------------------- 起動

/**
 * 起動処理．
 * @returns {Promise<void>}
 */
async function main() {
  setupTheme();
  try {
    await loadGraph();
  } catch (err) {
    setStatus(`読み込みに失敗した: ${err.message}`, 0);
    return;
  }
  injectDomainColors(state.graph.domains);
  state.hiddenEdgeTypes = new Set(state.graph.edge_types.filter((t) => t.default_visible === false).map((t) => t.id));
  state.layout = computeLayout(state.graph, measureLabel);
  setupSvg();
  renderFrame();
  buildLegend();
  syncLegend();
  setupYearSlider();
  setupPeriod();
  setupSearch();
  renderAll();
  $("btn-fit").addEventListener("click", () => zoomToNodes([]));
  els.btnList.addEventListener("click", () => setView(els.list.hidden ? "list" : null));
  els.btnCompare.addEventListener("click", () => setView(els.compare.hidden ? "compare" : null));
  els.btnPatterns.addEventListener("click", () => setView(els.patterns.hidden ? "patterns" : null));
  $("btn-svg").addEventListener("click", exportSvg);
  $("btn-png").addEventListener("click", exportPng);
  $("panel-close").addEventListener("click", () => select(null));
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && document.activeElement !== els.search) { setView(null); clearFocus(); } });
  window.addEventListener("hashchange", readHash);
  zoomToNodes([], 1.2, false);
  readHash();
  setStatus(`${state.graph.nodes.length} 件の論文・手法，${state.graph.edges.length} 本の関係（データ生成日 ${state.graph.generated}）`, 4000);
  // テスト・デバッグ用の参照口（描画には影響しない）
  window.ICM = { findTechnicalLineage, findRelatedPath, state };
  document.body.dataset.ready = "true";
}

main();
