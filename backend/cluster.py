# backend/cluster.py
"""
Resilient clustering:
- Preferred: HDBSCAN over sentence-embeddings (dense)  -> labels incl. -1 for noise
- Fallback:  MiniBatchKMeans over TF-IDF (sparse)      -> labels in [0..k-1]
Returns a consistent payload with sizes, n_clusters, and engine name.
"""

from typing import List, Dict, Optional
import math

# Optional deps
try:
    import hdbscan  # type: ignore
except Exception:  # pragma: no cover
    hdbscan = None  # type: ignore

try:
    from .nlp import embed_texts  # uses sentence-transformers if installed
except Exception:  # pragma: no cover
    embed_texts = None  # type: ignore

# Fallback (always available in our stack)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans


def _summarize_labels(labels) -> Dict:
    sizes: Dict[int, int] = {}
    for l in labels:
        sizes[l] = sizes.get(l, 0) + 1
    n_clusters = len([k for k in sizes.keys() if k != -1])
    return {"sizes": sizes, "n_clusters": n_clusters}


def _cluster_hdbscan(msgs: List[str], min_cluster_size: int, min_samples: int) -> Dict:
    # guard: require both hdbscan and embed_texts
    if hdbscan is None or embed_texts is None:
        raise RuntimeError("HDBSCAN or embeddings unavailable")

    X = embed_texts(msgs)  # (N, d) float32
    if X.shape[0] < max(10, min_cluster_size):
        labels = [-1] * len(msgs)
        out = _summarize_labels(labels)
        return {
            "labels": labels,
            "prob": None,
            "engine": "hdbscan+embeddings",
            **out,
        }

    cl = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
    )
    labels = cl.fit_predict(X).tolist()
    out = _summarize_labels(labels)
    prob = getattr(cl, "probabilities_", None)
    return {
        "labels": labels,
        "prob": prob.tolist() if prob is not None else None,
        "engine": "hdbscan+embeddings",
        **out,
    }


def _cluster_kmeans_tfidf(msgs: List[str]) -> Dict:
    # TF-IDF features (1–2 grams) + MiniBatchKMeans
    vec = TfidfVectorizer(max_features=30000, ngram_range=(1, 2))
    X = vec.fit_transform(msgs)

    n = X.shape[0]
    # Heuristic for k: ~sqrt(n/8), clamped 2..12
    k = max(2, min(12, int(math.sqrt(max(2, n // 8)))))

    km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init="auto")
    labels = km.fit_predict(X).tolist()  # 0..k-1 (no -1 noise)

    sizes: Dict[int, int] = {}
    for l in labels:
        sizes[l] = sizes.get(l, 0) + 1

    return {
        "labels": labels,
        "prob": None,
        "sizes": sizes,
        "n_clusters": k,
        "engine": "kmeans+tfidf",
    }


def cluster_messages(
    msgs: List[str],
    min_cluster_size: int = 5,
    min_samples: int = 1,
    mode: Optional[str] = None,  # "hdbscan" | "kmeans" | None (auto)
) -> Dict:
    """
    Cluster log messages. Prefers HDBSCAN+embeddings if available, else TF-IDF+KMeans.
    - msgs: list of raw message strings
    - min_cluster_size/min_samples: used by HDBSCAN path
    - mode: force "hdbscan" or "kmeans"; None chooses automatically
    Returns:
      {
        "labels": List[int],         # cluster id per message; -1 means noise (only in HDBSCAN)
        "n_clusters": int,           # excludes noise (-1)
        "sizes": Dict[int, int],     # cluster_id -> count
        "prob": Optional[List[float]],  # HDBSCAN probabilities or None
        "engine": str                # which engine was used
      }
    """
    clean = [m for m in (msgs or []) if (m or "").strip()]
    if len(clean) < 2:
        return {"labels": [-1] * len(msgs), "n_clusters": 0, "sizes": {}, "prob": None, "engine": "none"}

    # Try preferred path if requested or available
    if mode == "hdbscan" or (mode is None and hdbscan is not None and embed_texts is not None):
        try:
            return _cluster_hdbscan(clean, min_cluster_size, min_samples)
        except Exception:
            # Fall back silently to kmeans if HDBSCAN/embeddings fail at runtime
            pass

    # Fallback path
    return _cluster_kmeans_tfidf(clean)