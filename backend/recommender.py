# backend/recommender.py (extend)
import yaml, os
SOP = yaml.safe_load(open("backend/sop_map.yaml")) if os.path.exists("backend/sop_map.yaml") else {}

def enrich_with_sop(incidents):
    for inc in incidents:
        meta = SOP.get(inc["label"], {})
        inc["sop_links"] = meta.get("links", [])
        inc["sop_snippets"] = meta.get("snippets", [])
    return incidents

def make_summary(incidents, totals):
    return {
        "headline": f"Found {totals.get('ERROR', 0)} errors across {len(incidents)} incident types",
        "top": incidents[:3]
    }