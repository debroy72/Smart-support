import re
from dateutil import parser as dtparser
from typing import Dict, Any, List

TS_RGX = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s+\[(?P<level>[A-Z]+)\]\s+(?P<service>[\w-]+)\s+(?P<host>[\w-]+)\s+-\s+(?P<msg>.*)$"
)
def parse_text_log(text: str) -> List[Dict[str, Any]]:
    lines = text.splitlines()
    out: List[Dict[str, Any]] = []
    buf: List[str] = []

    def flush(buf):
        if not buf: return
        head = buf[0]
        m = TS_RGX.match(head)
        if m:
            d = m.groupdict()
            entry = {
                "ts": d["ts"],
                "level": d.get("level"),
                "service": d.get("service"),
                "host": d.get("host"),
                "code": None,
                "message": d.get("msg") if len(buf)==1 else "\n".join([d.get("msg")] + buf[1:]),
                "attrs": {}
            }
            out.append(entry)
        buf.clear()

    for raw in lines:
        if TS_RGX.match(raw):
            flush(buf)
            buf.append(raw)
        else:
            # continuation (stack trace)
            if not buf: # orphan line, treat as message only
                out.append({"ts": None, "level": None, "service": None, "host": None, "code": None, "message": raw, "attrs": {}})
            else:
                buf.append(raw)
    flush(buf)
    return out