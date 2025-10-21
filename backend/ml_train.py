from .synth import generate
from .ml import train_and_save

def main():
    # crude labels from templates; use simple heuristics here
    data = generate(600)
    texts, labels = [], []
    for line in data.splitlines():
        msg = line.split(" - ", 1)[-1]
        texts.append(msg)
        if "license" in msg.lower(): labels.append("License Check Failure")
        elif "timed out" in msg.lower(): labels.append("Database Timeout")
        elif "authentication failed" in msg.lower(): labels.append("Authentication Failure")
        elif " 5" in msg: labels.append("HTTP 5xx")
        else: labels.append("Other")
    train_and_save(texts, labels)
    print("Model trained and saved to backend/model.joblib")

if __name__ == "__main__":
    main()