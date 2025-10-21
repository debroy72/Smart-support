import re
import yaml
from collections import defaultdict
from typing import List, Dict, Any

from .schemas import LogLine


class Rule:
    def __init__(self, id, pattern, label, severity, root_cause, recommend):
        self.id = id
        self.pattern = re.compile(pattern)
        self.label = label
        self.severity = severity
        self.root_cause = root_cause
        self.recommend = recommend

    def hit(self, line: Dict[str, Any]):
        msg = line.get("message", "") or ""
        m = self.pattern.search(msg)
        return m


def load_rules(path: str) -> List[Rule]:
    items = yaml.safe_load(open(path))
    return [Rule(i['id'], i['pattern'], i['label'], i['severity'],
                 i['root_cause'], i['recommend']) for i in items]


def apply_rules(lines: List[Dict[str, Any]], rules: List[Rule]):
    hits = []
    for ln in lines:
        matched = []
        for r in rules:
            m = r.hit(ln)
            if m:
                matched.append({
                    "rule_id": r.id,
                    "label": r.label,
                    "severity": r.severity,
                    "root_cause": r.root_cause,
                    "recommend": r.recommend,
                    "spans": [m.span()],
                })
        if matched:
            hits.append((ln, matched))
    return hits


from collections import defaultdict
from typing import List, Dict, Any

def aggregate_incidents(rule_hits: List):
    buckets = defaultdict(list)
    for ln, matched in rule_hits:
        m = matched[0]
        # Group by label only (not service or code) → merges duplicates
        key = m['label']
        buckets[key].append((ln, m))

    incidents = []
    for label, vals in buckets.items():
        lines = [v[0] for v in vals]
        sev = vals[0][1]['severity']
        rc = vals[0][1]['root_cause']
        rec = vals[0][1]['recommend']
        start = lines[0].get('ts')
        end = lines[-1].get('ts')

        # Combine across multiple services
        services = list({ln.get('service') for ln, _ in vals if ln.get('service')})
        codes = list({ln.get('code') for ln, _ in vals if ln.get('code')})

        incidents.append({
            "label": label,
            "severity": sev,
            "confidence": 0.95,
            "service": ", ".join(services) if services else None,
            "code": ", ".join(codes) if codes else None,
            "count": len(lines),
            "start": start,
            "end": end,
            "samples": lines[:5],
            "why": {"rule_id": vals[0][1]['rule_id'], "matches": len(vals)},
            "root_cause": rc,
            "recommend": rec
        })

    incidents.sort(key=lambda x: (x['severity'] != 'High', -x['count']))
    return incidents