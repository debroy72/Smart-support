import random, datetime as dt
SERVICES = ["auth-service","order-service","licensing-service","inventory-service"]
TEMPLATE = [
 ("license_expired","[ERROR] licensing-service - error detected during license check for user {id} (expired)"),
 ("db_timeout","[ERROR] order-service - Database connection timed out after {sec}s"),
 ("auth_failed","[ERROR] auth-service - authentication failed for user {email}"),
]
def gen_line(ts, tpl):
    label, msg = tpl
    msg = msg.format(id=random.randint(1000,9999), sec=random.randint(5,60), email=f"user{random.randint(1,999)}@example.com")
    return f"{ts} {msg}"
def generate(n=500, start=None):
    t = dt.datetime.utcnow() if not start else start
    out=[]
    for i in range(n):
        ts = (t + dt.timedelta(seconds=i*random.randint(1,3))).strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append(gen_line(ts, random.choice(TEMPLATE)))
    return "\n".join(out)
if __name__ == "__main__":
    print(generate())