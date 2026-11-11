"""研究分野樹形図の分類体系（data/research_taxonomy.json）の読み込み・検証・集計．

分類は論文ノードと独立に定義し，論文ノードは research_fields で所属する分類の ID を参照する．
分類の線（親子関係）は分類上の包含のみを表し，技術的な派生関係（研究系譜図のエッジ）とは無関係である．
"""
from collections import defaultdict

REQUIRED = ("id", "name_ja", "name_en", "description", "criteria", "parent", "children", "domain", "order")
OPS = ("prefix", "equals", "in", "contains")


def member_condition_matches(node, cond):
    """所属の条件に一致するかを判定する．

    Args:
        node (dict): ノード．
        cond (dict): {field, prefix | equals | in | contains}．
    Returns:
        bool: 一致すれば True．書式の誤りは False（taxonomy_errors が検出する）．
    """
    value = node.get(cond.get("field"))
    if "prefix" in cond:
        return isinstance(value, str) and value.startswith(cond["prefix"])
    if "equals" in cond:
        return value == cond["equals"]
    if "in" in cond:
        return value in cond["in"]
    if "contains" in cond:
        return isinstance(value, list) and cond["contains"] in value
    return False


def index(tax):
    """分類の辞書を作る．

    Args:
        tax (dict): 分類体系．
    Returns:
        dict[str, dict]: ID → 分類（重複 ID は後の定義で上書きされる）．
    """
    return {c["id"]: c for c in tax.get("categories", [])}


def ancestors(cat_id, by_id):
    """祖先の ID の列（親から根へ）．循環がある場合は循環の手前で止める．

    Args:
        cat_id (str): 分類の ID．
        by_id (dict[str, dict]): 分類の辞書．
    Returns:
        list[str]: 祖先の ID．
    """
    out, seen, cur = [], {cat_id}, by_id.get(cat_id, {}).get("parent")
    while cur is not None and cur in by_id and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = by_id[cur].get("parent")
    return out


def find_cycles(by_id):
    """親子関係（parent）の循環を検出する．

    Args:
        by_id (dict[str, dict]): 分類の辞書．
    Returns:
        list[list[str]]: 循環（ID の列）．
    """
    cycles, done = [], set()
    for start in by_id:
        path, cur = [], start
        while cur is not None and cur in by_id and cur not in done:
            if cur in path:
                cyc = path[path.index(cur):] + [cur]
                if sorted(cyc[:-1]) not in [sorted(c[:-1]) for c in cycles]:
                    cycles.append(cyc)
                break
            path.append(cur)
            cur = by_id[cur].get("parent")
        done.update(path)
    return cycles


def taxonomy_errors(tax, domain_ids):
    """分類体系の構造を検査する．

    - 必須キー，ID の一意性，存在しない親・子の参照，parent と children の整合
    - 根が1つであること，親子関係の循環
    - domain が既存の分野であること，親が分野を持つ場合は子も同じ分野であること
    - 所属の条件の書式

    Args:
        tax (dict): 分類体系．
        domain_ids (set[str]): data/domains.json の分野 ID．
    Returns:
        list[str]: エラーのリスト．
    """
    errors, seen = [], set()
    cats = tax.get("categories", [])
    for c in cats:
        missing = [k for k in REQUIRED if k not in c]
        if missing:
            errors.append(f"research_taxonomy.json: {c.get('id')} に {missing} が無い")
        if c.get("id") in seen:
            errors.append(f"research_taxonomy.json: 分類 ID '{c.get('id')}' が重複")
        seen.add(c.get("id"))
    by_id = index(tax)
    roots = [c["id"] for c in cats if c.get("parent") is None]
    if len(roots) != 1:
        errors.append(f"research_taxonomy.json: 根（parent が null）は1つとする（現在 {roots}）")
    for c in cats:
        cid, parent = c.get("id"), c.get("parent")
        if parent is not None and parent not in by_id:
            errors.append(f"research_taxonomy.json: {cid} の親 '{parent}' が存在しない")
        if parent in by_id and cid not in by_id[parent].get("children", []):
            errors.append(f"research_taxonomy.json: {cid} の親 '{parent}' の children に {cid} が無い")
        for ch in c.get("children", []):
            if ch not in by_id:
                errors.append(f"research_taxonomy.json: {cid} の子 '{ch}' が存在しない")
            elif by_id[ch].get("parent") != cid:
                errors.append(f"research_taxonomy.json: {cid} の子 '{ch}' の parent が {cid} でない")
        if c.get("domain") is not None and c["domain"] not in domain_ids:
            errors.append(f"research_taxonomy.json: {cid} の domain '{c['domain']}' が未定義")
        pdom = by_id.get(parent, {}).get("domain") if parent else None
        if pdom is not None and c.get("domain") != pdom:
            errors.append(f"research_taxonomy.json: {cid} の domain が親 {parent} の分野 '{pdom}' と異なる")
        for cond in c.get("member_conditions", []):
            if "field" not in cond or len([k for k in OPS if k in cond]) != 1 or set(cond) - {"field", *OPS}:
                errors.append(f"research_taxonomy.json: {cid} の所属の条件の書式が不正: {cond}")
    errors += ["research_taxonomy.json: 親子関係の循環: " + " -> ".join(cyc) for cyc in find_cycles(by_id)]
    return errors


def inherited_conditions(cat_id, by_id):
    """分類とその祖先の所属の条件．

    Args:
        cat_id (str): 分類の ID．
        by_id (dict[str, dict]): 分類の辞書．
    Returns:
        list[tuple[str, dict]]: (条件を定めた分類の ID, 条件)．
    """
    out = []
    for cid in [cat_id, *ancestors(cat_id, by_id)]:
        out += [(cid, c) for c in by_id[cid].get("member_conditions", [])]
    return out


def membership_errors(nodes, tax):
    """論文ノードの research_fields と分類体系の整合を検査する．

    - 存在しない分類・根への所属，重複，祖先と子孫の両方への所属
    - 所属する分類の分野がノードの domains に含まれ，ノードの主分野（domains の先頭）がいずれかの所属で表されること
    - 所属の条件（祖先の条件を含む）を満たすこと
    - 所属する論文の無い分類（allow_empty のものを除く）は警告

    Args:
        nodes (list[tuple[Path, dict]]): ノードのファイルと内容．
        tax (dict): 分類体系．
    Returns:
        tuple[list[str], list[str]]: (エラー, 警告)．
    """
    errors, warnings = [], []
    by_id = index(tax)
    root = next((c["id"] for c in tax.get("categories", []) if c.get("parent") is None), None)
    used = set()
    for path, n in nodes:
        fields = n.get("research_fields", [])
        if not fields:
            errors.append(f"{path.name}: research_fields が空")
        for f in {f for f in fields if fields.count(f) > 1}:
            errors.append(f"{path.name}: research_fields の '{f}' が重複")
        valid = [f for f in fields if f in by_id]
        for f in fields:
            if f not in by_id:
                errors.append(f"{path.name}: 存在しない分類 '{f}' を参照")
            elif f == root:
                errors.append(f"{path.name}: 根の分類 '{f}' には直接所属させない")
        for f in valid:
            used.update([f, *ancestors(f, by_id)])
            for a in ancestors(f, by_id):
                if a in valid:
                    errors.append(f"{path.name}: '{f}' とその祖先 '{a}' の両方に所属している")
            dom = by_id[f].get("domain")
            if dom is not None and dom not in n.get("domains", []):
                errors.append(f"{path.name}: 分類 '{f}' の分野 '{dom}' がノードの domains に無い")
            for owner, cond in inherited_conditions(f, by_id):
                if not member_condition_matches(n, cond):
                    errors.append(f"{path.name}: 分類 '{f}' の所属の条件（{owner}: {cond}）を満たさない")
        covered = {by_id[f].get("domain") for f in valid}
        if n.get("domains") and n["domains"][0] not in covered:
            errors.append(f"{path.name}: 主分野 '{n['domains'][0]}' に対応する分類に所属していない")
    for c in tax.get("categories", []):
        if c["id"] not in used and c["id"] != root and not c.get("allow_empty"):
            warnings.append(f"research_taxonomy.json: 分類 '{c['id']}' に所属する論文が無い")
    return errors, warnings


def members(tax, nodes, include_descendants=True):
    """分類ごとの所属ノードの ID を求める．

    Args:
        tax (dict): 分類体系．
        nodes (list[dict]): ノード．
        include_descendants (bool): 子孫の分類の所属を含めるか．
    Returns:
        dict[str, list[str]]: 分類 ID → ノード ID（重複なし，順序はノードの順）．
    """
    by_id = index(tax)
    out = defaultdict(list)
    for n in nodes:
        targets = set()
        for f in n.get("research_fields", []):
            if f in by_id:
                targets.add(f)
                if include_descendants:
                    targets.update(ancestors(f, by_id))
        for t in targets:
            out[t].append(n["id"])
    return dict(out)
