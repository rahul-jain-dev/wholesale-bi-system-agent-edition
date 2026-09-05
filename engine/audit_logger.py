"""
Lightweight audit trail module for a Revenue Recovery Agent.
Writes to a single canonical CSV file at data/recovery_audit.csv.
"""

import csv
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    AGENT_QUERY = "AGENT_QUERY"
    TOOL_CALL = "TOOL_CALL"
    CAMPAIGN_START = "CAMPAIGN_START"
    CAMPAIGN_END = "CAMPAIGN_END"
    RECOVERY_ACTION = "RECOVERY_ACTION"
    STATE_TRANSITION = "STATE_TRANSITION"
    PAYMENT_OUTCOME = "PAYMENT_OUTCOME"

_AUDIT_COLUMNS = [
    "timestamp", "event_type", "campaign_id", "customer_name", "previous_state",
    "new_state", "action", "reason", "risk_tier", "collection_probability",
    "outstanding_amount", "amount_targeted", "amount_recovered", "attempt_number",
    "actor", "simulation_result"
]

_CSV_PATH = Path(__file__).parent.parent / "data" / "recovery_audit.csv"


def log_event(
    event_type: str,
    campaign_id: str = "",
    customer_name: str = "",
    previous_state: str = "",
    new_state: str = "",
    action: str = "",
    reason: str = "",
    risk_tier: str = "",
    collection_probability: float = 0.0,
    outstanding_amount: float = 0.0,
    amount_targeted: float = 0.0,
    amount_recovered: float = 0.0,
    attempt_number: int = 0,
    actor: str = "recovery_agent",
    simulation_result: str = "",
) -> None:
    """Appends a single row to the audit CSV."""
    _CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = _CSV_PATH.exists()
    
    with open(_CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists or _CSV_PATH.stat().st_size == 0:
            writer.writerow(_AUDIT_COLUMNS)
            
        timestamp = datetime.now(timezone.utc).isoformat()
        row = [
            timestamp, event_type, campaign_id, customer_name, previous_state,
            new_state, action, reason, risk_tier, collection_probability,
            outstanding_amount, amount_targeted, amount_recovered, attempt_number,
            actor, simulation_result
        ]
        writer.writerow(row)
    logger.debug(f"Logged {event_type} for campaign {campaign_id}")


def get_audit_log(campaign_id: Optional[str] = None) -> pd.DataFrame:
    """Reads the CSV into a DataFrame, optionally filtered by campaign_id."""
    if not _CSV_PATH.exists() or _CSV_PATH.stat().st_size == 0:
        return pd.DataFrame(columns=_AUDIT_COLUMNS)
        
    try:
        df = pd.read_csv(_CSV_PATH)
    except Exception as e:
        logger.error(f"Error reading audit log: {e}")
        return pd.DataFrame(columns=_AUDIT_COLUMNS)
        
    if campaign_id:
        df = df[df["campaign_id"] == campaign_id]
        
    return df


def clear_audit_log() -> None:
    """Deletes the CSV file if it exists."""
    if _CSV_PATH.exists():
        try:
            _CSV_PATH.unlink()
            logger.info("Cleared audit log.")
        except Exception as e:
            logger.error(f"Failed to clear audit log: {e}")
