#!/usr/bin/env python3
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "stress_1000.log"
random.seed(42)

start = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

services = [
    ("api-server",   "host1"),
    ("db-service",   "host2"),
    ("auth-service", "host4"),
    ("scheduler",    "host3"),
    ("queue-worker", "host5"),
    ("cache-service","host6"),
    ("inventory",    "host7"),
    ("payment",      "host8"),
]

# Known-error templates (match your rules.yaml)
KNOWN_ERRORS = [
    # Database timeout
    ('db-service', "Database connection timed out after 30s"),
    ('db-service', "Database connection refused"),
    ('api-server', "Database timed out for endpoint /user"),
    # Auth failed
    ('auth-service', "authentication failed for user alice@example.com"),
    ('auth-service', "invalid credentials for user bob@example.com"),
    # License problems
    ('scheduler', "license expired for org_id=8831"),
    ('scheduler', "License validation failed: expired token"),
    # Null pointer / reference
    ('inventory', "NoneType object has no attribute 'id'"),
    ('inventory', "NullPointerException while processing item"),
]

# Unknown-error templates (to exercise clustering)
UNKNOWN_ERRORS = [
    ('payment', "Payment gateway returned 401 Unauthorized"),
    ('api-server', "upstream 502 Bad Gateway from shipping-service"),
    ('queue-worker', "Job invoice_sync failed permanently: HTTP 504"),
    ('analytics', "IndexError: list index out of range"),
    ('reporting', "division by zero in metrics aggregation"),
]

INFOS = [
    "Request started for /login",
    "Response 200 OK /login user=alice",
    "Healthcheck passed (latency=90ms)",
    "cleanup finished successfully",
    "processed 234 transactions successfully",
    "Cache warmup complete",
]
WARNS = [
    "Slow query detected: SELECT * FROM orders WHERE ...",
    "Retry #3 for job=invoice_sync",
    "High latency detected: 2100ms",
    "cache miss ratio 18%",
]

def fmt(ts, level, svc, host, msg):
    return f"{ts.strftime('%Y-%m-%dT%H:%M:%SZ')} [{level}] {svc} {host} - {msg}"

lines = []
current = start

# Strategy:
# - Generate 1,000 lines over ~2 hours
# - Every 5 minutes: produce a "burst" minute with 12–20 ERROR lines
# - Other minutes: a mix of INFO/WARN/occasional ERROR

minute = 0
while len(lines) < 1000:
    minute_ts = start + timedelta(minutes=minute)
    burst = (minute % 5 == 0)  # every 5 minutes

    if burst:
        # Burst: 12–20 ERRORs within the same minute, mixed known/unknown
        n_err = random.randint(12, 20)
        for i in range(n_err):
            ts = minute_ts + timedelta(seconds=random.randint(0, 59))
            if random.random() < 0.75:
                svc, msg = random.choice(KNOWN_ERRORS)
            else:
                svc, msg = random.choice(UNKNOWN_ERRORS)
            host = random.choice([h for s, h in services if s == svc] + ["srv-zz"])
            lines.append(fmt(ts, "ERROR", svc, host, msg))
        # plus a couple of WARN/INFO for flavor
        for _ in range(random.randint(2, 5)):
            svc, host = random.choice(services)
            ts = minute_ts + timedelta(seconds=random.randint(0, 59))
            msg = random.choice(WARNS)
            lines.append(fmt(ts, "WARN", svc, host, msg))
        for _ in range(random.randint(2, 4)):
            svc, host = random.choice(services)
            ts = minute_ts + timedelta(seconds=random.randint(0, 59))
            msg = random.choice(INFOS)
            lines.append(fmt(ts, "INFO", svc, host, msg))
    else:
        # Normal minute: 5–10 lines, mostly INFO/WARN, rare ERROR
        n = random.randint(5, 10)
        for _ in range(n):
            svc, host = random.choice(services)
            ts = minute_ts + timedelta(seconds=random.randint(0, 59))
            r = random.random()
            if r < 0.70:
                msg = random.choice(INFOS)
                level = "INFO"
            elif r < 0.95:
                msg = random.choice(WARNS)
                level = "WARN"
            else:
                # occasional error
                if random.random() < 0.7:
                    svc, msg = random.choice(KNOWN_ERRORS)
                else:
                    svc, msg = random.choice(UNKNOWN_ERRORS)
                host = random.choice([h for s, h in services if s == svc] + ["srv-yy"])
                level = "ERROR"
            lines.append(fmt(ts, level, svc, host, msg))

    minute += 1

# Sort globally by timestamp and trim exactly 1000 lines
lines.sort()
lines = lines[:1000]

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {len(lines)} lines to {OUT}")