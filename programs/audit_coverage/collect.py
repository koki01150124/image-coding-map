"""収録範囲の網羅性監査のための文献収集．

OpenAlex，Semantic Scholar，arXiv の検索 API と，OpenAlex による参考文献・被引用文献の追跡で
候補文献を収集し，API の応答を正規化して audit/raw/ に保存する．検索式・検索日・対象・取得件数は
audit/search_log.json に記録する．書誌情報は API の応答のみを用い，手で補わない．

使い方:
    python programs/audit_coverage/collect.py inventory   # 既存ノードの台帳 audit/existing_inventory.csv
    python programs/audit_coverage/collect.py search      # 横断検索
    python programs/audit_coverage/collect.py snowball    # 参考文献・被引用文献の追跡
    python programs/audit_coverage/collect.py priority    # order の優先確認論文の照合
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "audit"
RAW = AUDIT / "raw"
LOG = AUDIT / "search_log.json"
UA = {"User-Agent": "image-coding-map-coverage-audit (research; contact via repository)"}
FROM_YEAR = 2015

# 検索式（英語）．対象分野・課題ごとに定める
QUERIES = {
    "lic": ["learned image compression", "end-to-end optimized image compression entropy model",
            "neural image codec rate-distortion"],
    "generative": ["diffusion model image compression", "generative image compression perceptual",
                   "zero-shot diffusion image compression"],
    "sscc": ["separate source channel coding image transmission LDPC", "image transmission channel coding learned compression"],
    "analog_jscc": ["deep joint source-channel coding image", "deep JSCC wireless image transmission",
                    "semantic communication image transmission joint source channel coding"],
    "digital_jscc": ["digital deep joint source-channel coding", "digital semantic communication modulation quantization",
                     "neural joint source channel coding binary symmetric channel"],
    "diffusion_jscc": ["diffusion model joint source-channel coding", "generative semantic communication diffusion"],
    "bit_error": ["bit error robustness learned image compression", "bit flip error resilient image compression",
                  "robust deep joint source-channel coding"],
    "packet_loss": ["packet loss resilient image coding", "loss-resilient learned image compression",
                    "erasure resilient neural image codec"],
}


def http_json(url, retries=5, wait=6.0):
    """JSON を返す API を呼び出す（429 等では待機して再試行する）．

    Args:
        url (str): URL．
        retries (int): 再試行の回数．
        wait (float): 再試行までの待機秒数（回ごとに増やす）．
    Returns:
        dict | None: 応答．失敗した場合は None．
    """
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as ex:  # noqa: BLE001
            if "404" in str(ex):
                return None
            time.sleep(wait * (i + 1))
    return None


def http_text(url, retries=4, wait=6.0):
    """テキストを返す API を呼び出す．

    Args:
        url (str): URL．
        retries (int): 再試行の回数．
        wait (float): 待機秒数．
    Returns:
        str | None: 応答．
    """
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            time.sleep(wait * (i + 1))
    return None


def norm_title(t):
    """照合用にタイトルを正規化する．

    Args:
        t (str | None): タイトル．
    Returns:
        str: 英小文字と数字のみの文字列．
    """
    t = re.sub(r"\$[^$]*\$", "", t or "")
    return re.sub(r"[^a-z0-9]", "", t.lower())


def arxiv_from_doi(doi):
    """arXiv の DOI（10.48550/arxiv.XXXX）から arXiv ID を取り出す．

    Args:
        doi (str | None): DOI．
    Returns:
        str | None: arXiv ID．
    """
    m = re.match(r"10\.48550/arxiv\.(.+)$", (doi or "").lower())
    return m.group(1) if m else None


def from_openalex(w):
    """OpenAlex の work を共通の形式に変換する．

    Args:
        w (dict): OpenAlex の work．
    Returns:
        dict: {title, authors, year, venue, doi, arxiv, openalex, cited_by, abstract, source}
    """
    doi = (w.get("doi") or "").replace("https://doi.org/", "").lower() or None
    arxiv = arxiv_from_doi(doi)
    for loc in w.get("locations") or []:
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})", (loc.get("landing_page_url") or "") + " " + (loc.get("pdf_url") or ""))
        if m:
            arxiv = arxiv or m.group(1)
    inv = w.get("abstract_inverted_index") or {}
    words = sorted(((p, k) for k, ps in inv.items() for p in ps))
    src = ((w.get("primary_location") or {}).get("source") or {})
    return {"title": w.get("title"), "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
            "year": w.get("publication_year"), "venue": src.get("display_name"), "doi": doi, "arxiv": arxiv,
            "openalex": (w.get("id") or "").rsplit("/", 1)[-1], "cited_by": w.get("cited_by_count"),
            "abstract": " ".join(k for _, k in words)[:3000], "source": "openalex"}


def from_s2(p):
    """Semantic Scholar の paper を共通の形式に変換する．

    Args:
        p (dict): Semantic Scholar の paper．
    Returns:
        dict: 共通の形式．
    """
    ext = p.get("externalIds") or {}
    return {"title": p.get("title"), "authors": [a.get("name") for a in p.get("authors") or []], "year": p.get("year"),
            "venue": p.get("venue") or None, "doi": (ext.get("DOI") or "").lower() or None, "arxiv": ext.get("ArXiv"),
            "openalex": None, "cited_by": p.get("citationCount"), "abstract": (p.get("abstract") or "")[:3000],
            "s2": p.get("paperId"), "source": "semanticscholar"}


def from_arxiv_xml(text):
    """arXiv API の Atom を共通の形式のリストに変換する．

    Args:
        text (str): Atom の XML．
    Returns:
        list[dict]: 共通の形式．
    """
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    out = []
    for e in ET.fromstring(text).findall("a:entry", ns):
        aid = re.sub(r"v\d+$", "", e.findtext("a:id", "", ns).rsplit("/abs/", 1)[-1])
        doi = e.findtext("x:doi", None, ns)
        out.append({"title": " ".join(e.findtext("a:title", "", ns).split()), "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
                    "year": int(e.findtext("a:published", "0000", ns)[:4]), "venue": e.findtext("x:journal_ref", None, ns) or "arXiv",
                    "doi": doi.lower() if doi else None, "arxiv": aid, "openalex": None, "cited_by": None,
                    "abstract": " ".join(e.findtext("a:summary", "", ns).split())[:3000], "source": "arxiv"})
    return out


def log(entry):
    """検索の記録を追記する．

    Args:
        entry (dict): 記録（type, target, query, n_results 等）．
    Returns:
        None
    """
    logs = json.loads(LOG.read_text()) if LOG.exists() else []
    logs.append({"date": date.today().isoformat(), **entry})
    LOG.write_text(json.dumps(logs, ensure_ascii=False, indent=1) + "\n")


def save(name, records):
    """正規化した応答を保存する．

    Args:
        name (str): ファイル名（拡張子なし）．
        records (list[dict]): 文献．
    Returns:
        None
    """
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{name}.json").write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n")


def search_openalex(query, sort):
    """OpenAlex を検索する．

    Args:
        query (str): 検索式．
        sort (str): "relevance" または "cited"．
    Returns:
        list[dict] | None: 文献．
    """
    params = {"search": query, "per-page": "50", "filter": f"from_publication_date:{FROM_YEAR}-01-01"}
    if sort == "cited":
        params["sort"] = "cited_by_count:desc"
    d = http_json("https://api.openalex.org/works?" + urllib.parse.urlencode(params))
    return None if d is None else [from_openalex(w) for w in d.get("results", [])]


def search_s2(query):
    """Semantic Scholar を検索する．

    Args:
        query (str): 検索式．
    Returns:
        list[dict] | None: 文献．
    """
    fields = "title,authors,year,venue,externalIds,citationCount,abstract"
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
        {"query": query, "limit": "50", "fields": fields, "year": f"{FROM_YEAR}-"})
    d = http_json(url, retries=2, wait=20)
    return None if d is None else [from_s2(p) for p in d.get("data") or []]


def search_arxiv(query):
    """arXiv を新しい順に検索する．

    Args:
        query (str): 検索式．
    Returns:
        list[dict] | None: 文献．
    """
    q = " AND ".join(f"all:{w}" for w in query.split())
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": q, "start": "0", "max_results": "40", "sortBy": "submittedDate", "sortOrder": "descending"})
    text = http_text(url)
    return None if text is None else from_arxiv_xml(text)


def cmd_inventory():
    """既存ノードの DOI・arXiv ID・正式タイトルの台帳を作る．

    Returns:
        None
    """
    rows = []
    for p in sorted((ROOT / "data" / "nodes").glob("*.json")):
        n = json.loads(p.read_text())
        b, pub = n["bibliography"], n.get("publication") or {}
        formal = pub.get("formal") or {}
        rows.append({"id": n["id"], "kind": n["kind"], "short_name": n["short_name"], "title": b.get("title") or "",
                     "doi": b.get("doi") or "", "arxiv": b.get("arxiv") or "", "year": n["year"],
                     "formal_venue": formal.get("venue") or "", "formal_year": formal.get("year") or "",
                     "domains": "|".join(n["domains"])})
    with open(AUDIT / "existing_inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"[inventory] {len(rows)} 件")


def cmd_search(sources="openalex_relevance,openalex_cited,arxiv_date,semanticscholar"):
    """全ての検索式で指定した API を検索する（保存済みの検索は飛ばし，失敗した検索は再実行する）．

    Args:
        sources (str): 検索対象（カンマ区切り）．
    Returns:
        None
    """
    jobs = [(topic, q, src) for src in sources.split(",") for topic, qs in QUERIES.items() for q in qs]
    for topic, q, src in tqdm(jobs, leave=False):
        name = f"search_{src}_{norm_title(q)[:40]}"
        if (RAW / f"{name}.json").exists():
            continue
        if src.startswith("openalex"):
            res = search_openalex(q, src.split("_")[1])
        elif src == "semanticscholar":
            res = search_s2(q)
        else:
            res = search_arxiv(q)
        period = f"{FROM_YEAR}-" if src != "arxiv_date" else "新しい順の上位40件"
        log({"type": "search", "target": src, "topic": topic, "query": q, "period": period,
             "n_results": None if res is None else len(res), "status": "ok" if res is not None else "failed"})
        if res is not None:
            save(name, res)
        time.sleep(3.5 if src in ("semanticscholar", "arxiv_date") else 1.2)


SEEDS = {  # 既存ノード ID → OpenAlex ID（survey/library.json）
    "deepjscc": "bourtsoulatze2019deep", "necst": "choi2018neural", "scale_hyperprior": "balle2018variational",
    "ddcm": "ohayon2025compressed", "robust_turbo_ddcm": "vaisman2026robustness", "blindsc": "oh2025blind",
    "ntscc": "dai2022nonlinear",
}


def cmd_snowball():
    """主要な既存ノードの参考文献と被引用文献を OpenAlex で取得する．

    Returns:
        None
    """
    lib = json.loads((ROOT / "survey" / "library.json").read_text())
    for node_id, key in tqdm(SEEDS.items(), leave=False):
        oa = lib[key]["openalex"]
        name = f"snowball_{node_id}"
        if (RAW / f"{name}.json").exists():
            continue
        work = http_json(f"https://api.openalex.org/works/{oa}?select=id,referenced_works")
        refs = [r.rsplit("/", 1)[-1] for r in (work or {}).get("referenced_works", [])]
        records = []
        for i in range(0, len(refs), 40):
            ids = "|".join(refs[i:i + 40])
            d = http_json(f"https://api.openalex.org/works?filter=openalex:{ids}&per-page=50")
            records += [dict(from_openalex(w), relation="reference") for w in (d or {}).get("results", [])]
            time.sleep(1.2)
        # 被引用文献は被引用数の多い順に上位 200 件（OpenAlex の1ページ）に限る
        d = http_json(f"https://api.openalex.org/works?filter=cites:{oa}&per-page=200&sort=cited_by_count:desc")
        cites = [dict(from_openalex(w), relation="citation") for w in (d or {}).get("results", [])]
        total = ((d or {}).get("meta") or {}).get("count")
        log({"type": "snowball", "target": "openalex", "seed": node_id, "seed_openalex": oa,
             "n_references": len(records), "n_citations": len(cites), "n_citations_total": total,
             "citation_policy": "被引用数の多い順に上位200件", "status": "ok" if work and d else "failed"})
        save(name, records + cites)


PRIORITY = [  # order_004 の優先確認論文（識別子は order の記載）
    {"label": "BitFlat", "arxiv": "2610.25682"},
    {"label": "DiffJSCC", "arxiv": "2404.17736"},
    {"label": "SGD-JSCC", "arxiv": "2501.01138"},
    {"label": "CDDM", "doi": "10.1109/twc.2024.3379244"},
    {"label": "ResiComp", "doi": "10.1109/tcsvt.2025.3539747"},
    {"label": "Loss-Resilient Image Coding (AAAI 2025)", "title": "Towards Loss-Resilient Image Coding for Unstable Satellite Networks"},
    {"label": "Survey on Robust DeepJSCC", "arxiv": "2604.04413"},
]


def cmd_priority():
    """優先確認論文の実在と書誌情報を arXiv・Crossref・OpenAlex で照合する．

    Returns:
        None
    """
    out = []
    for p in tqdm(PRIORITY, leave=False):
        rec = {"label": p["label"], "query": {k: v for k, v in p.items() if k != "label"}, "found": {}}
        if "arxiv" in p:
            t = http_text(f"https://export.arxiv.org/api/query?id_list={p['arxiv']}")
            items = from_arxiv_xml(t) if t else []
            rec["found"]["arxiv"] = items[0] if items and items[0]["title"] and items[0]["title"] != "Error" else None
            time.sleep(3.5)
        if "doi" in p:
            d = http_json(f"https://api.crossref.org/works/{urllib.parse.quote(p['doi'])}")
            m = (d or {}).get("message")
            rec["found"]["crossref"] = None if not m else {
                "title": (m.get("title") or [None])[0], "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in m.get("author", [])],
                "year": ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0], "venue": (m.get("container-title") or [None])[0], "doi": m.get("DOI", "").lower()}
        title = (rec["found"].get("arxiv") or rec["found"].get("crossref") or {}).get("title") or p.get("title")
        if title:
            d = http_json("https://api.openalex.org/works?" + urllib.parse.urlencode({"search": title, "per-page": "5"}))
            hits = [from_openalex(w) for w in (d or {}).get("results", [])]
            rec["found"]["openalex"] = next((h for h in hits if norm_title(h["title"]) == norm_title(title)), None)
            time.sleep(1.2)
        log({"type": "priority_check", "target": "arxiv/crossref/openalex", "query": rec["query"],
             "n_results": sum(1 for v in rec["found"].values() if v), "status": "ok"})
        out.append(rec)
    (AUDIT / "priority_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for r in out:
        f = r["found"]
        print(r["label"], "|", {k: (v or {}).get("title") for k, v in f.items()})


# 既存ノードの本文の参考文献リストから取ったタイトル（OpenAlex に参考文献の登録が無い論文の追跡に用いる）
TEXT_REFERENCES = {
    "robust_turbo_ddcm": [
        "Generative adversarial networks for extreme learned image compression",
        "Improving statistical fidelity for neural image compression with implicit local likelihood models",
        "Deep learning-based image compression for wireless communications: impacts on reliability, throughput, and latency",
        "Lossy image compression with foundation diffusion models",
        "Algorithms for the communication of samples",
        "Lossy compression with gaussian diffusion",
        "Lossy compression with pretrained diffusion models",
        "Stablecodec: Taming one-step diffusion for extreme image compression",
    ],
}


def cmd_textrefs():
    """本文の参考文献リストのタイトルを OpenAlex で照合する（参考文献の追跡の補完）．

    Returns:
        None
    """
    for node_id, titles in TEXT_REFERENCES.items():
        name = f"textrefs_{node_id}"
        records = []
        for title in tqdm(titles, leave=False):
            d = http_json("https://api.openalex.org/works?" + urllib.parse.urlencode({"search": title, "per-page": "5"}))
            hits = [from_openalex(w) for w in (d or {}).get("results", [])]
            hit = next((h for h in hits if norm_title(h["title"]) == norm_title(title)), None)
            if hit:
                records.append(dict(hit, relation="reference"))
            log({"type": "text_reference", "target": "openalex", "seed": node_id, "query": title,
                 "n_results": 1 if hit else 0, "status": "ok" if d is not None else "failed"})
            time.sleep(1.5)
        save(name, records)
        print(f"[textrefs] {node_id}: {len(records)}/{len(titles)} 件を照合")


if __name__ == "__main__":
    {"inventory": cmd_inventory, "search": cmd_search, "snowball": cmd_snowball, "priority": cmd_priority, "textrefs": cmd_textrefs}[sys.argv[1]](*sys.argv[2:])
