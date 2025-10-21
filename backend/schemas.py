from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class LogLine(BaseModel):
    ts: Optional[str] = None
    level: Optional[str] = None
    service: Optional[str] = None
    host: Optional[str] = None
    code: Optional[str] = None
    message: str
    attrs: Dict[str, Any] = {}

class RuleHit(BaseModel):
    rule_id: str
    label: str
    severity: str
    root_cause: str
    recommend: List[str]

class Incident(BaseModel):
    label: str
    severity: str
    confidence: float
    service: Optional[str] = None
    code: Optional[str] = None
    count: int
    start: Optional[str] = None
    end: Optional[str] = None
    samples: List[LogLine]
    why: Dict[str, Any]

class AnalyzeResponse(BaseModel):
    incidents: List[Incident]
    totals: Dict[str, int]