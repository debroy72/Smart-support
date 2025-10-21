from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Set, Optional
from collections import Counter
import time, json

# --- Core modules (present in your repo) ---
from .parser import parse_text_log
from .detector import load_rules, apply_rules, aggregate_incidents
from .recommender import make_summary
from .ml import load_model, predict
from .pdf_report import generate_summary_pdf

# --- Optional modules (v2 features). We degrade gracefully if they are missing. ---
try:
    from .cluster import cluster_messages           # unsupervised clustering
except Exception:
    cluster_messages = None  # type: ignore

try:
    from .sop_index import build_index              # SOP reindex
except Exception:
    build_index = None  # type: ignore

try:
    from .chatbot import answer                     # RAG answer
except Exception:
    answer = None  # type: ignore

try:
    from .recommender import enrich_with_sop        # SOP links/snippets
except Exception:
    def enrich_with_sop(incidents):                 # no-op fallback
        return incidents

try:
    from .compliance import compliance_score        # scoring
except Exception:
    def compliance_score(_):                        # default 100 if module not present
        return 100


app = FastAPI(title="SmartSupport API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RULES = load_rules("backend/rules.yaml")
MODEL = load_model()
FEEDBACK_PATH = "backend/feedback.jsonl"


# ---------------------------
# Health & rules
# ---------------------------
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/rules")
def rules():
    return [{
        "id": r.id,
        "pattern": r.pattern.pattern,
        "label": r.label,
        "severity": r.severity
    } for r in RULES]


# ---------------------------
# Analyze
# ---------------------------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = (await file.read()).decode(errors="ignore")
    lines = parse_text_log(raw)

    # Totals by level
    totals: Dict[str, int] = {"TOTAL": len(lines)}
    for ln in lines:
        lvl = (ln.get("level") or "").upper()
        if lvl:
            totals[lvl] = totals.get(lvl, 0) + 1

    # Rule hits
    hits = apply_rules(lines, RULES)
    matched_ids: Set[int] = {id(ln) for ln, _ in hits}

    # Simple anomaly detection (per-minute volume spike)
    def minute_bucket(ts): return ts[:16] if ts else None
    buckets = Counter(minute_bucket(ln.get("ts")) for ln in lines if ln.get("ts"))
    series = [c for _, c in sorted(buckets.items())]
    spikes = []
    if series:
        import statistics as st
        med = st.median(series)
        mad = st.median([abs(x - med) for x in series]) or 1
        for k, c in sorted(buckets.items()):
            if k and (c - med) / mad > 6:
                spikes.append(k)

    # ML fallback for non-rule WARN/ERROR lines
    ml_incidents = []
    if MODEL:
        to_pred = [
            ln for ln in lines
            if id(ln) not in matched_ids and (ln.get("level") or "").upper() in {"WARN", "ERROR"}
        ]
        preds = predict(MODEL, [ln.get("message", "") for ln in to_pred])
        by_label: Dict[str, Dict] = {}
        for ln, pr in zip(to_pred, preds):
            if pr.get("confidence", 0) < 0.80:
                continue
            b = by_label.setdefault(
                pr["label"],
                {
                    "label": pr["label"],
                    "severity": "Medium",
                    "confidence": pr["confidence"],
                    "count": 0,
                    "samples": [],
                    "why": {"model": "vector-clf"},
                    "root_cause": "Model-predicted category",
                    "recommend": [
                        "Investigate recent changes",
                        "Check related service logs"
                    ],
                },
            )
            b["count"] += 1
            if len(b["samples"]) < 5:
                b["samples"].append(ln)
        ml_incidents = list(by_label.values())

    # Aggregate and enrich
    incidents = aggregate_incidents(hits)
    incidents.extend(ml_incidents)
    incidents = enrich_with_sop(incidents)
    summary = make_summary(incidents, totals)

    payload = {
        "incidents": incidents,
        "totals": totals,
        "summary": summary,
        "anomaly": {"spikes": spikes},
        "compliance": {"score": compliance_score(incidents)},
    }
    return JSONResponse(content=payload)


# ---------------------------
# Feedback
# ---------------------------
@app.post("/feedback")
def feedback(item: dict = Body(...)):
    item["ts"] = time.time()
    with open(FEEDBACK_PATH, "a") as f:
        f.write(json.dumps(item) + "\n")
    return {"ok": True}


# ---------------------------
# PDF Report
# ---------------------------
@app.post("/report")
async def report(file: UploadFile = File(...)):
    raw = (await file.read()).decode(errors="ignore")
    lines = parse_text_log(raw)

    totals: Dict[str, int] = {"TOTAL": len(lines)}
    for ln in lines:
        lvl = (ln.get("level") or "").upper()
        if lvl:
            totals[lvl] = totals.get(lvl, 0) + 1

    hits = apply_rules(lines, RULES)
    incidents = aggregate_incidents(hits)
    incidents = enrich_with_sop(incidents)
    summary = make_summary(incidents, totals)

    data = {"incidents": incidents, "totals": totals, "summary": summary}
    pdf_path = generate_summary_pdf(data)
    return FileResponse(pdf_path, filename="SmartSupport_Report.pdf", media_type="application/pdf")


# ---------------------------
# Ingest (raw text POST)
# ---------------------------
@app.post("/ingest")
async def ingest(payload: dict = Body(...)):
    text = payload.get("text", "")
    lines = parse_text_log(text)
    return {"ok": True, "count": len(lines), "preview": lines[:5]}


# ---------------------------
# Clusterize (unknown pattern discovery)
# ---------------------------
@app.post("/clusterize")
async def clusterize(file: UploadFile = File(...)):
    if cluster_messages is None:
        return JSONResponse(
            status_code=501,
            content={"ok": False, "error": "Clustering module not available. Install extras and add backend/cluster.py."},
        )

    raw = (await file.read()).decode(errors="ignore")
    lines = parse_text_log(raw)
    msgs = [ln.get("message", "") for ln in lines if (ln.get("level") or "").upper() in {"ERROR", "WARN"}]
    result = cluster_messages(msgs)

    # mark "new error pattern" clusters = not matched by rules
    hits = apply_rules(lines, RULES)
    matched_texts = {t[0]["message"] for t in hits}
    clusters: Dict[int, Dict] = {}
    for msg, label in zip(msgs, result.get("labels", [])):
        if label == -1:
            continue
        c = clusters.setdefault(label, {"count": 0, "samples": [], "known": False})
        c["count"] += 1
        if len(c["samples"]) < 5:
            c["samples"].append(msg)
        if msg in matched_texts:
            c["known"] = True

    unknown = {k: v for k, v in clusters.items() if not v["known"]}
    return {
        "summary": {"clusters": len(clusters), "unknown": len(unknown)},
        "clusters": clusters,
        "unknown": unknown,
        "raw": result,
    }


# ---------------------------
# SOP indexing & Chat (RAG)
# ---------------------------
@app.post("/sop/reindex")
def sop_reindex():
    if build_index is None:
        return JSONResponse(
            status_code=501,
            content={"ok": False, "error": "SOP indexer not available. Add backend/sop_index.py and dependencies."},
        )
    n = build_index()
    return {"ok": True, "docs_indexed": n}


@app.post("/chat")
def chat(payload: dict = Body(...)):
    if answer is None:
        return JSONResponse(
            status_code=501,
            content={"ok": False, "error": "Chatbot not available. Add backend/chatbot.py and SOP index."},
        )
    q = payload.get("q", "")
    return answer(q)