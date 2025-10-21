# backend/ml.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
import joblib, os

MODEL_PATH = "backend/model.joblib"

def train_and_save(train_texts, labels):
    pipe = make_pipeline(
        TfidfVectorizer(max_features=30000, ngram_range=(1,2)),
        LogisticRegression(max_iter=1000)  # exposes predict_proba
    )
    pipe.fit(train_texts, labels)
    joblib.dump(pipe, MODEL_PATH)

def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

def predict(model, texts):
    if not texts:
        return []
    probs = model.predict_proba(texts)
    classes = model.classes_
    out = []
    for i, p in enumerate(probs):
        idx = p.argmax()
        out.append({"label": classes[idx], "confidence": float(p[idx]), "text": texts[i]})
    return out