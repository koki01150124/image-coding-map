// Image Coding Map — 改良パターン・採用技術の判定と集計（tools/patterns.py と同じ規則）
//
// ノードとパターンの組の状態:
//   "yes"     該当: patterns.<軸>.items に挙げられている
//   "no"      非該当: 軸の判定が assessed（挙げていないものは非該当）か not_applicable，
//             またはパターン定義の not_applicable_if の条件に一致する
//   "unknown" 未判定: 上記以外

/**
 * 非該当の条件に一致するかを判定する．
 * @param {object} node - ノード．
 * @param {{field: string, prefix?: string, equals?: *, in?: Array}} cond - 条件．
 * @returns {boolean}
 */
export function conditionMatches(node, cond) {
  const v = node[cond.field];
  if ("prefix" in cond) return typeof v === "string" && v.startsWith(cond.prefix);
  if ("equals" in cond) return v === cond.equals;
  if ("in" in cond) return cond.in.includes(v);
  return false;
}

/**
 * ノードとパターンの組の状態を返す．
 * @param {object} node - ノード．
 * @param {string} axisId - "improvements" または "techniques"．
 * @param {object} pattern - パターン定義．
 * @returns {"yes"|"no"|"unknown"}
 */
export function patternStatus(node, axisId, pattern) {
  const axis = node.patterns?.[axisId] ?? { assessment: "unassessed", items: [] };
  if (axis.items.some((it) => it.id === pattern.id)) return "yes";
  if (axis.assessment === "assessed" || axis.assessment === "not_applicable") return "no";
  if ((pattern.not_applicable_if || []).some((c) => conditionMatches(node, c))) return "no";
  return "unknown";
}

/**
 * パターン表を集計する．複数分野のノードは各分野に計上し，行・列・全体の合計は重複を除いた件数とする．
 * @param {object[]} nodes - 集計対象のノード（絞り込み済み）．
 * @param {object} axis - 軸の定義（patterns を含む）．
 * @param {string[]} domains - 列（分野 ID）．
 * @returns {{cells: Map<string, {yes: string[], unknown: string[]}>, rowTotal: Map<string, number>, colTotal: Map<string, number>, total: number}}
 *   cells のキーは `${patternId}|${domainId}`．
 */
export function countTable(nodes, axis, domains) {
  const cells = new Map(), rows = new Map(), cols = new Map(), total = new Set();
  const cell = (k) => { if (!cells.has(k)) cells.set(k, { yes: [], unknown: [] }); return cells.get(k); };
  const add = (m, k, id) => { if (!m.has(k)) m.set(k, new Set()); m.get(k).add(id); };
  for (const p of axis.patterns) {
    for (const n of nodes) {
      const st = patternStatus(n, axis.id, p);
      for (const d of n.domains) {
        if (!domains.includes(d)) continue;
        if (st === "yes") { cell(`${p.id}|${d}`).yes.push(n.id); add(rows, p.id, n.id); add(cols, d, n.id); total.add(n.id); }
        else if (st === "unknown") cell(`${p.id}|${d}`).unknown.push(n.id);
      }
    }
  }
  const size = (m) => new Map([...m].map(([k, v]) => [k, v.size]));
  return { cells, rowTotal: size(rows), colTotal: size(cols), total: total.size };
}

/**
 * 件数を色の段階（0〜4）に変換する．
 * @param {number} n - 件数．
 * @returns {number} 0: 0件，1: 1件，2: 2件，3: 3〜4件，4: 5件以上．
 */
export function heatLevel(n) {
  if (n <= 0) return 0;
  if (n === 1) return 1;
  if (n === 2) return 2;
  return n <= 4 ? 3 : 4;
}
