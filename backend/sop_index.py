# backend/sop_index.py  (FAISS-free, robust)
import os, glob, joblib
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

BASE_DIR  = os.path.dirname(__file__)
INDEX_DIR = os.path.join(BASE_DIR, "data")
DOC_DIR   = os.path.join(BASE_DIR, "sop_docs")

VEC_PATH  = os.path.join(INDEX_DIR, "sop_vec.joblib")
NN_PATH   = os.path.join(INDEX_DIR, "sop_nn.joblib")
TXT_PATH  = os.path.join(INDEX_DIR, "sop_texts.joblib")
META_PATH = os.path.join(INDEX_DIR, "sop_meta.joblib")

def _ensure_dirs():
    os.makedirs(INDEX_DIR, exist_ok=True)
    os.makedirs(DOC_DIR, exist_ok=True)

def build_index(folder: str = None) -> int:
    _ensure_dirs()
    folder = folder or DOC_DIR
    files = sorted(glob.glob(os.path.join(folder, "*")))
    texts, meta = [], []
    for fp in files:
        try:
            txt = open(fp, "rb").read().decode(errors="ignore").strip()
        except Exception:
            txt = ""
        if not txt:
            continue
        texts.append(txt)
        meta.append({"path": fp})

    if not texts:
        # Save empty index to avoid crashes
        joblib.dump(None, VEC_PATH)
        joblib.dump(None, NN_PATH)
        joblib.dump([], TXT_PATH)
        joblib.dump([], META_PATH)
        return 0

    vec = TfidfVectorizer(max_features=50000, ngram_range=(1, 2))
    X = vec.fit_transform(texts)

    nn = NearestNeighbors(metric="cosine", n_neighbors=3, algorithm="brute")
    nn.fit(X)

    joblib.dump(vec, VEC_PATH)
    joblib.dump(nn, NN_PATH)
    joblib.dump(texts, TXT_PATH)
    joblib.dump(meta, META_PATH)
    return len(texts)

def search(q: str, k: int = 3) -> List[Dict]:
    _ensure_dirs()
    # If index not built or empty, return []
    if not (os.path.exists(VEC_PATH) and os.path.exists(NN_PATH)
            and os.path.exists(TXT_PATH) and os.path.exists(META_PATH)):
        return []
    vec = joblib.load(VEC_PATH)
    nn  = joblib.load(NN_PATH)
    texts = joblib.load(TXT_PATH)
    meta  = joblib.load(META_PATH)
    if vec is None or nn is None or not texts:
        return []

    q = (q or "").strip()
    if not q:
        return []

    qv = vec.transform([q])
    n  = min(k, len(texts))
    dist, idx = nn.kneighbors(qv, n_neighbors=n)
    hits = []
    for i, d in zip(idx[0], dist[0]):
        hits.append({"path": meta[i]["path"], "score": float(1 - d)})
    return hits