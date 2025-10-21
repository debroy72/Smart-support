# backend/chatbot.py
from typing import Dict, Any
from .sop_index import search

def answer(q: str) -> Dict[str, Any]:
    q = (q or "").strip()
    if not q:
        return {"answer": "Please provide a question.", "sources": []}

    hits = search(q, k=3)
    if not hits:
        return {
            "answer": "I couldn't find a matching SOP yet. Try reindexing or adding docs to backend/sop_docs.",
            "sources": []
        }

    sources = []
    for h in hits:
        try:
            with open(h["path"], "rb") as f:
                txt = f.read().decode(errors="ignore")
            excerpt = txt[:500].strip().replace("\n", " ")
        except Exception:
            excerpt = ""
        sources.append({
            "path": h["path"],
            "score": round(h["score"], 3),
            "excerpt": (excerpt + "...") if len(excerpt) == 500 else excerpt
        })

    summary = "Here are the most relevant SOP sections. Open the cited files for step-by-step guidance."
    return {"answer": summary, "sources": sources}