"""
engine/ai_agent.py
==================
ReAct-style Agentic Business Intelligence Engine.

Implements a Reason + Act (ReAct) loop where the agent:
  1. Receives a natural language business question
  2. Thinks about which tool(s) to use
  3. Calls the tool, gets a data observation
  4. Reasons over the observation
  5. Repeats until it can give a grounded final answer

Every answer is backed by real data from the existing engine modules —
no hallucination, no fabricated numbers.

Architecture
------------
  WholesaleAgent
    ├── ToolRegistry      — maps tool names → callable wrappers of engine fns
    ├── AgentContext      — holds loaded DataFrames + formats them as text for LLM
    ├── LLMClient         — Gemini Flash → Groq Llama 3 → rule-based fallback
    └── ReAct loop        — Thought → Action → Observation → repeat → Final Answer

LLM Priority:
  1. Google Gemini Flash  (set GEMINI_API_KEY env var or pass directly)
  2. Groq Llama 3         (set GROQ_API_KEY env var)
  3. Rule-based fallback  (no API key needed — still shows full reasoning trace)

Razorpay Parallels:
  This agent is architecturally similar to Razorpay's "Slash" assistant and
  "Agent Studio" — tools that let business teams query operational data in
  natural language and get grounded, actionable answers.

Author: Wholesale BI System — Agent Edition
Python: 3.12
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_REACT_STEPS = 6          # safety ceiling on reasoning steps
FALLBACK_MODEL  = "rule-based"
GEMINI_MODEL    = "gemini-1.5-flash"      # primary; fallback list tried in _gemini()
GROQ_MODEL      = "llama-3.1-8b-instant"


# ═════════════════════════════════════════════════════════════════════════════
# 1. Agent Step — one round-trip in the ReAct loop
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentStep:
    """Records one full step (Thought → Action → Observation) in the ReAct loop."""
    step_num:    int
    thought:     str
    action:      str
    action_args: dict
    observation: str
    elapsed_ms:  int = 0

    def to_display(self) -> dict:
        return {
            "step":        self.step_num,
            "thought":     self.thought,
            "action":      self.action,
            "observation": self.observation[:800] + ("…" if len(self.observation) > 800 else ""),
        }


@dataclass
class AgentResult:
    """Final output of the agent after completing the ReAct loop."""
    question:     str
    answer:       str
    steps:        list[AgentStep]
    llm_used:     str
    total_ms:     int
    tool_calls:   list[str]
    confidence:   str  # "HIGH" / "MEDIUM" / "LOW"

    @property
    def step_count(self) -> int:
        return len(self.steps)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Agent Context — holds DataFrames + formats text summaries for LLM
# ═════════════════════════════════════════════════════════════════════════════

class AgentContext:
    """
    Packages all loaded business DataFrames into text summaries that the LLM
    can reason over. Keeps summaries short to fit within token limits.
    """

    def __init__(
        self,
        sales_df:     Optional[pd.DataFrame] = None,
        inventory_df: Optional[pd.DataFrame] = None,
        customer_df:  Optional[pd.DataFrame] = None,
        recovery_state: Optional[dict] = None,
    ):
        self.sales_df     = sales_df     if sales_df is not None     else pd.DataFrame()
        self.inventory_df = inventory_df if inventory_df is not None else pd.DataFrame()
        self.customer_df  = customer_df  if customer_df is not None  else pd.DataFrame()
        self.recovery_state = recovery_state if recovery_state is not None else {}


    def is_empty(self) -> bool:
        return self.sales_df.empty and self.inventory_df.empty and self.customer_df.empty

    def business_summary(self) -> str:
        """One-paragraph text summary of the business state for the system prompt."""
        parts = []

        if not self.sales_df.empty:
            n_txn     = len(self.sales_df)
            date_col  = "date" if "date" in self.sales_df.columns else None
            date_range = ""
            if date_col:
                try:
                    dates      = pd.to_datetime(self.sales_df[date_col], errors="coerce").dropna()
                    date_range = f" from {dates.min().date()} to {dates.max().date()}"
                except Exception:
                    pass
            rev = 0.0
            if "sale_price" in self.sales_df.columns and "quantity" in self.sales_df.columns:
                rev = float(
                    (pd.to_numeric(self.sales_df["sale_price"], errors="coerce").fillna(0)
                     * pd.to_numeric(self.sales_df["quantity"], errors="coerce").fillna(0)
                    ).sum()
                )
            parts.append(
                f"Sales: {n_txn:,} transactions{date_range}. "
                f"Total revenue: ₹{rev:,.0f}."
            )

        if not self.inventory_df.empty:
            n_sku = len(self.inventory_df)
            stock_val = 0.0
            if "purchase_price" in self.inventory_df.columns and "quantity_in_stock" in self.inventory_df.columns:
                stock_val = float(
                    (pd.to_numeric(self.inventory_df["purchase_price"],  errors="coerce").fillna(0)
                     * pd.to_numeric(self.inventory_df["quantity_in_stock"], errors="coerce").fillna(0)
                    ).sum()
                )
            parts.append(f"Inventory: {n_sku} SKUs. Estimated stock value: ₹{stock_val:,.0f}.")

        if not self.customer_df.empty:
            n_cust = len(self.customer_df)
            parts.append(f"Customers: {n_cust} retailers/customers in the system.")

        return " ".join(parts) if parts else "No data loaded yet."

    def get_dataframes(self) -> dict[str, pd.DataFrame]:
        return {
            "sales":     self.sales_df,
            "inventory": self.inventory_df,
            "customer":  self.customer_df,
        }


# ═════════════════════════════════════════════════════════════════════════════
# 3. Tool Registry — wraps engine functions as agent-callable tools
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Tool:
    """An agent-callable tool that wraps an engine function."""
    name:        str
    description: str
    fn:          Callable
    category:    str = "analytics"

    def call(self, **kwargs) -> str:
        """Call the tool and return a plain-text observation."""
        try:
            result = self.fn(**kwargs)
            return _format_result(result)
        except Exception as exc:
            return f"Tool error: {exc}"


def _format_result(result: Any) -> str:
    """Convert any engine output (DataFrame, dict, list, str) to readable text."""
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return "No results found."
        # Show top rows as a compact text table
        n = min(10, len(result))
        return f"Found {len(result)} records. Top {n}:\n{result.head(n).to_string(index=False, max_colwidth=40)}"
    if isinstance(result, dict):
        lines = []
        for k, v in result.items():
            if isinstance(v, pd.DataFrame):
                lines.append(f"{k}: {len(v)} records")
            elif isinstance(v, float):
                lines.append(f"{k}: ₹{v:,.2f}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    if isinstance(result, list):
        return "\n".join(str(r) for r in result[:10])
    return str(result)


def build_tool_registry(context: AgentContext) -> dict[str, Tool]:
    """
    Build the complete tool registry by wrapping existing engine functions.
    Each tool receives pre-loaded DataFrames from the context — no re-loading.
    """
    sales     = context.sales_df
    inventory = context.inventory_df
    customers = context.customer_df

    tools: dict[str, Tool] = {}

    # ── Inventory / Dead Stock ─────────────────────────────────────────────
    def _dead_stock():
        from engine.analytics import detect_dead_stock
        if inventory.empty:
            return "No inventory data loaded."
        return detect_dead_stock(inventory)

    tools["get_dead_stock"] = Tool(
        name="get_dead_stock",
        description=(
            "Returns products that haven't sold recently. "
            "Shows days_unsold, capital_blocked (₹), and stock_status (DEAD/SLOW/ACTIVE). "
            "Use when asked about slow-moving stock, dead inventory, or capital blocked in stock."
        ),
        fn=_dead_stock,
        category="inventory",
    )

    # ── Outstanding Payments ───────────────────────────────────────────────
    def _outstanding_payments():
        from engine.analytics import get_outstanding_payments
        if sales.empty:
            return "No sales data loaded."
        return get_outstanding_payments(sales, customers)

    tools["get_outstanding_payments"] = Tool(
        name="get_outstanding_payments",
        description=(
            "Returns overdue customer invoices ranked by urgency. "
            "Shows customer_name, invoice_no, days_overdue, invoice_amount, risk_level (HIGH/MEDIUM/LOW). "
            "Use when asked about payments, collections, who owes money, or cash flow."
        ),
        fn=_outstanding_payments,
        category="payments",
    )

    # ── Payment Risk Score ─────────────────────────────────────────────────
    def _payment_risk():
        from engine.payment_intelligence import score_payment_risk
        if sales.empty:
            return "No sales data loaded."
        return score_payment_risk(sales, customers)

    tools["get_payment_risk_scores"] = Tool(
        name="get_payment_risk_scores",
        description=(
            "Predicts which customers are UNLIKELY to pay. Returns collection_probability (0-100%), "
            "recommended_action (Call/WhatsApp/Legal/Write-off), and risk tier per customer. "
            "Use when asked who won't pay, payment default risk, or collection strategy."
        ),
        fn=_payment_risk,
        category="payments",
    )

    # ── Customer Segments ──────────────────────────────────────────────────
    def _segments():
        from engine.segmentation import compute_rfm, segment_customers
        if sales.empty or customers.empty:
            return "Need both sales and customer data."
        rfm = compute_rfm(sales, customers)
        return segment_customers(rfm)

    tools["get_customer_segments"] = Tool(
        name="get_customer_segments",
        description=(
            "Segments customers into Champions / Loyal / At Risk / Lost using RFM + K-Means. "
            "Use when asked about customer health, churn risk, who to retain, or customer value."
        ),
        fn=_segments,
        category="customers",
    )

    # ── Anomalies ──────────────────────────────────────────────────────────
    def _anomalies():
        from engine.anomaly_detector import detect_anomalies
        if sales.empty:
            return "No sales data loaded."
        df = detect_anomalies(sales)
        return df[df["is_anomaly"] == True] if "is_anomaly" in df.columns else df

    tools["get_anomalies"] = Tool(
        name="get_anomalies",
        description=(
            "Detects suspicious transactions using Isolation Forest. Flags anomalies in "
            "discount_pct, quantity, and price. Use when asked about fraud, suspicious sales, "
            "unusual discounts, or data integrity issues."
        ),
        fn=_anomalies,
        category="anomaly",
    )

    # ── Demand Forecast / Restock Alerts ──────────────────────────────────
    def _forecast_alerts():
        from engine.forecasting import forecast_demand, detect_demand_spikes
        if sales.empty:
            return "No sales data loaded."
        try:
            top_cat = sales["category"].mode().iloc[0] if "category" in sales.columns else "FMCG"
            fc      = forecast_demand(sales, top_cat, 30)
            return detect_demand_spikes({top_cat: fc}, inventory)
        except Exception as exc:
            return f"Forecast not available: {exc}"

    tools["get_restock_alerts"] = Tool(
        name="get_restock_alerts",
        description=(
            "Runs Prophet demand forecast and returns items where stock will run out soon. "
            "Shows days_coverage, predicted_demand, stock_gap. "
            "Use when asked about restock, what to order, stock running out, or upcoming demand."
        ),
        fn=_forecast_alerts,
        category="forecast",
    )

    # ── CEO Morning Briefing ───────────────────────────────────────────────
    def _briefing():
        from engine.analytics import detect_dead_stock, get_outstanding_payments
        from engine.recommender import generate_recommendations, ceo_morning_briefing
        try:
            ds_df   = detect_dead_stock(inventory) if not inventory.empty else None
            out_df  = get_outstanding_payments(sales, customers) if not sales.empty else None
            recs    = generate_recommendations(dead_stock_df=ds_df, outstanding_df=out_df)
            return ceo_morning_briefing(recs)
        except Exception as exc:
            return f"Could not generate briefing: {exc}"

    tools["get_morning_briefing"] = Tool(
        name="get_morning_briefing",
        description=(
            "Generates a CEO Morning Briefing — a prioritised summary of the top actions "
            "for today covering payments, inventory, and customer alerts. "
            "Use when asked 'what should I do today', 'morning briefing', or 'top priorities'."
        ),
        fn=_briefing,
        category="summary",
    )

    # ── Area / Town Performance ────────────────────────────────────────────
    def _area_rank():
        from engine.analytics import area_sales_ranking
        if sales.empty:
            return "No sales data loaded."
        return area_sales_ranking(sales)

    tools["get_area_performance"] = Tool(
        name="get_area_performance",
        description=(
            "Ranks towns/areas by revenue, growth, and number of customers. "
            "Use when asked about which area/town is performing best or worst, "
            "geographic performance, or regional insights."
        ),
        fn=_area_rank,
        category="analytics",
    )

    # ── Revenue Recovery Tools ─────────────────────────────────────────────
    # These tools wrap the recovery_engine module for AI-driven revenue
    # recovery campaigns.  The LLM may ORCHESTRATE these tools, but the
    # deterministic Recovery Policy Engine enforces all state transitions,
    # stopping rules, and intervention limits.

    def _recovery_batch():
        from engine.recovery_engine import build_recovery_batch
        if sales.empty:
            return "No sales data loaded."
        campaign, records = build_recovery_batch(sales, customers)
        if not records:
            return "No customers eligible for recovery (all are LOW RISK or no outstanding amounts)."
        lines = [f"Recovery Batch — Campaign {campaign.campaign_id} — {len(records)} customers prioritized by expected recovery value:\n"]
        for i, r in enumerate(records, 1):
            lines.append(
                f"{i}. {r.customer_name}: Rs.{r.outstanding_amount:,.0f} outstanding, "
                f"{r.collection_probability:.0f}% collection probability, "
                f"{int(r.days_overdue)} days overdue, "
                f"Priority Score: {r.priority_score:,.0f}, "
                f"Expected Recovery: Rs.{r.expected_recovery:,.0f}, "
                f"Risk: {r.risk_tier}"
            )
        total = sum(r.outstanding_amount for r in records)
        expected = sum(r.expected_recovery for r in records)
        lines.append(f"\nTotal targeted: Rs.{total:,.0f}")
        lines.append(f"Total expected recovery: Rs.{expected:,.0f}")
        return "\n".join(lines)

    tools["get_recovery_batch"] = Tool(
        name="get_recovery_batch",
        description=(
            "Identifies and prioritizes customers for revenue recovery today. "
            "Returns a batch sorted by expected recoverable value (outstanding x probability x urgency). "
            "Excludes LOW RISK customers by default. "
            "Use when asked: who should we contact today, which customers to recover from, "
            "maximize recovery, build recovery batch, revenue at risk."
        ),
        fn=_recovery_batch,
        category="recovery",
    )

    def _execute_campaign():
        from engine.recovery_engine import run_recovery_campaign
        if sales.empty:
            return "No sales data loaded."
        
        # Don't run again if already run
        if "campaign" in context.recovery_state and context.recovery_state["campaign"].status == "COMPLETED":
            campaign = context.recovery_state["campaign"]
            records = context.recovery_state["records"]
            metrics = context.recovery_state["metrics"]
            prefix = f"Recovery Campaign {campaign.campaign_id} was already run today. Showing results:\n\n"
        else:
            campaign, records, metrics = run_recovery_campaign(sales, customers)
            context.recovery_state["campaign"] = campaign
            context.recovery_state["records"] = records
            context.recovery_state["metrics"] = metrics
            prefix = f"Recovery Campaign {campaign.campaign_id} COMPLETED\n\n"

        if not records:
            return "No customers eligible for recovery campaign."

        lines = [prefix]
        lines.append("=== CAMPAIGN METRICS ===")
        lines.append(f"Amount at Risk:         Rs.{metrics['amount_at_risk']:,.0f}")
        lines.append(f"Amount Targeted:        Rs.{metrics['amount_targeted']:,.0f}")
        lines.append(f"Expected Recovery:      Rs.{metrics['expected_recovery']:,.0f}")
        lines.append(f"Actual Recovery:        Rs.{metrics['actual_recovery']:,.0f}")
        lines.append(f"Remaining Outstanding:  Rs.{metrics['remaining_outstanding']:,.0f}")
        lines.append(f"Recovery Rate:          {metrics['recovery_rate_pct']:.1f}%")
        lines.append(f"Recovery Performance:   {metrics['recovery_performance_pct']:.1f}% (actual vs expected)")
        lines.append(f"Customers Targeted:     {metrics['customers_targeted']}")
        lines.append(f"Customers Contacted:    {metrics['customers_contacted']}")
        lines.append(f"Customers Recovered:    {metrics['customers_recovered']}")
        lines.append(f"Customers Escalated:    {metrics['customers_escalated']}")
        lines.append(f"Customers Excluded:     {metrics.get('customers_excluded', 0)} (low risk)")
        lines.append(f"Avg Attempts to Recover: {metrics.get('average_attempts_to_recovery', 0):.1f}")
        lines.append(f"\n=== CUSTOMER RESULTS ===")
        for r in records:
            status_icon = "RECOVERED" if r.simulation_result == "PAID" else ("ESCALATED" if r.simulation_result == "ESCALATED" else "WAITING")
            lines.append(
                f"  {r.customer_name}: {status_icon} — "
                f"Rs.{r.outstanding_amount:,.0f} outstanding, "
                f"intervention={r.intervention}, "
                f"recovered=Rs.{r.amount_recovered:,.0f}"
            )
        lines.append(f"\nAll actions logged to canonical audit trail.")
        return "\n".join(lines)

    tools["execute_recovery_campaign"] = Tool(
        name="execute_recovery_campaign",
        description=(
            "Runs a complete revenue recovery campaign (or returns results if already run today): "
            "identifies at-risk customers, scores risks, prioritizes by expected recovery value, "
            "chooses bounded interventions, simulates payment outcomes, updates recovery states, "
            "and logs audit trail. Returns campaign metrics."
            "Use when asked to: run recovery campaign, recover outstanding, collect payments, "
            "execute collection today, maximize revenue recovery."
        ),
        fn=_execute_campaign,
        category="recovery",
    )

    def _recovery_metrics():
        if "metrics" in context.recovery_state:
            return context.recovery_state["metrics"]
        return "No campaign has been run yet. Please run execute_recovery_campaign first."

    tools["get_recovery_metrics"] = Tool(
        name="get_recovery_metrics",
        description=(
            "Returns detailed campaign performance metrics: amount recovered, recovery rate, "
            "recovery performance (actual vs expected), customers recovered/escalated/excluded. "
            "Use when asked: how much recovered, what was the recovery rate, campaign results, "
            "what happened in recovery."
        ),
        fn=_recovery_metrics,
        category="recovery",
    )

    def _recovery_audit():
        from engine.audit_logger import get_audit_log
        audit_df = get_audit_log()
        if audit_df.empty:
            return "No audit records found. Run a recovery campaign first."
        return audit_df

    tools["get_recovery_audit_log"] = Tool(
        name="get_recovery_audit_log",
        description=(
            "Returns the full audit trail of all recovery actions, state transitions, "
            "and payment outcomes. Shows timestamp, customer, action, state changes, "
            "and simulation results. "
            "Use when asked about: audit trail, audit log, what decisions were made, "
            "show recovery history, compliance, what happened."
        ),
        fn=_recovery_audit,
        category="recovery",
    )

    def _customer_recovery_status():
        from engine.recovery_engine import build_recovery_batch
        if sales.empty:
            return "No sales data loaded."
        _, records = build_recovery_batch(sales, customers, exclude_low_risk=False)
        if not records:
            return "No customers with outstanding amounts."
        lines = ["Customer Recovery Status:\n"]
        for r in records:
            lines.append(
                f"  {r.customer_name}: State={r.state.value}, "
                f"Rs.{r.outstanding_amount:,.0f} outstanding, "
                f"Risk={r.risk_tier}, Probability={r.collection_probability:.0f}%"
            )
        return "\n".join(lines)

    tools["get_customer_recovery_status"] = Tool(
        name="get_customer_recovery_status",
        description=(
            "Shows the current recovery state for all customers with outstanding balances, "
            "including LOW RISK customers. Shows state, amount, risk tier, probability. "
            "Use when asked: customer status, recovery status, which customers not to contact, "
            "who is low risk, show all customers."
        ),
        fn=_customer_recovery_status,
        category="recovery",
    )

    def _choose_action():
        from engine.recovery_engine import build_recovery_batch, choose_intervention
        if sales.empty:
            return "No sales data loaded."
        _, records = build_recovery_batch(sales, customers, exclude_low_risk=False)
        if not records:
            return "No customers with outstanding amounts."
        lines = ["Recommended Recovery Actions:\n"]
        for r in records:
            action = choose_intervention(r)
            reason = f"Risk: {r.risk_tier}, {int(r.days_overdue)} days overdue, {r.collection_probability:.0f}% probability"
            if action == "WAIT":
                reason += " — no contact needed"
            lines.append(f"  {r.customer_name}: ACTION={action} ({reason})")
        return "\n".join(lines)

    tools["choose_recovery_action"] = Tool(
        name="choose_recovery_action",
        description=(
            "Shows the deterministic intervention recommendation for each customer "
            "based on risk tier, attempts, and policy rules. "
            "Use when asked: what action to take, what should we do about a customer, "
            "why was this action chosen, intervention recommendation."
        ),
        fn=_choose_action,
        category="recovery",
    )

    def _check_payment():
        from engine.audit_logger import get_audit_log
        audit_df = get_audit_log()
        if audit_df.empty:
            return "No recovery campaigns have been run yet. Run a campaign first to check payment status."
        outcomes = audit_df[audit_df["event_type"] == "PAYMENT_OUTCOME"]
        if outcomes.empty:
            return "No payment outcomes recorded yet."
        lines = ["Payment Status (Simulated):\n"]
        for _, row in outcomes.iterrows():
            lines.append(
                f"  {row.get('customer_name', 'Unknown')}: {row.get('simulation_result', 'Unknown')} — "
                f"Rs.{float(row.get('amount_recovered', 0)):,.0f} recovered"
            )
        return "\n".join(lines)

    tools["check_payment_status"] = Tool(
        name="check_payment_status",
        description=(
            "Checks simulated payment outcomes from the audit trail. "
            "Shows which customers paid (RECOVERED) and which did not. "
            "Use when asked: did they pay, payment status, who paid, check payments."
        ),
        fn=_check_payment,
        category="recovery",
    )

    def _recovery_priority():
        from engine.recovery_engine import build_recovery_batch
        if sales.empty:
            return "No sales data loaded."
        _, records = build_recovery_batch(sales, customers, exclude_low_risk=False)
        if not records:
            return "No customers with outstanding amounts."
        lines = ["Recovery Priority Ranking (ALL customers, including excluded):\n"]
        lines.append(f"{'#':<3} {'Customer':<25} {'Outstanding':>12} {'Prob':>6} {'Days':>5} {'Priority':>10} {'Expected':>12} {'Risk Tier':<15}")
        lines.append("-" * 95)
        for i, r in enumerate(records, 1):
            lines.append(
                f"{i:<3} {r.customer_name:<25} Rs.{r.outstanding_amount:>10,.0f} {r.collection_probability:>5.0f}% {int(r.days_overdue):>4}d "
                f"{r.priority_score:>10,.0f} Rs.{r.expected_recovery:>10,.0f} {r.risk_tier:<15}"
            )
        targeted = [r for r in records if r.risk_tier != "LOW RISK"]
        excluded = [r for r in records if r.risk_tier == "LOW RISK"]
        lines.append(f"\nTargeted: {len(targeted)} customers | Excluded (Low Risk): {len(excluded)} customers")
        return "\n".join(lines)

    tools["get_recovery_priority"] = Tool(
        name="get_recovery_priority",
        description=(
            "Shows the full priority ranking of ALL customers by expected recoverable value, "
            "including LOW RISK customers that would be excluded from a campaign. "
            "Explains the priority score formula: outstanding x probability x urgency multiplier. "
            "Use when asked: why is this customer prioritized, priority ranking, "
            "expected recovery value, which customers have highest expected value."
        ),
        fn=_recovery_priority,
        category="recovery",
    )

    return tools



# ═════════════════════════════════════════════════════════════════════════════
# 4. LLM Client — Gemini → Groq → Rule-based fallback
# ═════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """
    Tries LLM providers in priority order dynamically:
      1. Google Gemini (discovers models)
      2. Groq Llama 3
      3. Rule-based fallback
    """

    def __init__(self, gemini_key: Optional[str] = None, groq_key: Optional[str] = None):
        self.gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
        self.groq_key   = groq_key   or os.getenv("GROQ_API_KEY",   "")
        self.backend_used = FALLBACK_MODEL
        self._gemini_model_cache = []

    @property
    def name(self) -> str:
        return self.backend_used

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate a completion. Returns plain text."""
        if self.gemini_key:
            res = self._try_gemini(prompt, system)
            if not res.startswith("AGENT_ERROR:"):
                return res
            logger.warning("Gemini failed (%s), falling back to Groq/RuleBased", res)

        if self.groq_key:
            res = self._try_groq(prompt, system)
            if not res.startswith("AGENT_ERROR:"):
                return res
            logger.warning("Groq failed (%s), falling back to RuleBased", res)

        self.backend_used = FALLBACK_MODEL
        return self._fallback(prompt)

    def _get_gemini_models(self, client) -> list[str]:
        if self._gemini_model_cache:
            return self._gemini_model_cache

        try:
            models = client.models.list()
            valid_models = []
            for m in models:
                name = m.name.lower()
                # Filter out embeddings, vision, audio, aqa
                if "gemini" not in name:
                    continue
                if any(x in name for x in ["vision", "embedding", "audio", "aqa", "learnmath"]):
                    continue
                # Check method if available
                if hasattr(m, 'supported_generation_methods'):
                    if 'generateContent' not in m.supported_generation_methods:
                        continue
                valid_models.append(m.name)
            
            def rank_score(model_name: str) -> int:
                score = 0
                n = model_name.lower()
                if "exp" in n or "preview" in n:
                    score -= 50
                if "flash" in n:
                    score += 20
                if "pro" in n:
                    score += 10
                if "2.5" in n:
                    score += 30
                elif "2.0" in n:
                    score += 20
                elif "1.5" in n:
                    score += 10
                return score
            
            valid_models.sort(key=rank_score, reverse=True)
            self._gemini_model_cache = valid_models
            return valid_models
        except Exception as e:
            logger.error("Model discovery failed: %s", str(e))
            return []

    def _try_gemini(self, prompt: str, system: str) -> str:
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_key)
            models_to_try = self._get_gemini_models(client)
            if not models_to_try:
                return "AGENT_ERROR: No compatible Gemini models discovered."
            
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            last_err = None

            for model_name in models_to_try:
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                    )
                    raw = resp.text.strip()
                    logger.debug("Gemini [%s] responded OK", model_name)
                    
                    # Clean up model name for UI presentation
                    ui_name = model_name.replace("models/", "")
                    self.backend_used = f"Gemini — {ui_name}"
                    return raw
                except Exception as model_exc:
                    err_str = str(model_exc)
                    if any(k in err_str.lower() for k in ["404", "not_found", "decommissioned", "no longer available", "503", "overloaded", "quota"]):
                        logger.warning("Gemini model %s unavailable, trying next.", model_name)
                        last_err = model_exc
                        continue
                    # Other exceptions (like bad auth) surface immediately to trigger fallback
                    return f"AGENT_ERROR: {str(model_exc)}"

            return f"AGENT_ERROR: All discovered Gemini models failed. Last error: {last_err}"
        except Exception as exc:
            return f"AGENT_ERROR: Gemini API error — {str(exc)}"

    def _try_groq(self, prompt: str, system: str) -> str:
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system or _SYSTEM_PROMPT})
            msgs.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=msgs,
                max_tokens=1024,
                temperature=0.3,
            )
            raw = resp.choices[0].message.content.strip()
            self.backend_used = f"Groq — {GROQ_MODEL}"
            return raw
        except Exception as exc:
            return f"AGENT_ERROR: Groq API error — {str(exc)}"

    def _fallback(self, prompt: str) -> str:
        """
        Rule-based fallback: parses the prompt to determine which tool
        the agent should call next, without an LLM.
        """
        p_full = prompt.lower()

        # If this is a "final answer" request (observation already in prompt)
        if "observation:" in p_full and "based on" in p_full:
            return "Final Answer: Based on the data retrieved, I have analyzed your business situation. Please review the detailed observations above for specific numbers and recommendations."

        # Extract only the original user question to prevent routing on stale observation keywords
        import re
        q_match = re.search(r"question:\s*(.+?)(?=\n|$)", prompt, re.IGNORECASE)
        p = q_match.group(1).lower() if q_match else p_full

        # Tool selection heuristics
        if any(w in p for w in ["recover", "campaign", "run recovery", "run today", "execute recovery", "maximize recovery"]):
            return 'Thought: The user wants to run a revenue recovery campaign.\nAction: execute_recovery_campaign\nAction Input: {}'

        if any(w in p for w in ["recovery batch", "who should we contact", "contact today", "revenue at risk"]):
            return 'Thought: I need to identify the recovery batch and prioritize customers.\nAction: get_recovery_batch\nAction Input: {}'

        if any(w in p for w in ["recovery metric", "how much recovered", "recovery rate", "what happened in", "campaign result"]):
            return 'Thought: I need to check the recovery campaign metrics.\nAction: get_recovery_metrics\nAction Input: {}'

        if any(w in p for w in ["audit trail", "audit log", "show audit", "recovery history", "decisions made"]):
            return 'Thought: I need to show the recovery audit trail.\nAction: get_recovery_audit_log\nAction Input: {}'

        if any(w in p for w in ["recovery status", "not contact", "low risk", "exclude", "should not contact"]):
            return 'Thought: I need to check recovery status for all customers.\nAction: get_customer_recovery_status\nAction Input: {}'

        if any(w in p for w in ["priority rank", "expected recovery value", "why priorit"]):
            return 'Thought: I need to show the full recovery priority ranking.\nAction: get_recovery_priority\nAction Input: {}'

        if any(w in p for w in ["dead stock", "slow moving", "not sold", "capital blocked", "inventory"]):

            return 'Thought: I need to check inventory data for dead or slow-moving stock.\nAction: get_dead_stock\nAction Input: {}'

        if any(w in p for w in ["pay", "overdue", "outstanding", "collection", "owes", "dues", "receivable", "payment"]):
            if any(w in p for w in ["risk", "default", "won't pay", "predict", "probability", "likely to not pay", "most likely"]):
                return 'Thought: I need to score payment default risk for customers.\nAction: get_payment_risk_scores\nAction Input: {}'
            return 'Thought: I need to check outstanding payments and overdue invoices.\nAction: get_outstanding_payments\nAction Input: {}'

        if any(w in p for w in ["churn", "segment", "loyal", "at risk", "lost customer", "retain"]):
            return 'Thought: I need customer segmentation data to identify at-risk customers.\nAction: get_customer_segments\nAction Input: {}'

        if any(w in p for w in ["fraud", "anomal", "suspicious", "unusual", "discount abuse"]):
            return 'Thought: I need to check for anomalous or suspicious transactions.\nAction: get_anomalies\nAction Input: {}'

        if any(w in p for w in ["restock", "order", "stock out", "running out", "demand", "forecast"]):
            return 'Thought: I need demand forecasts and restock alerts.\nAction: get_restock_alerts\nAction Input: {}'

        if any(w in p for w in ["area", "town", "region", "geography", "uniara", "tonk"]):
            return 'Thought: I need area/town performance data.\nAction: get_area_performance\nAction Input: {}'

        if any(w in p for w in ["today", "morning", "briefing", "priority", "what should", "what to do"]):
            return 'Thought: The user wants an executive summary of today\'s priorities.\nAction: get_morning_briefing\nAction Input: {}'

        # Default
        return 'Thought: Let me get an overview of the business priorities.\nAction: get_morning_briefing\nAction Input: {}'


# ═════════════════════════════════════════════════════════════════════════════
# 5. System Prompt
# ═════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are the WHOLESALE AI BUSINESS ANALYST for a wholesale distribution business in India.
You operate across Revenue Recovery, Inventory, Customer Intelligence, Sales, Territory / Operations, and Business-wide risk.
You help the business owner make data-driven decisions by selecting appropriate deterministic tools.

You have access to these tools:
TOOL_DESCRIPTIONS_PLACEHOLDER

IMPORTANT — Your Role & Constraints:
- You must NEVER invent metrics, fabricate customer balances, fabricate inventory, fabricate forecasts, or fabricate recovery probabilities.
- You must NEVER claim an action happened when it did not.
- You must NEVER treat Figma/reference content as business data.
- When factual numeric information is needed, obtain it ONLY from the available tools.
- Responses should be concise, executive-friendly, evidence-based, action-oriented, and grounded in tool results.
- Where appropriate, structure your answer with: Key finding, Recommended action, Evidence. Do not force this if a simple answer is better.

Authority boundaries (Revenue Recovery):
- You may RECOMMEND actions and ORCHESTRATE tool calls for recovery campaigns.
- The deterministic Recovery Policy Engine ENFORCES all state transitions, stopping rules, and intervention limits.
- You must NEVER claim to directly move money, change payment states, or bypass policy rules.
- All financial recovery results are SIMULATED for demonstration.
"""



# ═════════════════════════════════════════════════════════════════════════════
# 6. ReAct Agent — the main loop
# ═════════════════════════════════════════════════════════════════════════════

class WholesaleAgent:
    """
    ReAct-style agent for wholesale business intelligence.

    Usage::

        from engine.ai_agent import WholesaleAgent, AgentContext

        ctx   = AgentContext(sales_df=sales, inventory_df=inv, customer_df=cust)
        agent = WholesaleAgent(context=ctx, gemini_key="YOUR_KEY")
        result = agent.run("Which customers are at risk of churning?")

        print(result.answer)
        for step in result.steps:
            print(step.to_display())
    """

    def __init__(
        self,
        context:    AgentContext,
        gemini_key: Optional[str] = None,
        groq_key:   Optional[str] = None,
    ):
        self.context  = context
        self.llm      = LLMClient(gemini_key=gemini_key, groq_key=groq_key)
        self.tools    = build_tool_registry(context)

    @property
    def llm_name(self) -> str:
        return self.llm.name

    def _tool_descriptions(self) -> str:
        return "\n".join(
            f"- {name}: {tool.description}"
            for name, tool in self.tools.items()
        )

    def _build_react_prompt(
        self,
        question: str,
        history:  list[AgentStep],
        context_summary: str,
    ) -> str:
        """Build the full prompt for the next ReAct step."""
        tool_desc = self._tool_descriptions()

        lines = [
            f"Business Context: {context_summary}",
            "",
            f"Available Tools:\n{tool_desc}",
            "",
            f"Question: {question}",
            "",
        ]

        for step in history:
            lines += [
                f"Thought: {step.thought}",
                f"Action: {step.action}",
                f"Action Input: {json.dumps(step.action_args)}",
                f"Observation: {step.observation}",
                "",
            ]

        lines.append("What is your next Thought? (or write 'Final Answer: ...' if ready)")
        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> tuple[str, str, dict, bool]:
        """
        Parse LLM response into (thought, action, action_args, is_final).
        Handles plain text AND bold markdown (**Thought:**, **Action:**) from Gemini.
        Returns is_final=True when the LLM writes 'Final Answer: ...'.
        """
        # Strip markdown bold formatting that Gemini sometimes outputs
        cleaned = re.sub(r"\*\*(\w[^*]*)\*\*:", r"\1:", response)
        cleaned = re.sub(r"\*(\w[^*]*)\*:",   r"\1:", cleaned)

        # Check for API errors surfaced by _gemini / _groq
        if cleaned.startswith("AGENT_ERROR:"):
            return cleaned, "_error_", {}, True

        # Check for final answer
        final_match = re.search(r"Final Answer:\s*(.+)", cleaned, re.DOTALL | re.IGNORECASE)
        if final_match:
            return "", "", {}, True

        # Extract Thought
        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", cleaned, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else cleaned.strip()[:200]

        # Extract Action — allow word chars, underscores, hyphens, and optional parens
        action_match = re.search(r"Action:\s*([\w_-]+)", cleaned, re.IGNORECASE)
        action = action_match.group(1).strip() if action_match else "get_morning_briefing"

        # Extract Action Input
        args_match = re.search(r"Action Input:\s*(\{.*?\})", cleaned, re.DOTALL | re.IGNORECASE)
        args = {}
        if args_match:
            try:
                args = json.loads(args_match.group(1))
            except json.JSONDecodeError:
                args = {}

        # Validate action name
        if action not in self.tools:
            for tool_name in self.tools:
                if tool_name.lower() in action.lower() or action.lower() in tool_name.lower():
                    action = tool_name
                    break
            else:
                action = "get_morning_briefing"

        return thought, action, args, False

    def _extract_final_answer(self, response: str) -> str:
        # Strip markdown bold
        cleaned = re.sub(r"\*\*(\w[^*]*)\*\*:", r"\1:", response)
        cleaned = re.sub(r"\*(\w[^*]*)\*:",   r"\1:", cleaned)

        # Return the API error message directly if present
        if cleaned.startswith("AGENT_ERROR:"):
            return cleaned  # will be shown as an error in the UI

        match = re.search(r"Final Answer:\s*(.+)", cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # If no Final Answer tag but also no Action/Thought, treat the whole response as the answer
        if "Action:" not in cleaned and "Thought:" not in cleaned:
            return cleaned.strip()
        return ""

    def run(self, question: str, cancel_check: Optional[Callable[[], bool]] = None) -> AgentResult:
        """
        Run the full ReAct loop for the given question.

        Returns an AgentResult with the answer, all reasoning steps,
        and metadata about which LLM was used.
        """
        from engine.audit_logger import log_event

        t_start     = time.time()
        history: list[AgentStep] = []
        tool_calls: list[str]    = []
        context_summary          = self.context.business_summary()
        final_answer             = ""
        confidence               = "HIGH"

        logger.info("Agent starting. LLM: %s. Question: %s", self.llm.name, question[:80])
        log_event(event_type="AGENT_QUERY", reason=question)

        for step_num in range(1, MAX_REACT_STEPS + 1):
            if cancel_check and cancel_check():
                final_answer = "AGENT_ERROR: Generation stopped by user."
                break

            t_step = time.time()

            # Build system prompt with tool descriptions injected (avoid .format() issues with curly braces in tool output)
            system_prompt = _SYSTEM_PROMPT.replace("TOOL_DESCRIPTIONS_PLACEHOLDER", self._tool_descriptions())
            react_prompt  = self._build_react_prompt(question, history, context_summary)

            # Ask LLM what to do next
            llm_response = self.llm.generate(react_prompt, system=system_prompt)
            thought, action, action_args, is_final = self._parse_llm_response(llm_response)

            if is_final:
                final_answer = self._extract_final_answer(llm_response)
                break

            if cancel_check and cancel_check():
                final_answer = "AGENT_ERROR: Generation stopped by user."
                break

            # Call the tool
            tool = self.tools.get(action)
            if tool is None:
                observation = f"Tool '{action}' not found. Available: {list(self.tools.keys())}"
                confidence  = "LOW"
            else:
                if len(history) > 0 and history[-1].action == action and history[-1].action_args == action_args:
                    observation = "I already called this tool and got the same result. I should stop and provide a Final Answer."
                else:
                    observation = tool.call(**action_args)
                    log_event(event_type="TOOL_CALL", action=action, reason=json.dumps(action_args))
                tool_calls.append(action)

            elapsed_ms = int((time.time() - t_step) * 1000)

            step = AgentStep(
                step_num    = step_num,
                thought     = thought,
                action      = action,
                action_args = action_args,
                observation = observation,
                elapsed_ms  = elapsed_ms,
            )
            history.append(step)
            logger.debug("Step %d: action=%s elapsed=%dms", step_num, action, elapsed_ms)

            # Forcefully break out if we are in a loop
            if len(history) > 1 and history[-1].action == history[-2].action and history[-1].action_args == history[-2].action_args:
                logger.warning("Agent is looping on %s. Breaking.", action)
                break

            # After last allowed step, force final answer
            if step_num == MAX_REACT_STEPS:
                final_prompt = (
                    react_prompt
                    + f"\nThought: {thought}\nAction: {action}\nObservation: {observation}\n"
                    + "Based on all the above data, write your Final Answer:"
                )
                final_response = self.llm.generate(final_prompt, system=system_prompt)
                final_answer   = self._extract_final_answer(final_response)
                if not final_answer:
                    final_answer = self._synthesize_from_history(question, history)
                    confidence   = "MEDIUM"

        if not final_answer:
            final_answer = self._synthesize_from_history(question, history)
            confidence   = "MEDIUM"

        if final_answer.startswith("AGENT_ERROR:") or len(tool_calls) == 0:
            confidence = "LOW"

        total_ms = int((time.time() - t_start) * 1000)
        logger.info(
            "Agent done. Steps: %d, Tools: %s, LLM: %s, Time: %dms",
            len(history), tool_calls, self.llm.name, total_ms,
        )

        return AgentResult(
            question   = question,
            answer     = final_answer,
            steps      = history,
            llm_used   = self.llm.name,
            total_ms   = total_ms,
            tool_calls = tool_calls,
            confidence = confidence,
        )

    def _synthesize_from_history(self, question: str, history: list[AgentStep]) -> str:
        """
        Fallback synthesis when LLM doesn't produce a Final Answer.
        Extracts key info from observations and builds a structured answer.
        """
        if not history:
            return (
                "I don't have enough data to answer that question. "
                "Please make sure your sales, inventory, and customer data are loaded."
            )

        parts = [f"Here's what I found about '{question}':\n"]
        for step in history:
            # Don't show duplicate identical steps in the fallback synthesis
            if step.step_num > 1 and history[step.step_num - 2].action == step.action:
                continue
            tool_display = step.action.replace("_", " ").title()
            obs_short    = step.observation[:300]
            parts.append(f"**{tool_display}:** {obs_short}")

        parts.append(
            "\nReview the detailed observations above for specific numbers. "
            "For a more precise answer, set a GEMINI_API_KEY in your environment."
        )
        return "\n\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Convenience Function — quick single-call interface
# ═════════════════════════════════════════════════════════════════════════════

def ask(
    question:     str,
    sales_df:     Optional[pd.DataFrame] = None,
    inventory_df: Optional[pd.DataFrame] = None,
    customer_df:  Optional[pd.DataFrame] = None,
    gemini_key:   Optional[str] = None,
    groq_key:     Optional[str] = None,
) -> AgentResult:
    """
    One-line interface to the WholesaleAgent.

    Example::

        result = ask(
            "Which customers are at risk of churning?",
            sales_df=sales, inventory_df=inv, customer_df=cust,
        )
        print(result.answer)
    """
    ctx   = AgentContext(sales_df=sales_df, inventory_df=inventory_df, customer_df=customer_df)
    agent = WholesaleAgent(context=ctx, gemini_key=gemini_key, groq_key=groq_key)
    return agent.run(question)


# ─── Suggested questions for the UI ──────────────────────────────────────────
SUGGESTED_QUESTIONS = [
    "Who should we contact today to maximize expected revenue recovery?",
    "Run today's recovery campaign.",
    "What happened in today's recovery campaign?",
    "Why was Patel Stores selected?",
    "Why was this customer not selected?",
    "Did Patel Stores pay?",
    "Show today's recovery audit trail.",
    "What is the expected recoverable value?"
]

