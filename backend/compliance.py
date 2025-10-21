# backend/compliance.py
def compliance_score(incidents):
    score = 100
    # knock points by severity & count
    for inc in incidents:
        if inc["severity"] == "High": score -= min(30, inc["count"]*5)
        elif inc["severity"] == "Medium": score -= min(15, inc["count"]*3)
    # boost if recommendations exist
    if any(inc.get("recommend") for inc in incidents): score += 5
    return max(0, min(100, score))