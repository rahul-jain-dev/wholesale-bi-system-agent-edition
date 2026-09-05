"""
Revenue Recovery Engine

This module provides the core logic for the Wholesale BI System's AI Revenue Recovery.
It handles state transitions, deterministic simulations, and orchestration of recovery campaigns.
"""

from __future__ import annotations

import logging
import hashlib
from typing import Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import date, datetime
import pandas as pd

from engine.payment_intelligence import score_payment_risk, generate_collection_message
from engine.audit_logger import log_event

logger = logging.getLogger(__name__)

# --- Configuration & Policy ---

class RecoveryState(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    FIRST_REMINDER = "FIRST_REMINDER"
    WAITING_FOR_PAYMENT = "WAITING_FOR_PAYMENT"
    SECOND_REMINDER = "SECOND_REMINDER"
    ESCALATED = "ESCALATED"
    RECOVERED = "RECOVERED"
    STOPPED = "STOPPED"

_VALID_TRANSITIONS = {
    RecoveryState.IDENTIFIED: [RecoveryState.FIRST_REMINDER, RecoveryState.WAITING_FOR_PAYMENT, RecoveryState.ESCALATED, RecoveryState.STOPPED],
    RecoveryState.FIRST_REMINDER: [RecoveryState.WAITING_FOR_PAYMENT, RecoveryState.ESCALATED, RecoveryState.RECOVERED, RecoveryState.STOPPED],
    RecoveryState.WAITING_FOR_PAYMENT: [RecoveryState.SECOND_REMINDER, RecoveryState.ESCALATED, RecoveryState.RECOVERED, RecoveryState.STOPPED],
    RecoveryState.SECOND_REMINDER: [RecoveryState.WAITING_FOR_PAYMENT, RecoveryState.ESCALATED, RecoveryState.RECOVERED, RecoveryState.STOPPED],
    RecoveryState.ESCALATED: [RecoveryState.RECOVERED, RecoveryState.STOPPED],

    RecoveryState.RECOVERED: [],  # terminal
    RecoveryState.STOPPED: [],    # terminal
}

INTERVENTION_POLICY = {
    "LOW RISK": {"action": "WAIT", "message_tier": None, "contact": False},
    "MEDIUM RISK": {"action": "FIRST_REMINDER", "message_tier": "friendly_reminder", "contact": True},
    "HIGH RISK": {"action": "PAYMENT_LINK", "message_tier": "urgent_collection", "contact": True},
    "WRITE-OFF RISK": {"action": "ESCALATION", "message_tier": "legal_notice", "contact": True},
}

# --- Data Models ---

@dataclass
class Campaign:
    campaign_id: str
    campaign_date: str
    status: str
    started_at: str
    completed_at: str = ""

@dataclass
class CustomerRecoveryRecord:
    customer_name: str
    outstanding_amount: float
    collection_probability: float
    risk_tier: str
    days_overdue: float
    state: RecoveryState = RecoveryState.IDENTIFIED
    attempt_number: int = 0
    last_action_at: str = ""
    next_action_at: str = ""
    promise_to_pay_date: str = ""
    amount_recovered: float = 0.0
    intervention: str = ""
    payment_link: str = ""
    collection_message: str = ""
    priority_score: float = 0.0
    expected_recovery: float = 0.0
    reason: str = ""
    simulation_result: str = ""

# --- Core Functions ---

def calculate_recovery_priority(outstanding_amount: float, collection_probability: float, days_overdue: float) -> float:
    """
    Calculate the expected recoverable value and urgency multiplier to determine priority ordering.
    """
    if days_overdue > 120:
        urgency_multiplier = 2.0
    elif days_overdue > 90:
        urgency_multiplier = 1.8
    elif days_overdue > 60:
        urgency_multiplier = 1.5
    elif days_overdue > 30:
        urgency_multiplier = 1.2
    else:
        urgency_multiplier = 1.0
        
    return round(outstanding_amount * (collection_probability / 100.0) * urgency_multiplier, 2)

def build_recovery_batch(
    sales_df: pd.DataFrame,
    customer_df: Optional[pd.DataFrame] = None,
    exclude_low_risk: bool = True,
) -> tuple[Campaign, list[CustomerRecoveryRecord]]:
    """
    Score risks and construct a prioritized batch of customers to target.
    """
    risk_df = score_payment_risk(sales_df, customer_df)
    
    campaign_id = f"REC-{date.today().isoformat()}-001"
    campaign = Campaign(
        campaign_id=campaign_id,
        campaign_date=date.today().isoformat(),
        status="RUNNING",
        started_at=datetime.now().isoformat()
    )
    
    records = []
    for _, row in risk_df.iterrows():
        risk_tier = row.get('risk_tier', 'LOW RISK')
        
        if exclude_low_risk and risk_tier == "LOW RISK":
            continue
            
        record = CustomerRecoveryRecord(
            customer_name=row['customer_name'],
            outstanding_amount=float(row.get('total_overdue_amount', 0)),
            collection_probability=float(row.get('collection_probability', 0)),
            risk_tier=risk_tier,
            days_overdue=float(row.get('max_days_overdue', 0)),
        )
        
        record.priority_score = calculate_recovery_priority(
            record.outstanding_amount,
            record.collection_probability,
            record.days_overdue
        )
        record.expected_recovery = round(record.outstanding_amount * (record.collection_probability / 100.0), 2)
        records.append(record)
        
    records.sort(key=lambda x: x.priority_score, reverse=True)
    return campaign, records

def choose_intervention(record: CustomerRecoveryRecord) -> str:
    """
    Determine the next action based on policy and state overrides.
    """
    if record.state in (RecoveryState.RECOVERED, RecoveryState.STOPPED):
        return "WAIT"
        
    if record.promise_to_pay_date:
        try:
            ptp_date = date.fromisoformat(record.promise_to_pay_date)
            if ptp_date > date.today():
                return "WAIT"
        except ValueError:
            pass
            
    if record.attempt_number >= 3:
        return "ESCALATION"
        
    policy = INTERVENTION_POLICY.get(record.risk_tier, INTERVENTION_POLICY["LOW RISK"])
    return policy["action"]

def generate_mock_payment_link(customer_name: str, amount: float) -> str:
    """
    Generate a deterministic mock payment link that encodes amount context.
    """
    short_hash = hashlib.sha256(customer_name.encode()).hexdigest()[:8]
    amt_str = f"{amount:.0f}" if amount else "0"
    return f"https://rzp.io/i/{short_hash}?amt={amt_str}"

def execute_recovery_action(
    record: CustomerRecoveryRecord,
    campaign_id: str,
) -> CustomerRecoveryRecord:
    """
    Execute the chosen intervention, perform state transitions, and generate messages.
    """
    intervention = choose_intervention(record)
    record.intervention = intervention
    
    # State transitions
    new_state = record.state
    if intervention == "WAIT":
        if record.state == RecoveryState.IDENTIFIED:
            new_state = RecoveryState.WAITING_FOR_PAYMENT
    elif intervention == "FIRST_REMINDER":
        new_state = RecoveryState.FIRST_REMINDER
    elif intervention == "SECOND_REMINDER":
        new_state = RecoveryState.SECOND_REMINDER
    elif intervention == "PAYMENT_LINK":
        new_state = RecoveryState.WAITING_FOR_PAYMENT
    elif intervention == "ESCALATION":
        new_state = RecoveryState.ESCALATED
        
    if new_state in _VALID_TRANSITIONS.get(record.state, []):
        record.state = new_state
        
    record.attempt_number += 1
    record.last_action_at = datetime.now().isoformat()
    
    # Build reason string
    record.reason = (
        f"Selected: Rs.{record.outstanding_amount:,.0f} outstanding, "
        f"probability {record.collection_probability:.0f}%, "
        f"{int(record.days_overdue)} days overdue, "
        f"priority score {record.priority_score:,.0f}"
    )
    
    policy = INTERVENTION_POLICY.get(record.risk_tier, INTERVENTION_POLICY["LOW RISK"])
    if policy.get("contact"):
        record.payment_link = generate_mock_payment_link(record.customer_name, record.outstanding_amount)
        # Map intervention to recommended_action for message generator
        _action_map = {
            "FIRST_REMINDER": "Routine Follow-up",
            "SECOND_REMINDER": "Call Today",
            "PAYMENT_LINK": "Call Today",
            "ESCALATION": "Legal Notice",
        }
        record.collection_message = generate_collection_message(
            customer_name=record.customer_name,
            overdue_amount=record.outstanding_amount,
            days_overdue=int(record.days_overdue),
            recommended_action=_action_map.get(intervention, "Call Today"),
        )
        
    log_event(
        event_type="RECOVERY_ACTION",
        campaign_id=campaign_id,
        customer_name=record.customer_name,
        previous_state=record.state.value if hasattr(record.state, 'value') else str(record.state),
        new_state=record.state.value,
        action=intervention,
        reason=record.reason,
        risk_tier=record.risk_tier,
        collection_probability=record.collection_probability,
        outstanding_amount=record.outstanding_amount,
        amount_targeted=record.outstanding_amount,
        attempt_number=record.attempt_number,
    )
    
    return record

def simulate_payment_outcome(
    record: CustomerRecoveryRecord,
    campaign_date: str,
) -> CustomerRecoveryRecord:
    """
    Simulate the payment outcome deterministically and progress the state.
    """
    if record.state in (RecoveryState.RECOVERED, RecoveryState.STOPPED):
        return record
        
    seed_str = f"{record.customer_name}:{campaign_date}:{record.intervention}"
    seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
    seed_value = int(seed_hash[:8], 16) / 0xFFFFFFFF
    
    base_prob = record.collection_probability / 100.0
    
    # Relative uplifts (multiplier on base probability)
    uplift = {
        "WAIT": 1.0,
        "FIRST_REMINDER": 1.10,
        "SECOND_REMINDER": 1.15,
        "PAYMENT_LINK": 1.20,
        "ESCALATION": 1.25
    }
    intervention_multiplier = uplift.get(record.intervention, 1.0)
    
    # Attempt penalty (reduces probability on subsequent attempts)
    attempt_multiplier = max(1.0 - (record.attempt_number * 0.1), 0.5)
    
    final_prob = min(max(base_prob * intervention_multiplier * attempt_multiplier, 0.05), 0.95)
    
    recovered = seed_value < final_prob
    
    old_state = record.state
    if recovered:
        record.amount_recovered = round(record.outstanding_amount, 2)
        record.state = RecoveryState.RECOVERED
        record.simulation_result = "PAID"
    else:
        if record.attempt_number >= 3:
            record.state = RecoveryState.ESCALATED
            record.simulation_result = "ESCALATED"
        else:
            record.state = RecoveryState.WAITING_FOR_PAYMENT
            record.simulation_result = "NO_PAYMENT"
            
    # Fallback to current if invalid transition
    if record.state not in _VALID_TRANSITIONS.get(old_state, []):
        if record.state == RecoveryState.WAITING_FOR_PAYMENT and old_state == RecoveryState.WAITING_FOR_PAYMENT:
            pass # Self transition ok in this mock logic
            
    log_event(
        event_type="PAYMENT_OUTCOME",
        campaign_id="",  # filled by caller context
        customer_name=record.customer_name,
        previous_state=old_state.value,
        new_state=record.state.value,
        action=record.intervention,
        reason=f"Simulation: final_prob={final_prob:.2f}, seed={seed_value:.4f}, threshold={'<' if recovered else '>='}",
        risk_tier=record.risk_tier,
        collection_probability=record.collection_probability,
        outstanding_amount=record.outstanding_amount,
        amount_recovered=record.amount_recovered,
        attempt_number=record.attempt_number,
        simulation_result=record.simulation_result,
    )

    return record

def calculate_campaign_metrics(
    records: list[CustomerRecoveryRecord],
    campaign: Campaign,
) -> dict:
    """
    Calculate summary metrics for the campaign execution.
    """
    total_outstanding = round(sum(r.outstanding_amount for r in records), 2)
    amount_recovered = round(sum(r.amount_recovered for r in records), 2)
    expected_recovery = round(sum(r.expected_recovery for r in records), 2)
    
    metrics = {
        "campaign_id": campaign.campaign_id,
        "campaign_date": campaign.campaign_date,
        "total_outstanding": total_outstanding,
        "amount_at_risk": total_outstanding,
        "amount_targeted": total_outstanding,
        "amount_recovered": amount_recovered,
        "remaining_outstanding": round(total_outstanding - amount_recovered, 2),
        "expected_recovery": expected_recovery,
        "actual_recovery": amount_recovered,
        "recovery_rate_pct": round((amount_recovered / total_outstanding * 100) if total_outstanding > 0 else 0, 2),
        "recovery_performance_pct": round((amount_recovered / expected_recovery * 100) if expected_recovery > 0 else 0, 2),
        "customers_targeted": len(records),
        "customers_contacted": sum(1 for r in records if INTERVENTION_POLICY.get(r.risk_tier, {}).get("contact")),
        "customers_recovered": sum(1 for r in records if r.state == RecoveryState.RECOVERED),
        "customers_escalated": sum(1 for r in records if r.state == RecoveryState.ESCALATED),
        "customers_excluded": 0,
        "customers_waiting": sum(1 for r in records if r.state == RecoveryState.WAITING_FOR_PAYMENT),
        "average_attempts_to_recovery": round(
            sum(r.attempt_number for r in records if r.state == RecoveryState.RECOVERED) / 
            max(1, sum(1 for r in records if r.state == RecoveryState.RECOVERED)), 2
        ),
        "intervention_count": sum(r.attempt_number for r in records)
    }
    return metrics

def run_recovery_campaign(
    sales_df: pd.DataFrame,
    customer_df: Optional[pd.DataFrame] = None,
    exclude_low_risk: bool = True,
) -> tuple[Campaign, list[CustomerRecoveryRecord], dict]:
    """
    Orchestrate the complete recovery campaign process.
    
    Steps:
      1. Build prioritized recovery batch from risk scores
      2. Log CAMPAIGN_START
      3. For each customer: choose intervention → execute → simulate outcome
      4. Calculate campaign metrics
      5. Log CAMPAIGN_END
      6. Return (campaign, records, metrics)
    """
    campaign, records = build_recovery_batch(sales_df, customer_df, exclude_low_risk)
    
    # Count excluded customers for metrics
    risk_df = score_payment_risk(sales_df, customer_df)
    excluded_count = len(risk_df[risk_df["risk_tier"] == "LOW RISK"]) if exclude_low_risk else 0
    
    log_event(
        event_type="CAMPAIGN_START",
        campaign_id=campaign.campaign_id,
        action="START",
        reason=f"Targeting {len(records)} customers, excluded {excluded_count} low-risk",
    )
    
    for record in records:
        execute_recovery_action(record, campaign.campaign_id)
        simulate_payment_outcome(record, campaign.campaign_date)
        
    campaign.status = "COMPLETED"
    campaign.completed_at = datetime.now().isoformat()
    
    metrics = calculate_campaign_metrics(records, campaign)
    metrics["customers_excluded"] = excluded_count
    
    log_event(
        event_type="CAMPAIGN_END",
        campaign_id=campaign.campaign_id,
        action="COMPLETE",
        amount_recovered=metrics["amount_recovered"],
        reason=f"Recovery rate: {metrics['recovery_rate_pct']:.1f}%, Performance: {metrics['recovery_performance_pct']:.1f}%",
    )
    
    return campaign, records, metrics

