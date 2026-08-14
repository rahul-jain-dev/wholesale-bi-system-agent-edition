"""
engine/recommender.py
=====================
Recommendation engine orchestrator for the Wholesale BI System.

Aggregates signals from all analytical engines (dead stock, outstanding
payments, demand forecasts, customer segmentation, anomaly detection) into
a unified list of prioritised, actionable ``Recommendation`` objects.

Key features:
- Dataclass-based ``Recommendation`` type (fully typed, JSON-serialisable).
- Rule-based generation covering 5 categories: Inventory, Payment, Customer,
  Sales (restock), and Anomaly.
- Urgency score–driven sorting (descending).
- CEO Morning Briefing: one-paragraph executive summary with top-5 actions.
- ``filter_by_category`` helper for Streamlit and FastAPI layer.

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

VALID_PRIORITIES: set[str] = {"HIGH", "MEDIUM", "LOW"}
VALID_CATEGORIES: set[str] = {"Inventory", "Payment", "Customer", "Sales", "Anomaly"}


@dataclass
class Recommendation:
    """
    A single actionable business recommendation.

    Attributes:
        id:             Unique identifier (UUID4 string).
        category:       One of 'Inventory', 'Payment', 'Customer', 'Sales',
                        'Anomaly'.
        priority:       One of 'HIGH', 'MEDIUM', 'LOW'.
        title:          Short title (< 80 characters).
        message:        Plain-English detailed recommendation.
        impact_rupees:  Estimated financial impact in INR (0 if unknown).
        urgency_score:  Float in [0, 1]; higher = more urgent.
        created_at:     ISO timestamp when recommendation was created.
        metadata:       Optional extra context dict (product name, customer, etc.)
    """

    id: str
    category: str
    priority: str
    title: str
    message: str
    impact_rupees: float
    urgency_score: float
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary representation."""
        return asdict(self)

    def __post_init__(self) -> None:
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Recommendation.category must be one of {VALID_CATEGORIES!r}, "
                f"got {self.category!r}."
            )
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(
                f"Recommendation.priority must be one of {VALID_PRIORITIES!r}, "
                f"got {self.priority!r}."
            )
        self.urgency_score = round(float(self.urgency_score), 4)
        self.impact_rupees = round(float(self.impact_rupees), 2)


# ---------------------------------------------------------------------------
# Rule constants
# ---------------------------------------------------------------------------

# Dead stock rules
DS_HIGH_DAYS = 90
DS_HIGH_CAPITAL = 5_000.0
DS_MEDIUM_DAYS_LOW = 60
DS_MEDIUM_DAYS_HIGH = 90
DS_MEDIUM_CAPITAL_LOW = 2_000.0
DS_MEDIUM_CAPITAL_HIGH = 5_000.0

# Payment rules
PAY_HIGH_DAYS = 90
PAY_MEDIUM_DAYS = 45

# Restock rules (< 7 days coverage = HIGH)
RESTOCK_CRITICAL_DAYS = 7
RESTOCK_MEDIUM_DAYS = 14

# Anomaly rules
ANOMALY_HIGH_DISCOUNT = 25.0


# ---------------------------------------------------------------------------
# 1. Main Orchestrator
# ---------------------------------------------------------------------------

def generate_recommendations(
    dead_stock_df: Optional[pd.DataFrame] = None,
    outstanding_df: Optional[pd.DataFrame] = None,
    forecast_alerts: Optional[pd.DataFrame] = None,
    segment_df: Optional[pd.DataFrame] = None,
    anomaly_df: Optional[pd.DataFrame] = None,
) -> list[Recommendation]:
    """
    Generate a unified, prioritised list of recommendations from all engines.

    Each input is optional — pass ``None`` to skip that engine's analysis.
    The output list is sorted by ``urgency_score`` descending (most urgent first).

    Rules applied:

    **Inventory (Dead Stock):**
    - HIGH   : days_unsold > 90 AND capital_blocked > ₹5,000
    - MEDIUM : days_unsold 60–90 OR capital_blocked ₹2,000–₹5,000

    **Payment (Outstanding):**
    - HIGH   : outstanding_amount > 0 AND days_overdue > 90
    - MEDIUM : days_overdue 45–90

    **Sales (Restock / Forecast Alert):**
    - HIGH   : predicted_demand > current_stock × 1.5 AND days_coverage < 7
    - MEDIUM : days_coverage 7–14

    **Customer (Segmentation):**
    - MEDIUM : customer segment == 'At Risk'
    - LOW    : customer segment == 'Lost'

    **Anomaly:**
    - HIGH   : is_anomaly == True AND discount_pct > 25%
    - MEDIUM : is_anomaly == True AND discount_pct <= 25%

    Args:
        dead_stock_df:   Output of ``analytics.detect_dead_stock`` with
                         ``days_unsold``, ``capital_blocked``, ``stock_status``,
                         ``product_name``.
        outstanding_df:  Output of ``analytics.get_outstanding_payments`` with
                         ``customer_name``, ``invoice_no``, ``days_overdue``,
                         ``invoice_amount``, ``risk_level``.
        forecast_alerts: Output of ``forecasting.detect_demand_spikes`` with
                         ``category``, ``total_predicted_demand``,
                         ``current_stock``, ``stock_gap``.
        segment_df:      Output of ``segmentation.segment_customers`` with
                         ``customer_name``, ``segment``, ``recency_days``,
                         ``monetary``.
        anomaly_df:      Output of ``anomaly_detector.detect_anomalies`` with
                         ``is_anomaly``, ``discount_pct``, ``anomaly_score``,
                         ``invoice_no``, ``customer_name``, ``sale_price``,
                         ``quantity``.

    Returns:
        List of ``Recommendation`` objects sorted by ``urgency_score``
        descending. Empty list if all inputs are None or empty.
    """
    recommendations: list[Recommendation] = []

    # ------------------------------------------------------------------ #
    # A. Dead Stock Recommendations
    # ------------------------------------------------------------------ #
    if dead_stock_df is not None and not dead_stock_df.empty:
        recommendations.extend(
            _build_dead_stock_recommendations(dead_stock_df)
        )

    # ------------------------------------------------------------------ #
    # B. Payment Recommendations
    # ------------------------------------------------------------------ #
    if outstanding_df is not None and not outstanding_df.empty:
        recommendations.extend(
            _build_payment_recommendations(outstanding_df)
        )

    # ------------------------------------------------------------------ #
    # C. Restock / Forecast Recommendations
    # ------------------------------------------------------------------ #
    if forecast_alerts is not None and not forecast_alerts.empty:
        recommendations.extend(
            _build_restock_recommendations(forecast_alerts)
        )

    # ------------------------------------------------------------------ #
    # D. Customer Segment Recommendations
    # ------------------------------------------------------------------ #
    if segment_df is not None and not segment_df.empty:
        recommendations.extend(
            _build_customer_recommendations(segment_df)
        )

    # ------------------------------------------------------------------ #
    # E. Anomaly Recommendations
    # ------------------------------------------------------------------ #
    if anomaly_df is not None and not anomaly_df.empty:
        recommendations.extend(
            _build_anomaly_recommendations(anomaly_df)
        )

    # Sort by urgency score descending
    recommendations.sort(key=lambda r: r.urgency_score, reverse=True)

    logger.info(
        "generate_recommendations: %d total recommendations generated. "
        "HIGH=%d, MEDIUM=%d, LOW=%d",
        len(recommendations),
        sum(1 for r in recommendations if r.priority == "HIGH"),
        sum(1 for r in recommendations if r.priority == "MEDIUM"),
        sum(1 for r in recommendations if r.priority == "LOW"),
    )
    return recommendations


# ---------------------------------------------------------------------------
# 2. CEO Morning Briefing
# ---------------------------------------------------------------------------

def ceo_morning_briefing(recommendations: list[Recommendation]) -> str:
    """
    Generate a one-paragraph executive briefing from the top recommendations.

    Summarises:
    - Total number of open actions
    - Top 5 most urgent actions (with title and impact)
    - Total financial opportunity / risk identified
    - Count breakdown by category

    Args:
        recommendations: Output of ``generate_recommendations``, sorted by
                         urgency_score descending.

    Returns:
        Plain-English briefing string suitable for display on the dashboard
        header or sending as a WhatsApp/email summary.
    """
    if not recommendations:
        return (
            "Good morning! No critical actions required today. "
            "All systems are operating normally. Have a great day! 🌟"
        )

    today = datetime.now().strftime("%d %B %Y")
    total = len(recommendations)
    high_count = sum(1 for r in recommendations if r.priority == "HIGH")
    total_impact = sum(r.impact_rupees for r in recommendations)

    # Category breakdown
    cat_counts: dict[str, int] = {}
    for r in recommendations:
        cat_counts[r.category] = cat_counts.get(r.category, 0) + 1

    cat_summary = ", ".join(
        f"{count} {cat}" for cat, count in sorted(cat_counts.items())
    )

    # Top 5
    top5 = recommendations[:5]
    top5_lines = []
    for i, rec in enumerate(top5, 1):
        impact_str = f" (₹{rec.impact_rupees:,.0f} at stake)" if rec.impact_rupees > 0 else ""
        top5_lines.append(
            f"  {i}. [{rec.priority}] {rec.title}{impact_str}"
        )
    top5_text = "\n".join(top5_lines)

    briefing = (
        f"📊 CEO MORNING BRIEFING — {today}\n"
        f"{'─' * 55}\n\n"
        f"Good morning! Today you have {total} open action items "
        f"({high_count} HIGH priority). "
        f"Total financial exposure identified: ₹{total_impact:,.0f}.\n\n"
        f"Breakdown: {cat_summary}.\n\n"
        f"🔥 TOP 5 ACTIONS:\n{top5_text}\n\n"
        f"Review the full recommendation list in the BI dashboard "
        f"for detailed action plans and WhatsApp message templates."
    )
    return briefing


# ---------------------------------------------------------------------------
# 3. Filter by Category
# ---------------------------------------------------------------------------

def filter_by_category(
    recommendations: list[Recommendation],
    category: str,
) -> list[Recommendation]:
    """
    Filter recommendations by category.

    This function is exported and called directly by the Streamlit app.

    Args:
        recommendations: Full list of ``Recommendation`` objects.
        category:        One of ``'Inventory'``, ``'Payment'``,
                         ``'Customer'``, ``'Sales'``, ``'Anomaly'``.

    Returns:
        Filtered list of recommendations matching the given category,
        preserving the original sort order.

    Raises:
        ValueError: If ``category`` is not one of the valid values.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"filter_by_category: category must be one of {VALID_CATEGORIES!r}, "
            f"got {category!r}."
        )
    return [r for r in recommendations if r.category == category]


# ---------------------------------------------------------------------------
# 4. Utility: Recommendations to DataFrame
# ---------------------------------------------------------------------------

def recommendations_to_dataframe(
    recommendations: list[Recommendation],
) -> pd.DataFrame:
    """
    Convert a list of Recommendation objects to a pandas DataFrame.

    Useful for display in Streamlit tables or export to CSV.

    Args:
        recommendations: List of ``Recommendation`` objects.

    Returns:
        DataFrame with one row per recommendation and columns matching
        all ``Recommendation`` dataclass fields (except ``metadata``).
    """
    if not recommendations:
        return pd.DataFrame()

    records = [
        {
            "id": r.id,
            "category": r.category,
            "priority": r.priority,
            "title": r.title,
            "message": r.message,
            "impact_rupees": r.impact_rupees,
            "urgency_score": r.urgency_score,
            "created_at": r.created_at,
        }
        for r in recommendations
    ]
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Internal rule builders
# ---------------------------------------------------------------------------

def _build_dead_stock_recommendations(
    dead_stock_df: pd.DataFrame,
) -> list[Recommendation]:
    """Build Inventory category recommendations from dead stock data."""
    recs: list[Recommendation] = []

    required = {"days_unsold", "capital_blocked"}
    if not required.issubset(dead_stock_df.columns):
        logger.warning(
            "_build_dead_stock_recommendations: missing columns %s. Skipping.",
            required - set(dead_stock_df.columns),
        )
        return recs

    for _, row in dead_stock_df.iterrows():
        days = int(row.get("days_unsold", 0))
        capital = float(row.get("capital_blocked", 0))
        product = str(row.get("product_name", "Unknown Product"))
        category_name = str(row.get("category", ""))
        company = str(row.get("company", ""))
        discount_suggested = int(row.get("suggested_discount_pct", 0))
        action = str(row.get("recommended_action", ""))

        if days > DS_HIGH_DAYS and capital > DS_HIGH_CAPITAL:
            priority = "HIGH"
            urgency = round(
                min(days / 180, 1.0) * 0.4
                + min(capital / 50_000, 1.0) * 0.4
                + 1.0 * 0.2,
                4,
            )
            title = f"DEAD STOCK: {product} — ₹{capital:,.0f} blocked for {days} days"
            message = (
                f"🚨 {product} ({company}) has not sold in {days} days with "
                f"₹{capital:,.0f} of capital blocked. "
                f"Recommended action: {action} "
                f"Suggested discount: {discount_suggested}%. "
                f"Category: {category_name}."
            )
        elif (days > DS_HIGH_DAYS) or (DS_MEDIUM_DAYS_LOW <= days <= DS_MEDIUM_DAYS_HIGH) or (
            DS_MEDIUM_CAPITAL_LOW <= capital <= DS_MEDIUM_CAPITAL_HIGH
        ):
            priority = "MEDIUM"
            urgency = round(
                min(days / 180, 1.0) * 0.4
                + min(capital / 50_000, 1.0) * 0.4
                + 0.5 * 0.2,
                4,
            )
            title = f"SLOW STOCK: {product} — {days} days unsold"
            message = (
                f"⚠️ {product} ({company}) is moving slowly — {days} days since "
                f"last sale, ₹{capital:,.0f} tied up. "
                f"{action} Consider a {discount_suggested}% discount offer."
            )
        else:
            continue  # ACTIVE stock — no recommendation needed

        recs.append(
            Recommendation(
                id=str(uuid.uuid4()),
                category="Inventory",
                priority=priority,
                title=title,
                message=message,
                impact_rupees=capital,
                urgency_score=urgency,
                metadata={
                    "product_name": product,
                    "company": company,
                    "category": category_name,
                    "days_unsold": days,
                    "capital_blocked": capital,
                    "suggested_discount_pct": discount_suggested,
                },
            )
        )

    return recs


def _build_payment_recommendations(
    outstanding_df: pd.DataFrame,
) -> list[Recommendation]:
    """Build Payment category recommendations from outstanding payments data."""
    recs: list[Recommendation] = []

    required = {"days_overdue", "invoice_amount"}
    if not required.issubset(outstanding_df.columns):
        # Try alternative column name
        if "outstanding_amount" in outstanding_df.columns:
            outstanding_df = outstanding_df.copy()
            outstanding_df["invoice_amount"] = outstanding_df["outstanding_amount"]
        else:
            logger.warning(
                "_build_payment_recommendations: missing columns. Skipping."
            )
            return recs

    for _, row in outstanding_df.iterrows():
        days = int(row.get("days_overdue", 0))
        amount = float(row.get("invoice_amount", row.get("outstanding_amount", 0)))
        customer = str(row.get("customer_name", "Unknown Customer"))
        invoice = str(row.get("invoice_no", "N/A"))
        area = str(row.get("area", row.get("customer_area", "")))
        whatsapp = str(row.get("whatsapp_message", ""))
        risk = str(row.get("risk_level", "LOW"))

        if amount <= 0:
            continue

        if days > PAY_HIGH_DAYS:
            priority = "HIGH"
            urgency = round(
                min(days / 90, 1.0) * 0.4
                + min(amount / 50_000, 1.0) * 0.4
                + 1.0 * 0.2,
                4,
            )
            title = f"OVERDUE: {customer} — ₹{amount:,.0f} ({days} days)"
            message = (
                f"🚨 Payment from {customer} ({area}) is {days} days overdue. "
                f"Invoice #{invoice}, Amount: ₹{amount:,.0f}. "
                f"Risk level: {risk}. Immediate follow-up required. "
                f"WhatsApp template ready."
            )
        elif days >= PAY_MEDIUM_DAYS:
            priority = "MEDIUM"
            urgency = round(
                min(days / 90, 1.0) * 0.4
                + min(amount / 50_000, 1.0) * 0.4
                + 0.5 * 0.2,
                4,
            )
            title = f"PAYMENT DUE: {customer} — ₹{amount:,.0f} ({days} days)"
            message = (
                f"⚠️ {customer} ({area}) has a payment of ₹{amount:,.0f} "
                f"overdue by {days} days (Invoice #{invoice}). "
                f"Send WhatsApp reminder and follow up this week."
            )
        else:
            continue

        recs.append(
            Recommendation(
                id=str(uuid.uuid4()),
                category="Payment",
                priority=priority,
                title=title,
                message=message,
                impact_rupees=amount,
                urgency_score=urgency,
                metadata={
                    "customer_name": customer,
                    "invoice_no": invoice,
                    "area": area,
                    "days_overdue": days,
                    "risk_level": risk,
                    "whatsapp_message": whatsapp,
                },
            )
        )

    return recs


def _build_restock_recommendations(
    forecast_alerts: pd.DataFrame,
) -> list[Recommendation]:
    """Build Sales category recommendations from demand spike / forecast alerts."""
    recs: list[Recommendation] = []

    required = {"category", "stock_gap"}
    if not required.issubset(forecast_alerts.columns):
        logger.warning(
            "_build_restock_recommendations: missing columns. Skipping."
        )
        return recs

    for _, row in forecast_alerts.iterrows():
        cat = str(row.get("category", "Unknown"))
        product_filter = str(row.get("product_filter", "all"))
        gap = float(row.get("stock_gap", 0))
        current_stock = float(row.get("current_stock", 0))
        predicted = float(row.get("total_predicted_demand", 0))
        severity = str(row.get("spike_severity", "MEDIUM"))

        # Estimate financial impact: assume avg purchase price ₹50/unit (conservative)
        impact = gap * 50.0

        # days_coverage from forecast_alerts if available
        days_cov = float(row.get("days_coverage", 0))

        if severity == "CRITICAL" or days_cov < RESTOCK_CRITICAL_DAYS:
            priority = "HIGH"
            urgency = round(
                1.0 * 0.4
                + min(gap / 1000, 1.0) * 0.4
                + 1.0 * 0.2,
                4,
            )
            title = f"RESTOCK URGENT: {cat} — demand exceeds stock by {gap:.0f} units"
            message = (
                f"🚨 CRITICAL STOCK ALERT for category '{cat}' "
                f"(Product: {product_filter}). "
                f"Forecasted demand: {predicted:.0f} units, "
                f"current stock: {current_stock:.0f} units. "
                f"Shortfall: {gap:.0f} units. "
                f"Place purchase order IMMEDIATELY to avoid stockout."
            )
        elif days_cov < RESTOCK_MEDIUM_DAYS or severity == "HIGH":
            priority = "MEDIUM"
            urgency = round(
                0.6 * 0.4
                + min(gap / 1000, 1.0) * 0.4
                + 0.5 * 0.2,
                4,
            )
            title = f"RESTOCK NEEDED: {cat} — {gap:.0f} unit shortfall forecast"
            message = (
                f"⚠️ Stock for '{cat}' (Product: {product_filter}) is running low. "
                f"Forecast predicts {predicted:.0f} units needed; "
                f"only {current_stock:.0f} available. "
                f"Gap: {gap:.0f} units. Plan reorder within 7 days."
            )
        else:
            continue

        recs.append(
            Recommendation(
                id=str(uuid.uuid4()),
                category="Sales",
                priority=priority,
                title=title,
                message=message,
                impact_rupees=impact,
                urgency_score=urgency,
                metadata={
                    "category": cat,
                    "product_filter": product_filter,
                    "predicted_demand": predicted,
                    "current_stock": current_stock,
                    "stock_gap": gap,
                    "spike_severity": severity,
                },
            )
        )

    return recs


def _build_customer_recommendations(
    segment_df: pd.DataFrame,
) -> list[Recommendation]:
    """Build Customer category recommendations from segmentation data."""
    recs: list[Recommendation] = []

    if "segment" not in segment_df.columns:
        logger.warning(
            "_build_customer_recommendations: 'segment' column missing. Skipping."
        )
        return recs

    for _, row in segment_df.iterrows():
        segment = str(row.get("segment", ""))
        customer = str(row.get("customer_name", "Unknown"))
        recency = int(row.get("recency_days", 0))
        monetary = float(row.get("monetary", 0))
        recommendation_text = str(row.get("recommendation", ""))

        if segment == "At Risk":
            priority = "MEDIUM"
            urgency = round(
                min(recency / 90, 1.0) * 0.4
                + min(monetary / 100_000, 1.0) * 0.4
                + 0.5 * 0.2,
                4,
            )
            monthly_spend = round(monetary / max(recency / 30, 1), 0)
            title = f"RETENTION ALERT: {customer} — {recency} days inactive"
            message = (
                f"⚠️ {customer} is AT RISK — no order in {recency} days. "
                f"Historical monthly spend: ≈ ₹{monthly_spend:,.0f}. "
                f"Lifetime value: ₹{monetary:,.0f}. "
                f"Action: {recommendation_text}"
            )
            impact = monetary * 0.3  # Estimate 30% of LTV at risk

        elif segment == "Lost":
            priority = "LOW"
            urgency = round(
                min(recency / 180, 1.0) * 0.4
                + min(monetary / 100_000, 1.0) * 0.4
                + 0.2 * 0.2,
                4,
            )
            title = f"RECOVERY: {customer} — {recency} days since last order"
            message = (
                f"🔴 {customer} appears LOST — last order {recency} days ago. "
                f"Total business: ₹{monetary:,.0f}. "
                f"Action: {recommendation_text}"
            )
            impact = monetary * 0.1  # Lower recovery probability

        else:
            continue  # Champions and Loyal don't generate alerts

        recs.append(
            Recommendation(
                id=str(uuid.uuid4()),
                category="Customer",
                priority=priority,
                title=title,
                message=message,
                impact_rupees=impact,
                urgency_score=urgency,
                metadata={
                    "customer_name": customer,
                    "segment": segment,
                    "recency_days": recency,
                    "monetary": monetary,
                },
            )
        )

    return recs


def _build_anomaly_recommendations(
    anomaly_df: pd.DataFrame,
) -> list[Recommendation]:
    """Build Anomaly category recommendations from anomaly detection data."""
    recs: list[Recommendation] = []

    if "is_anomaly" not in anomaly_df.columns:
        logger.warning(
            "_build_anomaly_recommendations: 'is_anomaly' column missing. Skipping."
        )
        return recs

    flagged = anomaly_df[anomaly_df["is_anomaly"] == True].copy()  # noqa: E712
    if flagged.empty:
        return recs

    flagged["discount_pct"] = pd.to_numeric(
        flagged.get("discount_pct", pd.Series(0, index=flagged.index)),
        errors="coerce",
    ).fillna(0)
    flagged["sale_price"] = pd.to_numeric(
        flagged.get("sale_price", pd.Series(0, index=flagged.index)),
        errors="coerce",
    ).fillna(0)
    flagged["quantity"] = pd.to_numeric(
        flagged.get("quantity", pd.Series(1, index=flagged.index)),
        errors="coerce",
    ).fillna(1).clip(lower=1)
    flagged["transaction_value"] = flagged["sale_price"] * flagged["quantity"]

    for _, row in flagged.iterrows():
        discount = float(row.get("discount_pct", 0))
        value = float(row.get("transaction_value", 0))
        invoice = str(row.get("invoice_no", "N/A"))
        customer = str(row.get("customer_name", "Unknown"))
        product = str(row.get("product_name", "Unknown"))
        salesperson = str(row.get("salesperson", "Unknown"))
        anomaly_score = float(row.get("anomaly_score", 0))
        date_val = row.get("date", "")

        if discount > ANOMALY_HIGH_DISCOUNT:
            priority = "HIGH"
            urgency = round(
                min(discount / 50, 1.0) * 0.4
                + min(value / 50_000, 1.0) * 0.4
                + min(abs(anomaly_score) / 0.5, 1.0) * 0.2,
                4,
            )
            title = (
                f"ANOMALY HIGH DISCOUNT: {discount:.0f}% on Invoice #{invoice}"
            )
            message = (
                f"🚨 Suspicious transaction detected! Invoice #{invoice} "
                f"({date_val}) — {product} sold to {customer} "
                f"with {discount:.0f}% discount by {salesperson}. "
                f"Transaction value: ₹{value:,.0f}. "
                f"Anomaly score: {anomaly_score:.4f}. "
                f"Investigate immediately — possible policy violation."
            )
        else:
            priority = "MEDIUM"
            urgency = round(
                min(discount / 50, 1.0) * 0.4
                + min(value / 50_000, 1.0) * 0.4
                + min(abs(anomaly_score) / 0.5, 1.0) * 0.2 * 0.5,
                4,
            )
            title = f"ANOMALY: Unusual transaction on Invoice #{invoice}"
            message = (
                f"⚠️ Unusual transaction pattern detected on Invoice #{invoice} "
                f"({date_val}). Product: {product}, Customer: {customer}, "
                f"Salesperson: {salesperson}, Discount: {discount:.0f}%, "
                f"Value: ₹{value:,.0f}. "
                f"Review for data entry error or policy exception."
            )

        recs.append(
            Recommendation(
                id=str(uuid.uuid4()),
                category="Anomaly",
                priority=priority,
                title=title,
                message=message,
                impact_rupees=value,
                urgency_score=urgency,
                metadata={
                    "invoice_no": invoice,
                    "customer_name": customer,
                    "product_name": product,
                    "salesperson": salesperson,
                    "discount_pct": discount,
                    "transaction_value": value,
                    "anomaly_score": anomaly_score,
                },
            )
        )

    logger.info(
        "_build_anomaly_recommendations: %d anomaly recommendations built.", len(recs)
    )
    return recs
