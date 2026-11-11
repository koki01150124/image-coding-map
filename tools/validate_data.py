"""ノードデータの検証．

検証の内容:
    1. JSON スキーマ（data/schema/node.schema.json）
    2. ID とファイル名の一致，重複 ID
    3. 分野・エッジ種別が定義済みであること
    4. 関係の参照先の存在，自己参照，重複
    5. 系譜関係（lineage が true のエッジ種別）の循環
    6. 年代軸の年（year）と year_basis・publication（初出・正式掲載）の整合
    7. 論文の書誌情報が survey/library.json と一致すること
    8. プレプリントと正式掲載版などの重複（arXiv ID，DOI，タイトル）
    9. 分類の規則（data/classification_rules.json）
    10. 改良パターン・採用技術の定義（data/patterns.json）とノードの参照の整合
    11. 研究分野樹形図の分類体系（data/research_taxonomy.json）と，ノードの research_fields の整合

使い方:
    python tools/validate_data.py   # エラーがあれば終了コード1
"""
import sys
from collections import defaultdict

from common import DATA, load_library, load_node_files, load_vocab, read_json
from patterns import condition_matches
from taxonomy import membership_errors, taxonomy_errors
from sync_bibliography import diff_bibliography


def schema_errors(nodes, schema):
    """JSON スキーマによる検証．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        schema (dict): JSON スキーマ．
    Returns:
        list[str]: エラーのリスト．
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema がインストールされていない（pip install -r requirements_tools.txt）"]
    validator = Draft202012Validator(schema)
    errors = []
    for path, node in nodes:
        for err in sorted(validator.iter_errors(node), key=lambda e: list(e.path)):
            loc = "/".join(str(p) for p in err.path) or "(root)"
            errors.append(f"{path.name}: スキーマ違反 {loc}: {err.message}")
    return errors


def identity_errors(nodes):
    """ID とファイル名の一致と，重複 ID を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
    Returns:
        list[str]: エラーのリスト．
    """
    errors, seen = [], {}
    for path, node in nodes:
        nid = node.get("id")
        if nid != path.stem:
            errors.append(f"{path.name}: id '{nid}' がファイル名と一致しない")
        if nid in seen:
            errors.append(f"{path.name}: id '{nid}' が {seen[nid]} と重複")
        seen.setdefault(nid, path.name)
    return errors


def relation_errors(nodes, edge_types):
    """関係の参照先・種別・自己参照・重複を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        edge_types (list[dict]): エッジ種別の定義．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors, warnings = [], []
    ids = {n["id"] for _, n in nodes}
    by_id = {n["id"]: n for _, n in nodes}
    types = {t["id"]: t for t in edge_types}
    undirected_pairs = set()
    for _, node in nodes:
        nid, seen = node["id"], set()
        for rel in node.get("relations", []):
            tgt, typ = rel.get("target"), rel.get("type")
            if typ not in types:
                errors.append(f"{nid}: 未定義のエッジ種別 '{typ}'")
                continue
            if tgt == nid:
                errors.append(f"{nid}: 自己参照の関係（{typ}）")
                continue
            if tgt not in ids:
                errors.append(f"{nid}: 関係の参照先 '{tgt}' が存在しない（{typ}）")
                continue
            if (tgt, typ) in seen:
                errors.append(f"{nid}: '{tgt}' への {typ} が重複")
            seen.add((tgt, typ))
            if not types[typ]["directed"]:
                pair = (frozenset((nid, tgt)), typ)
                if pair in undirected_pairs:
                    warnings.append(f"{nid}: '{tgt}' との {typ} が両方向に登録されている")
                undirected_pairs.add(pair)
            if types[typ]["lineage"] and by_id[tgt]["year"] > node["year"]:
                errors.append(f"{nid}（{node['year']}）: 系譜の元 '{tgt}'（{by_id[tgt]['year']}）の方が新しい（{typ}）")
    return errors, warnings


def find_lineage_cycles(nodes, edge_types):
    """系譜関係（lineage が true のエッジ）の有向グラフの循環を検出する．

    エッジの向きは「新しい手法 → 元の手法」である．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        edge_types (list[dict]): エッジ種別の定義．
    Returns:
        list[list[str]]: 検出した循環（ノードIDの列）のリスト．
    """
    lineage = {t["id"] for t in edge_types if t["lineage"]}
    graph = defaultdict(list)
    for _, node in nodes:
        for rel in node.get("relations", []):
            if rel.get("type") in lineage:
                graph[node["id"]].append(rel["target"])
    color, cycles = {}, []

    def visit(u, stack):
        """深さ優先探索で循環を探す．

        Args:
            u (str): 現在のノード．
            stack (list[str]): 探索中の経路．
        Returns:
            None
        """
        color[u] = "gray"
        stack.append(u)
        for v in graph.get(u, []):
            if color.get(v) == "gray":
                cycles.append(stack[stack.index(v):] + [v])
            elif v not in color:
                visit(v, stack)
        stack.pop()
        color[u] = "black"

    for _, node in nodes:
        if node["id"] not in color:
            visit(node["id"], [])
    return cycles


def arxiv_year(arxiv):
    """新形式の arXiv ID（YYMM.NNNNN）から初版の年を求める．

    Args:
        arxiv (str | None): arXiv ID．
    Returns:
        int | None: 年．旧形式・無しの場合は None．
    """
    import re
    m = re.match(r"^(\d{2})(\d{2})\.\d{4,5}$", arxiv or "")
    return 2000 + int(m.group(1)) if m else None


def bibliography_errors(nodes, library):
    """書誌情報と survey/library.json の一致，論文の bib_key の有無を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        library (dict[str, dict]): library.json の内容．
    Returns:
        list[str]: エラーのリスト．
    """
    errors = []
    for path, node in nodes:
        if node.get("kind") in ("paper", "standard") and not node.get("bib_key"):
            errors.append(f"{path.name}: 論文・標準規格の解説論文（kind={node.get('kind')}）は survey/library.json の bib_key が必要")
    updates, sync_errors = diff_bibliography(nodes, library)
    errors += sync_errors
    errors += [f"{p.name}: bibliography が survey/library.json と一致しない" for p, _, _ in updates]
    return errors


def year_errors(nodes, rules, edge_types):
    """年代軸の年と，年の基準（year_basis）・初出・正式掲載の整合を検査する．

    - 論文・標準: year = 初出年，初出年 ≤ 正式掲載年，初出年 ≤ arXiv 初版の年（初出が arXiv なら一致）
    - ソフトウェア: year = 最初の公開年，正式掲載なし
    - 構成例・未公開: 初出・正式掲載なし．構成例の year は比較対象として用いた論文の最小の年
    - 書誌情報の年が初出年・正式掲載年のいずれとも一致しない場合は year_note が必要

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        rules (list[dict]): 分類の規則（kind_year_basis を含む）．
        edge_types (list[dict]): エッジ種別の定義（未使用，互換のため）．
    Returns:
        list[str]: エラーのリスト．
    """
    errors = []
    basis_of = next((r["kind_year_basis"] for r in rules if "kind_year_basis" in r), {})
    by_id = {n["id"]: n for _, n in nodes}
    users = {}
    for _, n in nodes:
        for r in n.get("relations", []):
            if r["type"] == "compared_with":
                users.setdefault(r["target"], []).append(n["id"])
    for path, n in nodes:
        name, kind, year = path.name, n["kind"], n["year"]
        pub = n.get("publication") or {}
        first, formal = pub.get("first_public"), pub.get("formal")
        if basis_of.get(kind) and n.get("year_basis") != basis_of[kind]:
            errors.append(f"{name}: kind={kind} の year_basis は '{basis_of[kind]}'（現在 '{n.get('year_basis')}'）")
        if kind in ("paper", "standard", "software"):
            if not first:
                errors.append(f"{name}: publication.first_public（初出）が無い")
                continue
            if year != first["year"]:
                errors.append(f"{name}: year（{year}）が初出年（{first['year']}）と一致しない")
            if formal and formal["year"] < first["year"]:
                errors.append(f"{name}: 正式掲載年（{formal['year']}）が初出年（{first['year']}）より前")
            ay = arxiv_year(n["bibliography"].get("arxiv"))
            if ay is not None and first["year"] > ay:
                errors.append(f"{name}: 初出年（{first['year']}）が arXiv 初版の年（{ay}）より後")
            if ay is not None and first["venue"] == "arXiv" and first["year"] != ay:
                errors.append(f"{name}: 初出が arXiv であるが年（{first['year']}）が arXiv ID の年（{ay}）と異なる")
        else:
            if first or formal:
                errors.append(f"{name}: kind={kind} は初出・正式掲載を持たない（publication の値は null とする）")
            if not n.get("year_note"):
                errors.append(f"{name}: kind={kind} の年の意味を year_note に書く")
        if kind == "scheme":
            used = [by_id[u]["year"] for u in users.get(n["id"], [])]
            if not used:
                errors.append(f"{name}: 構成例を比較対象として用いた論文（compared_with）が無い")
            elif year != min(used):
                errors.append(f"{name}: 構成例の year（{year}）が比較対象として用いた論文の最小の年（{min(used)}）と一致しない")
        bib_year = n["bibliography"].get("year")
        dated = {x["year"] for x in (first, formal) if x}
        if bib_year is not None and dated and bib_year not in dated and not n.get("year_note"):
            errors.append(f"{name}: 書誌情報の年（{bib_year}）が初出年・正式掲載年のいずれとも異なるが year_note が無い")
    return errors


def duplicate_errors(nodes):
    """同じ論文（プレプリントと正式掲載版など）が複数のノードになっていないかを検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
    Returns:
        list[str]: エラーのリスト．
    """
    import re
    errors, seen = [], {}
    for path, n in nodes:
        b = n["bibliography"]
        keys = [("bib_key", n.get("bib_key")), ("arXiv", b.get("arxiv")), ("DOI", (b.get("doi") or "").lower() or None),
                ("タイトル", re.sub(r"[^a-z0-9]", "", (b.get("title") or "").lower()) or None)]
        for label, value in keys:
            if value is None:
                continue
            if (label, value) in seen:
                errors.append(f"{path.name}: {label} が {seen[(label, value)]} と重複（同じ論文を別のノードにしない）")
            seen.setdefault((label, value), path.name)
    return errors


def rule_errors(nodes, rules):
    """分類の規則（data/classification_rules.json）を検査する．

    規則の when（domains_any，kinds，tags_any）に該当するノードについて，field の値の allow／forbid／warn，
    primary_domain（主分野），forbid_domain（属してはならない分野）を検査する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        rules (list[dict]): 規則．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors, warnings = [], []
    for rule in rules:
        when = rule.get("when")
        if when is None:
            continue
        for path, n in nodes:
            if "domains_any" in when and not set(when["domains_any"]) & set(n["domains"]):
                continue
            if "kinds" in when and n["kind"] not in when["kinds"]:
                continue
            if "tags_any" in when and not set(when["tags_any"]) & set(n.get("tags", [])):
                continue
            msg = f"{path.name}: 分類の規則 {rule['id']} に違反（{rule['description']}）"
            value = n.get(rule["field"]) if "field" in rule else None
            if "allow" in rule and value not in rule["allow"]:
                errors.append(f"{msg}: {rule['field']}={value!r}")
            if "forbid" in rule and value in rule["forbid"]:
                errors.append(f"{msg}: {rule['field']}={value!r}")
            if "warn" in rule and value in rule["warn"]:
                warnings.append(f"{path.name}: {rule['field']} が未確認（{rule['id']}）")
            if "primary_domain" in rule and n["domains"][0] != rule["primary_domain"]:
                errors.append(f"{msg}: 主分野={n['domains'][0]}")
            if "forbid_domain" in rule and rule["forbid_domain"] in n["domains"]:
                errors.append(msg)
    return errors, warnings

PATTERN_KEYS = ("id", "label", "definition", "criteria", "order")
CONDITION_OPS = ("prefix", "equals", "in")


def pattern_definition_errors(defs):
    """パターン定義の構造・重複 ID・条件の書式を検査する．

    Args:
        defs (dict): data/patterns.json の内容．
    Returns:
        list[str]: エラーのリスト．
    """
    errors = []
    axis_ids = [a.get("id") for a in defs.get("axes", [])]
    if sorted(axis_ids) != ["improvements", "techniques"]:
        errors.append(f"patterns.json: 軸は improvements と techniques の2つとする（現在 {axis_ids}）")
    for axis in defs.get("axes", []):
        seen = set()
        for p in axis.get("patterns", []):
            missing = [k for k in PATTERN_KEYS if not p.get(k) and p.get(k) != 0]
            if missing:
                errors.append(f"patterns.json: {axis['id']}.{p.get('id')} に {missing} が無い")
            if p.get("id") in seen:
                errors.append(f"patterns.json: {axis['id']} のパターン ID '{p.get('id')}' が重複")
            seen.add(p.get("id"))
            for cond in p.get("not_applicable_if", []):
                ops = [k for k in CONDITION_OPS if k in cond]
                if "field" not in cond or len(ops) != 1 or set(cond) - {"field", *CONDITION_OPS}:
                    errors.append(f"patterns.json: {axis['id']}.{p['id']} の非該当の条件の書式が不正: {cond}")
    return errors


def pattern_errors(nodes, defs, edge_types):
    """ノードの改良パターン・採用技術の参照を検査する．

    - 未定義のパターン ID，同じノード内の重複
    - 対象外（not_applicable）・未判定（unassessed）の軸に該当を挙げていないこと
    - 改良元（from）が系譜の関係の参照先であること
    - 該当として挙げたパターンが，定義の非該当の条件に一致しないこと

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        defs (dict): パターン定義．
        edge_types (list[dict]): エッジ種別の定義．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors, warnings = pattern_definition_errors(defs), []
    lineage = {t["id"] for t in edge_types if t["lineage"]}
    by_axis = {a["id"]: {p["id"]: p for p in a["patterns"]} for a in defs.get("axes", [])}
    used = {a: set() for a in by_axis}
    for path, n in nodes:
        for axis_id, pats in by_axis.items():
            axis = n.get("patterns", {}).get(axis_id)
            if axis is None:
                continue
            ids = [it["id"] for it in axis["items"]]
            for pid in ids:
                if pid not in pats:
                    errors.append(f"{path.name}: 未定義の{axis_id}のパターン '{pid}'")
            for pid in {i for i in ids if ids.count(i) > 1}:
                errors.append(f"{path.name}: {axis_id} のパターン '{pid}' が重複")
            if axis["assessment"] in ("not_applicable", "unassessed") and ids:
                errors.append(f"{path.name}: {axis_id} は {axis['assessment']} であるが該当を挙げている")
            if axis["assessment"] in ("not_applicable", "unassessed") and not axis.get("note"):
                errors.append(f"{path.name}: {axis_id} の {axis['assessment']} の理由（note）が無い")
            if axis["assessment"] == "assessed" and not ids:
                warnings.append(f"{path.name}: {axis_id} は判定済みで該当が無い（全て非該当）")
            for it in axis["items"]:
                used[axis_id].add(it["id"])
                if it.get("from") and not any(r["target"] == it["from"] and r["type"] in lineage for r in n["relations"]):
                    errors.append(f"{path.name}: {axis_id}.{it['id']} の改良元 '{it['from']}' が系譜の関係に無い")
                p = pats.get(it["id"])
                if p and any(condition_matches(n, c) for c in p.get("not_applicable_if", [])):
                    errors.append(f"{path.name}: {axis_id}.{it['id']} は該当とされているが，定義の非該当の条件に一致する")
    for axis_id, pats in by_axis.items():
        for pid in pats:
            if pid not in used[axis_id]:
                warnings.append(f"patterns.json: {axis_id}.{pid} を用いるノードが無い")
    return errors, warnings


def validate(nodes, vocab, schema, library):
    """全ての検証を実行する．

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        vocab (dict): load_vocab の戻り値．
        schema (dict): JSON スキーマ．
        library (dict[str, dict]): library.json の内容．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors = schema_errors(nodes, schema) + identity_errors(nodes)
    if errors:
        return errors, []
    domain_ids = {d["id"] for d in vocab["domains"]}
    for path, node in nodes:
        for d in node["domains"]:
            if d not in domain_ids:
                errors.append(f"{path.name}: 未定義の分野 '{d}'")
    rel_errors, warnings = relation_errors(nodes, vocab["edge_types"])
    errors += rel_errors
    errors += ["系譜関係の循環: " + " -> ".join(c) for c in find_lineage_cycles(nodes, vocab["edge_types"])]
    errors += bibliography_errors(nodes, library)
    errors += year_errors(nodes, vocab["rules"], vocab["edge_types"])
    errors += duplicate_errors(nodes)
    r_errors, r_warnings = rule_errors(nodes, vocab["rules"])
    p_errors, p_warnings = pattern_errors(nodes, vocab["patterns"], vocab["edge_types"]) if "patterns" in vocab else ([], [])
    t_errors, t_warnings = [], []
    if "taxonomy" in vocab:
        t_errors = taxonomy_errors(vocab["taxonomy"], domain_ids)
        m_errors, t_warnings = membership_errors(nodes, vocab["taxonomy"])
        t_errors += m_errors
    return errors + r_errors + p_errors + t_errors, warnings + r_warnings + p_warnings + t_warnings


def main():
    """コマンドラインの入口．

    Returns:
        int: 終了コード（エラーがあれば1）．
    """
    nodes = load_node_files()
    errors, warnings = validate(nodes, load_vocab(), read_json(DATA / "schema" / "node.schema.json"), load_library())
    for w in warnings:
        print(f"[warn]  {w}")
    for e in errors:
        print(f"[error] {e}")
    n_edges = sum(len(n.get("relations", [])) for _, n in nodes)
    print(f"[validate] nodes={len(nodes)} edges={n_edges} errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
