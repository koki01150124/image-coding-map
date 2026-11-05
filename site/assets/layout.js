// Image Compression Map — 配置計算
//
// 縦方向: 発表年（古い年を上）．年ごとに1行とし，論文の無い年は詰める．
// 横方向: 研究分野の列（domains.json の order 順）．複数分野の論文は，主分野の列と隣り合う副分野の列の間
//         （主分野の重み 2，副分野 1 の加重平均）に置く．分野の重なりは位置・外周の色分け・範囲の重なりで表す．
// 同じ年の論文はラベルの幅を考慮して段に振り分け，ノードとラベルが重ならないようにする（乱数を用いず再現する）．

export const LAYOUT = {
  radius: 9,
  colWidth: 210,
  header: 64,
  axisWidth: 62,
  lineHeight: 30,
  rowPad: 14,
  labelGap: 14,
  region: { cell: 6, sigmaX: 24, sigmaY: 30, threshold: 0.5 },
};

/**
 * ラベル幅の概算（全角は12px，半角は6.6px）．ブラウザでは実測の関数を渡す．
 * @param {string} s - ラベル．
 * @returns {number} 幅（px）．
 */
export function estimateTextWidth(s) {
  let w = 0;
  for (const ch of s) w += ch.charCodeAt(0) > 0xff ? 12 : 6.6;
  return w;
}

/**
 * 配置を計算する．
 * @param {{nodes: object[], domains: object[]}} graph - graph.json の内容．
 * @param {function(string): number} textWidth - ラベル幅を返す関数．
 * @param {object} C - 配置の定数（既定: LAYOUT）．
 * @returns {{width: number, height: number, columns: object[], rows: object[], pos: Map<string, {x: number, y: number}>}}
 *   columns: {id, label, short, x0, x1, cx}，rows: {year, y0, y1, cy}，pos: ノードID → 座標．
 */
export function computeLayout(graph, textWidth = estimateTextWidth, C = LAYOUT) {
  const domains = [...graph.domains].sort((a, b) => a.order - b.order);
  const columns = domains.map((d, i) => {
    const x0 = C.axisWidth + i * C.colWidth;
    return { id: d.id, label: d.label, short: d.short, x0, x1: x0 + C.colWidth, cx: x0 + C.colWidth / 2 };
  });
  const colOf = new Map(columns.map((c) => [c.id, c]));
  // 主分野の列を基準とし，隣り合う列の副分野がある場合のみ列の境界側へ寄せる（離れた列の間には置かない）
  const colIndex = new Map(columns.map((c, i) => [c.id, i]));
  const targetX = (n) => {
    const p = colIndex.get(n.domains[0]);
    const adjacent = n.domains.slice(1).filter((d) => Math.abs(colIndex.get(d) - p) === 1);
    let sx = 2 * colOf.get(n.domains[0]).cx, sw = 2;
    for (const d of adjacent) { sx += colOf.get(d).cx; sw += 1; }
    return Math.round(sx / sw - C.colWidth * 0.22);
  };

  // 系譜の深さ（派生元をたどる最長の段数）．同じ年の中で派生元を上の段に置くために用いる
  const lineageTypes = new Set((graph.edge_types || []).filter((t) => t.lineage).map((t) => t.id));
  const parents = new Map();
  for (const e of graph.edges || []) {
    if (!lineageTypes.has(e.type)) continue;
    if (!parents.has(e.source)) parents.set(e.source, []);
    parents.get(e.source).push(e.target);
  }
  const depthMemo = new Map();
  const depth = (id, seen = new Set()) => {
    if (depthMemo.has(id)) return depthMemo.get(id);
    if (seen.has(id)) return 0;
    seen.add(id);
    const d = Math.max(0, ...(parents.get(id) || []).map((p) => depth(p, seen) + 1));
    depthMemo.set(id, d);
    return d;
  };

  const years = [...new Set(graph.nodes.map((n) => n.year))].sort((a, b) => a - b);
  const rows = [];
  const pos = new Map();
  let y = C.header;
  for (const yr of years) {
    const items = graph.nodes.filter((n) => n.year === yr)
      .map((n) => ({ id: n.id, x: targetX(n), d: depth(n.id), w: 2 * C.radius + 8 + textWidth(n.short_name) }))
      .sort((a, b) => a.x - b.x || a.d - b.d || a.id.localeCompare(b.id));
    const lineEnds = [];
    for (const it of items) {
      let line = lineEnds.findIndex((end) => end + C.labelGap <= it.x - C.radius);
      if (line < 0) { line = lineEnds.length; lineEnds.push(0); }
      lineEnds[line] = it.x - C.radius + it.w;
      it.line = line;
    }
    const h = 2 * C.rowPad + lineEnds.length * C.lineHeight;
    for (const it of items) pos.set(it.id, { x: it.x, y: y + C.rowPad + (it.line + 0.5) * C.lineHeight });
    rows.push({ year: yr, y0: y, y1: y + h, cy: y + h / 2 });
    y += h;
  }
  const width = columns[columns.length - 1].x1 + 20;
  return { width, height: y + 20, columns, rows, pos };
}

/**
 * 分野ごとの範囲を，所属する論文の位置に置いたガウス関数の和の等高線として求める．
 * 離れた論文同士はつながらず，近い論文同士だけが1つの範囲にまとまる．
 * @param {string[]} memberIds - 分野に属するノードID．
 * @param {Map<string, {x: number, y: number}>} pos - ノードの座標．
 * @param {number} width - 全体の幅．
 * @param {number} height - 全体の高さ．
 * @param {object} d3 - d3 名前空間（contours，geoPath を用いる）．
 * @param {object} C - 配置の定数．
 * @returns {string | null} SVG の path の d 属性．メンバーが無い場合は null．
 */
export function regionPath(memberIds, pos, width, height, d3, C = LAYOUT) {
  const pts = memberIds.map((id) => pos.get(id)).filter(Boolean);
  if (!pts.length) return null;
  const { cell, sigmaX, sigmaY, threshold } = C.region;
  const gw = Math.ceil(width / cell), gh = Math.ceil(height / cell);
  const values = new Float64Array(gw * gh);
  const sx2 = 2 * sigmaX * sigmaX, sy2 = 2 * sigmaY * sigmaY;
  for (const p of pts) {
    const ix0 = Math.max(0, Math.floor((p.x - 3 * sigmaX) / cell)), ix1 = Math.min(gw - 1, Math.ceil((p.x + 3 * sigmaX) / cell));
    const iy0 = Math.max(0, Math.floor((p.y - 3 * sigmaY) / cell)), iy1 = Math.min(gh - 1, Math.ceil((p.y + 3 * sigmaY) / cell));
    for (let iy = iy0; iy <= iy1; iy++) {
      const ey = (iy * cell - p.y) ** 2 / sy2;
      for (let ix = ix0; ix <= ix1; ix++) values[iy * gw + ix] += Math.exp(-((ix * cell - p.x) ** 2) / sx2 - ey);
    }
  }
  const [contour] = d3.contours().size([gw, gh]).thresholds([threshold])(values);
  return d3.geoPath(d3.geoIdentity().scale(cell))(contour);
}

/**
 * 2点間の曲線エッジのパスを作る（同じ行の場合は弧，それ以外は縦方向の3次ベジェ）．
 * @param {{x: number, y: number}} a - 始点．
 * @param {{x: number, y: number}} b - 終点．
 * @param {number} r - ノードの半径（端点をノードの外周まで縮める）．
 * @returns {string} SVG の path の d 属性．
 */
export function edgePath(a, b, r) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  if (Math.abs(dy) < 12) {
    const sx = a.x + (dx / len) * r, ex = b.x - (dx / len) * (r + 3);
    const bulge = Math.min(60, len * 0.25);
    return `M${sx},${a.y}Q${(sx + ex) / 2},${a.y - bulge} ${ex},${b.y}`;
  }
  const dirY = Math.sign(dy);
  const sy = a.y + dirY * r, ey = b.y - dirY * (r + 3);
  const my = (sy + ey) / 2;
  return `M${a.x},${sy}C${a.x},${my} ${b.x},${my} ${b.x},${ey}`;
}
