"""収集した文献の重複排除・分類・優先度付け．

audit/raw/ の検索・スノーボーリングの結果を統合し，以下を出力する．
    audit/candidates.json，audit/candidates.csv  未収録の候補（優先度・理由・関係候補つき）
    audit/dedup_log.json                         重複の統合と，既存ノードとの照合の記録
    audit/coverage_stats.json                    分野・年ごとの集計

関連性の判定はタイトルと要旨のキーワードによる一次判定であり，audit/decisions.json の人手の判断
（採否・理由・分野・関係候補）で上書きする．関係候補は要旨の記述を根拠とし，本文の確認を要する．

使い方:
    python programs/audit_coverage/build_candidates.py
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from collect import AUDIT, RAW, ROOT, norm_title

# 分野・課題のキーワード（タイトルと要旨を小文字化して照合する）
TOPIC_TERMS = {
    "lic": [r"learned image compression", r"neural image compression", r"end-to-end (optimized )?image compression",
            r"entropy model", r"hyperprior", r"learned (image )?codec", r"variable[- ]rate image compression"],
    "generative": [r"diffusion", r"generative (image )?compression", r"perceptual (image )?compression", r"\bgan\b", r"codebook"],
    "analog_jscc": [r"joint source[- ]channel", r"\bjscc\b", r"deep ?jscc", r"semantic communication"],
    "digital_jscc": [r"digital (deep )?(joint source|semantic|jscc)", r"modulation", r"quantiz", r"binary symmetric", r"\bbsc\b",
                     r"constellation", r"discrete"],
    "sscc": [r"separat\w* source[- ]channel", r"\bldpc\b", r"\bpolar code", r"channel cod(e|ing)", r"\bbpg\b"],
    "bit_error": [r"bit[- ]?(flip|error)", r"\bber\b", r"error[- ]resilien", r"robust\w*"],
    "packet_loss": [r"packet loss", r"loss[- ]resilien", r"erasure", r"lossy (network|channel)"],
}
IMAGE_TERMS = r"image|picture|visual|video|vision"
CORE_TERMS = r"compression|codec|coding|jscc|source[- ]channel|semantic communication|transmission"
OFFTOPIC = r"medical imag|hyperspectral|point cloud|lidar|\bmri\b|\bct\b scan|speech|audio|text-to-image generation|federated|large language model"

# 既存ノードの名称（要旨での言及を関係候補の手がかりにする）
NODE_MENTIONS = {
    "deepjscc": r"bourtsoulatze|\bdeep ?jscc\b(?![- ](f|l|q)\b)", "deepjscc_f": r"deepjscc-f\b", "deepjscc_q": r"deepjscc-q\b",
    "adjscc": r"\badjscc\b", "ntscc": r"\bntscc\b|nonlinear transform source[- ]channel", "swinjscc": r"swinjscc",
    "necst": r"\bnecst\b", "blindsc": r"blindsc", "jcm": r"\bjcm\b", "d2jscc": r"d2-?jscc|d²-jscc",
    "scale_hyperprior": r"hyperprior", "minnen_joint": r"autoregressive (context|prior)", "elic": r"\belic\b", "tcm": r"\btcm\b",
    "hific": r"\bhific\b", "ddpm": r"\bddpm\b", "cdc": r"conditional diffusion compression", "ddcm": r"\bddcm\b",
    "turbo_ddcm": r"turbo-ddcm", "bpg": r"\bbpg\b", "jpeg": r"\bjpeg\b(?! ?2000)", "jpeg2000": r"jpeg ?2000", "vvc": r"\bvvc\b",
    "gallager_ldpc": r"\bldpc\b", "polar": r"polar code",
}


def load_raw():
    """audit/raw/ の全ての結果を読み込み，出典（検索式・スノーボーリング）を付ける．

    Returns:
        list[dict]: 文献（hit キーに出典の文字列を持つ）．
    """
    log = json.loads((AUDIT / "search_log.json").read_text())
    query_of = {}
    for e in log:
        if e["type"] == "search":
            query_of[f"search_{e['target']}_{norm_title(e['query'])[:40]}"] = (e["target"], e["topic"], e["query"])
    recs = []
    for p in sorted(RAW.glob("*.json")):
        for r in json.loads(p.read_text()):
            if p.stem.startswith("search_"):
                tgt, topic, q = query_of.get(p.stem, ("?", "?", p.stem))
                r["hit"], r["topic_hit"] = f"{tgt}: {q}", topic
            else:
                stem = p.stem.replace("snowball_", "snowball:").replace("textrefs_", "snowball:")
                r["hit"], r["topic_hit"] = f"{stem} ({r.get('relation')})", None
            recs.append(r)
    for item in json.loads((AUDIT / "priority_check.json").read_text()):
        for src, r in item["found"].items():
            if r:
                r = dict(r, source=r.get("source", src), hit=f"order_004 優先確認: {item['label']}", topic_hit=None, priority_label=item["label"])
                recs.append(r)
    return recs


class UnionFind:
    """重複の統合に用いる素集合．"""

    def __init__(self, n):
        """n 個の要素で初期化する．@param n 要素数．"""
        self.p = list(range(n))

    def find(self, i):
        """代表元を返す．@param i 要素．@return int"""
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a, b):
        """2つの集合を統合する．@param a 要素．@param b 要素．@return None"""
        self.p[self.find(a)] = self.find(b)


def keys_of(r):
    """重複判定の鍵（DOI，arXiv ID，正規化タイトル）．

    Args:
        r (dict): 文献．
    Returns:
        list[str]: 鍵．
    """
    ks = []
    if r.get("doi") and not r["doi"].startswith("10.48550/"):
        ks.append("doi:" + r["doi"].lower())
    if r.get("arxiv"):
        ks.append("arxiv:" + re.sub(r"v\d+$", "", r["arxiv"]))
    t = norm_title(r.get("title"))
    if len(t) >= 20:
        ks.append("title:" + t)
    return ks


def merge(recs):
    """プレプリントと正式掲載版などの重複を1件にまとめる．

    Args:
        recs (list[dict]): 文献．
    Returns:
        list[dict]: 統合した文献（members に元の件数）．
    """
    uf, owner = UnionFind(len(recs)), {}
    for i, r in enumerate(recs):
        for k in keys_of(r):
            if k in owner:
                uf.union(i, owner[k])
            owner.setdefault(k, i)
    groups = defaultdict(list)
    for i, r in enumerate(recs):
        groups[uf.find(i)].append(r)
    return [combine(g) for g in groups.values()]


def arxiv_year(a):
    """arXiv ID の年．@param a arXiv ID．@return int|None"""
    m = re.match(r"^(\d{2})(\d{2})\.", a or "")
    return 2000 + int(m.group(1)) if m else None


def combine(group):
    """同一文献の記録を統合する．

    Args:
        group (list[dict]): 同一文献の記録．
    Returns:
        dict: 統合した文献．
    """
    def first(key, pred=lambda v: v):
        return next((r[key] for r in group if r.get(key) and pred(r[key])), None)
    formal = [r for r in group if r.get("venue") and not str(r["venue"]).lower().startswith("arxiv") and r.get("year")]
    arx = first("arxiv")
    years = [r["year"] for r in group if r.get("year")] + ([arxiv_year(arx)] if arxiv_year(arx) else [])
    doi = first("doi", lambda d: not d.startswith("10.48550/")) or first("doi")
    return {
        "title": (formal[0]["title"] if formal else None) or first("title"),
        "authors": max((r.get("authors") or [] for r in group), key=len),
        "first_public_year": min(years) if years else None,
        "formal_venue": formal[0]["venue"] if formal else None,
        "formal_year": formal[0]["year"] if formal else None,
        "doi": doi, "arxiv": arx, "openalex": first("openalex"),
        "cited_by": max((r.get("cited_by") or 0 for r in group), default=0),
        "abstract": max((r.get("abstract") or "" for r in group), key=len),
        "hits": sorted({r["hit"] for r in group}), "topics_hit": sorted({r["topic_hit"] for r in group if r.get("topic_hit")}),
        "sources": sorted({r["source"] for r in group}), "priority_label": first("priority_label"),
        "n_records": len(group),
    }


def existing_index():
    """既存ノードと除外済みの重複文献の照合用の鍵．

    Returns:
        dict[str, str]: 鍵 → ノードID（または library のキー）．
    """
    idx = {}
    for p in (ROOT / "data" / "nodes").glob("*.json"):
        n = json.loads(p.read_text())
        for k in keys_of(n["bibliography"]):
            idx[k] = n["id"]
    lib = json.loads((ROOT / "survey" / "library.json").read_text())
    for key, e in lib.items():
        if e.get("status") == "excluded" and "同一論文" in (e.get("reason") or ""):
            for k in keys_of(e):
                idx[k] = f"library:{key}（{e['reason'][:30]}…）"
    return idx


def classify(c):
    """キーワードによる関連性の一次判定と，分野・課題・既存ノードへの言及を求める．

    Args:
        c (dict): 統合した文献．
    Returns:
        dict: {relevance, topics, mentions, offtopic}
    """
    text = f"{c['title'] or ''} {c['abstract'] or ''}".lower()
    topics = [t for t, pats in TOPIC_TERMS.items() if any(re.search(p, text) for p in pats)]
    image = bool(re.search(IMAGE_TERMS, text))
    core = bool(re.search(CORE_TERMS, text))
    off = bool(re.search(OFFTOPIC, text))
    title = (c["title"] or "").lower()
    in_title = sum(1 for pats in TOPIC_TERMS.values() if any(re.search(p, title) for p in pats))
    if off or not (image and core) or not topics:
        rel = 0
    else:
        rel = min(3, 1 + (in_title >= 1) + (len(topics) >= 2 or "bit_error" in topics or "packet_loss" in topics))
    mentions = sorted(k for k, p in NODE_MENTIONS.items() if re.search(p, text))
    return {"relevance": rel, "topics": topics, "mentions": mentions, "offtopic": off}


def snowball_relations(c):
    """スノーボーリングの出典から，既存ノードとの引用関係を求める（派生関係を意味しない）．

    Args:
        c (dict): 統合した文献．
    Returns:
        list[dict]: {node, relation}．relation は "cites"（候補が既存ノードを引用）または "cited_by"．
    """
    out = []
    for h in c["hits"]:
        m = re.match(r"snowball:(\w+) \((citation|reference)\)", h)
        if m:
            out.append({"node": m.group(1), "relation": "cites" if m.group(2) == "citation" else "cited_by"})
    return out


def priority_of(c):
    """追加の優先度（A／B／C）と理由を求める．

    A: 関連性が高く（3），被引用 50 以上・3つ以上の検索で出現・既存ノードへの引用関係が2件以上・order の優先確認のいずれか
    B: 関連性が 2 以上で，A に該当しない
    C: 関連性が 1

    Args:
        c (dict): 統合・判定済みの文献．
    Returns:
        tuple[str, list[str]]: (優先度, 理由)．
    """
    reasons = []
    if c["priority_label"]:
        reasons.append(f"order_004 の優先確認論文（{c['priority_label']}）")
    if c["cited_by"] >= 50:
        reasons.append(f"被引用 {c['cited_by']}（OpenAlex/Semantic Scholar の最大値）")
    n_search = sum(1 for h in c["hits"] if not h.startswith("snowball") and not h.startswith("order_004"))
    if n_search >= 3:
        reasons.append(f"{n_search} 件の検索で出現")
    if len(c["snowball"]) >= 2:
        reasons.append(f"既存ノード {len(c['snowball'])} 件と引用関係（OpenAlex）")
    if c["relevance"] >= 3 and reasons:
        return "A", reasons
    if c["priority_label"]:
        return "A", reasons
    if c["relevance"] >= 2:
        return "B", reasons or ["関連性は高いが，被引用・出現回数が少ない"]
    return "C", reasons or ["関連性が限定的（キーワードの一致が少ない）"]


def main():
    """統合・判定・出力を行う．

    Returns:
        None
    """
    recs = load_raw()
    merged = merge(recs)
    idx = existing_index()
    decisions = json.loads((AUDIT / "decisions.json").read_text()) if (AUDIT / "decisions.json").exists() else {}
    dedup, cands = {"n_records": len(recs), "n_unique": len(merged), "matched_existing": [], "merged_groups": []}, []
    for c in merged:
        if c["n_records"] > 1:
            dedup["merged_groups"].append({"title": c["title"], "n_records": c["n_records"], "doi": c["doi"], "arxiv": c["arxiv"]})
        hit = next((idx[k] for k in keys_of(c) if k in idx), None)
        if hit:
            dedup["matched_existing"].append({"title": c["title"], "existing": hit})
            continue
        c.update(classify(c))
        c["snowball"] = snowball_relations(c)
        c["key"] = (f"arxiv:{c['arxiv']}" if c["arxiv"] else f"doi:{c['doi']}" if c["doi"] else f"title:{norm_title(c['title'])[:60]}")
        d = decisions.get(c["key"])
        if c["relevance"] == 0 and not c["priority_label"] and not d:
            continue
        c["priority"], c["priority_reasons"] = priority_of(c)
        c["certainty"] = {"bibliographic": "API で確認（" + "，".join(c["sources"]) + "）" + ("，DOI あり" if c["doi"] else ""),
                          "content": "要旨あり（本文未確認）" if len(c["abstract"]) > 200 else "要旨なし（内容未確認）"}
        c["decision"] = d or {"status": "unreviewed"}
        if d and d.get("priority"):
            c["priority"] = d["priority"]
        cands.append(c)
    order = {"A": 0, "B": 1, "C": 2, "X": 3}
    cands.sort(key=lambda c: (order.get(c["priority"], 9), -c["relevance"], -(c["cited_by"] or 0)))
    (AUDIT / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=1) + "\n")
    (AUDIT / "dedup_log.json").write_text(json.dumps(dedup, ensure_ascii=False, indent=1) + "\n")
    cols = ["priority", "title", "first_public_year", "formal_venue", "formal_year", "doi", "arxiv", "cited_by", "relevance",
            "topics", "mentions", "snowball", "decision_status", "suggested_domains", "relation_candidates", "reason", "priority_reasons", "content_certainty"]
    with open(AUDIT / "candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in cands:
            d = c["decision"]
            w.writerow({"priority": c["priority"], "title": c["title"], "first_public_year": c["first_public_year"],
                        "formal_venue": c["formal_venue"] or "", "formal_year": c["formal_year"] or "", "doi": c["doi"] or "",
                        "arxiv": c["arxiv"] or "", "cited_by": c["cited_by"], "relevance": c["relevance"], "topics": "|".join(c["topics"]),
                        "mentions": "|".join(c["mentions"]), "snowball": "|".join(f"{s['relation']}:{s['node']}" for s in c["snowball"]),
                        "decision_status": d.get("status"), "suggested_domains": "|".join(d.get("domains", [])),
                        "relation_candidates": " ; ".join(f"{r['type']}→{r['target']}（{r['evidence']}）" for r in d.get("relations", [])),
                        "reason": d.get("reason", ""), "priority_reasons": " ; ".join(c["priority_reasons"]), "content_certainty": c["certainty"]["content"]})
    stats = {"by_priority": Counter(c["priority"] for c in cands), "by_topic": Counter(t for c in cands for t in c["topics"]),
             "by_topic_A": Counter(t for c in cands if c["priority"] == "A" for t in c["topics"]),
             "by_year": dict(sorted(Counter(c["first_public_year"] for c in cands).items(), key=lambda x: (x[0] is None, x[0]))),
             "by_decision": Counter(c["decision"]["status"] for c in cands)}
    (AUDIT / "coverage_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1, default=str) + "\n")
    print(f"[build] records={len(recs)} unique={len(merged)} existing={len(dedup['matched_existing'])} candidates={len(cands)} {dict(stats['by_priority'])}")


if __name__ == "__main__":
    main()
