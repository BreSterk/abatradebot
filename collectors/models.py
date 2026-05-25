from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

class Signal(BaseModel):
    id: str = ""
    ticker: str
    source: str
    category: str
    raw_score: float
    confidence: float
    event_time: datetime
    ingestion_time: datetime
    expected_horizon_hours: int
    decay_rate: float
    catalyst_type: str
    raw_text: str
    metadata: dict = {}

    def __init__(self, **data):
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        if not data.get("ingestion_time"):
            data["ingestion_time"] = datetime.utcnow()
        super().__init__(**data)

class TradeDecision(BaseModel):
    id: str = ""
    ticker: str 
    decision: str                  # BUY / SELL / WAIT
    conviction: float
    uncertainty: float
    position_size_pct: float = 0.0
    thesis: str
    counter_argument: str
    invalidators: list[str] = []
    time_horizon_days: int = 0
    tp_logic: str = ""
    sl_logic: str = ""
    missing_data: str = ""
    wait_reason: Optional[str] = None
    timestamp: datetime = None
    agent_outputs: dict = {}

    def __init__(self, **data):
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        if not data.get("timestamp"):
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)

class Position(BaseModel):
    id: str = ""
    ticker: str
    entry_price: float
    current_price: float
    size_pct: float
    decision_id: str
    opened_at: datetime = None
    invalidators: list[str] = []
    time_horizon_days: int = 0
    original_catalyst: str = ""
    status: str = "open"

    def __init__(self, **data):
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        if not data.get("opened_at"):
            data["opened_at"] = datetime.utcnow()
        super().__init__(**data)