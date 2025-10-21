# backend/nlp.py
from sentence_transformers import SentenceTransformer
import numpy as np
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def embed_texts(texts):
    m = get_model()
    vecs = m.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vecs.astype(np.float32)