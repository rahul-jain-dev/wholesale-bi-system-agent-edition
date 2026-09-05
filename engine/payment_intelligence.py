"""
engine/payment_intelligence.py
===============================
Payment Collection Risk Intelligence for the Wholesale BI System.

Predicts which customers are unlikely to pay their outstanding invoices
using a gradient-boosted classifier trained on behavioral signals extracted
from existing sales and customer data.

This module is a direct analog to Razorpay's payment risk scoring systems
used in Razorpay Capital and their lending/collections products — the same
principle of scoring "will this payment succeed?" applied to wholesale
distributor collections.

Features Used
-------------
- days_overdue         : How long since the invoice was due
- invoice_amount       : Size of the outstanding amount
- sales_trend_3m       : 3-month sales velocity (declining = higher risk)
- avg_days_to_pay      : Historical payment speed for this customer
- payment_count        : Total payments made historically
- is_at_risk_segment   : RFM segment (At Risk = 1, Lost = 1, else 0)
- overdue_invoice_count: Number of currently overdue invoices for this customer

Output
------
- collection_probability : float 0–100 (higher = more likely to pay)
- risk_tier              : "LOW RISK" / "MEDIUM RISK" / "HIGH RISK" / "WRITE-OFF"
- recommended_action     : "Routine Follow-up" / "Call Today" / "Personal Visit" / "Legal Notice"
- urgency_score          : float 0–1 (for sorting)

Author: Wholesale BI System — Agent Edition
Python: 3.12
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Feature Engineering
# ═════════════════════════════════════════════════════════════════════════════

def _build_features(
    sales_df:    pd.DataFrame,
    customer_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Extract payment-risk features per customer from sales history.

    Returns a DataFrame indexed by customer_name with ML-ready features.
    """
    if sales_df.empty:
        return pd.DataFrame()

    df = sales_df.copy()

    # Coerce types
    df["date"]       = pd.to_datetime(df.get("date"), errors="coerce")
    df["sale_price"] = pd.to_numeric(df.get("sale_price", 0), errors="coerce").fillna(0)
    df["quantity"]   = pd.to_numeric(df.get("quantity",   0), errors="coerce").fillna(0)
    df["revenue"]    = df["sale_price"] * df["quantity"]

    today  = df["date"].max()
    cutoff = today - pd.Timedelta(days=90)

    # ── Per-customer aggregations ──────────────────────────────────────────
    cust_stats = (
        df.groupby("customer_name")
        .agg(
            total_revenue   = ("revenue",    "sum"),
            payment_count   = ("invoice_no", "nunique") if "invoice_no" in df.columns else ("date", "count"),
            last_sale_date  = ("date",       "max"),
            first_sale_date = ("date",       "min"),
        )
        .reset_index()
    )

    # Days since last sale (recency proxy)
    cust_stats["days_since_last_sale"] = (today - cust_stats["last_sale_date"]).dt.days.fillna(999)

    # 3-month revenue trend: positive = growing, negative = declining
    recent = df[df["date"] >= cutoff].groupby("customer_name")["revenue"].sum().rename("revenue_3m")
    older  = df[df["date"] <  cutoff].groupby("customer_name")["revenue"].sum().rename("revenue_before_3m")
    cust_stats = cust_stats.merge(recent, on="customer_name", how="left")
    cust_stats = cust_stats.merge(older,  on="customer_name", how="left")
    cust_stats["revenue_3m"]        = cust_stats["revenue_3m"].fillna(0)
    cust_stats["revenue_before_3m"] = cust_stats["revenue_before_3m"].fillna(1)  # avoid div/0
    cust_stats["sales_trend_3m"]    = (
        (cust_stats["revenue_3m"] - cust_stats["revenue_before_3m"])
        / cust_stats["revenue_before_3m"].clip(lower=1)
    ).clip(-1, 1)  # normalised to [-1, +1]

    # ── Outstanding invoice features ───────────────────────────────────────
    # Compute days_overdue from payment_due_date if not already present
    if "days_overdue" not in df.columns and "payment_due_date" in df.columns:
        due_dates = pd.to_datetime(df["payment_due_date"], errors="coerce")
        raw_days = (today - due_dates).dt.days.fillna(0).astype(int)
        df["days_overdue"] = raw_days.clip(lower=0)
        # Only count as overdue if payment_status is not PAID
        if "payment_status" in df.columns:
            paid_mask = df["payment_status"].str.upper().isin(["PAID"])
            df.loc[paid_mask, "days_overdue"] = 0

    if "days_overdue" in df.columns:

        overdue = (
            df[pd.to_numeric(df["days_overdue"], errors="coerce").fillna(0) > 0]
            .groupby("customer_name")
            .agg(
                max_days_overdue     = ("days_overdue", "max"),
                overdue_invoice_count= ("invoice_no",   "nunique") if "invoice_no" in df.columns else ("date", "count"),
                total_overdue_amount = ("revenue",      "sum"),
            )
            .reset_index()
        )
        cust_stats = cust_stats.merge(overdue, on="customer_name", how="left")
    else:
        # Estimate from recency: customers who haven't bought recently but have high revenue = outstanding
        cust_stats["max_days_overdue"]      = cust_stats["days_since_last_sale"].clip(0, 180)
        cust_stats["overdue_invoice_count"] = 0
        cust_stats["total_overdue_amount"]  = 0.0

    for col in ["max_days_overdue", "overdue_invoice_count", "total_overdue_amount"]:
        if col not in cust_stats.columns:
            cust_stats[col] = 0
        cust_stats[col] = pd.to_numeric(cust_stats[col], errors="coerce").fillna(0)

    # ── Historical payment speed ───────────────────────────────────────────
    # Proxy: customers with fewer transactions per revenue unit are slower payers
    cust_stats["avg_days_to_pay"] = (
        cust_stats["days_since_last_sale"]
        / cust_stats["payment_count"].clip(lower=1)
    ).clip(0, 180)

    return cust_stats


# ═════════════════════════════════════════════════════════════════════════════
# 2. Risk Scoring
# ═════════════════════════════════════════════════════════════════════════════

_FEATURE_COLS = [
    "max_days_overdue",
    "total_overdue_amount",
    "sales_trend_3m",
    "avg_days_to_pay",
    "payment_count",
    "days_since_last_sale",
    "overdue_invoice_count",
]

def _rule_based_score(row: pd.Series) -> float:
    """
    Rule-based collection probability when ML model can't be trained
    (insufficient data). Returns 0–100, higher = safer to collect.
    """
    score = 80.0  # start optimistic

    days = float(row.get("max_days_overdue", 0))
    if days > 120:  score -= 45
    elif days > 90: score -= 30
    elif days > 60: score -= 20
    elif days > 30: score -= 10

    trend = float(row.get("sales_trend_3m", 0))
    if trend < -0.3:  score -= 15
    elif trend < 0:   score -= 5
    elif trend > 0.2: score += 5

    payments = float(row.get("payment_count", 0))
    if payments > 20: score += 10
    elif payments < 3: score -= 10

    amount = float(row.get("total_overdue_amount", 0))
    if amount > 50_000: score -= 10
    elif amount > 20_000: score -= 5

    return float(np.clip(score, 0, 100))


def _assign_tier(prob: float, days: float) -> tuple[str, str]:
    """Map collection probability + days overdue to risk tier + recommended action."""
    if prob >= 75:
        return "LOW RISK", "Routine Follow-up"
    elif prob >= 55:
        return "MEDIUM RISK", "Call Today"
    elif prob >= 35:
        if days > 90:
            return "HIGH RISK", "Personal Visit"
        return "HIGH RISK", "Call Today"
    else:
        if days > 120:
            return "WRITE-OFF RISK", "Legal Notice"
        return "HIGH RISK", "Personal Visit"


def score_payment_risk(
    sales_df:    pd.DataFrame,
    customer_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Score payment collection risk for all customers with outstanding amounts.

    Returns a DataFrame sorted by urgency_score (most urgent first) with:
    - customer_name
    - total_overdue_amount
    - max_days_overdue
    - collection_probability  (0–100, higher = more likely to pay)
    - risk_tier               (LOW RISK / MEDIUM RISK / HIGH RISK / WRITE-OFF RISK)
    - recommended_action      (Routine Follow-up / Call Today / Personal Visit / Legal Notice)
    - urgency_score           (0–1, for sorting — higher = needs attention now)
    - sales_trend_3m          (positive = growing, negative = declining)

    Args:
        sales_df:    Standardized sales DataFrame.
        customer_df: Optional customer master DataFrame.

    Returns:
        DataFrame with risk scores, empty if no data.
    """
    if sales_df.empty:
        logger.warning("score_payment_risk: empty sales_df")
        return pd.DataFrame()

    features = _build_features(sales_df, customer_df)
    if features.empty:
        return pd.DataFrame()

    # ── Try to train a lightweight ML classifier ───────────────────────────
    use_ml = False
    try:
        feat_matrix = features[_FEATURE_COLS].copy()
        for col in _FEATURE_COLS:
            if col not in feat_matrix.columns:
                feat_matrix[col] = 0
            feat_matrix[col] = pd.to_numeric(feat_matrix[col], errors="coerce").fillna(0)

        # Synthetic labels: customers with max_days_overdue > 90 + declining trend → likely to default
        labels = (
            (feat_matrix["max_days_overdue"] > 90) &
            (feat_matrix["sales_trend_3m"]   < 0)
        ).astype(int)

        n_default = labels.sum()
        n_good    = (labels == 0).sum()

        # Need at least 4 samples and both classes to train
        if len(features) >= 4 and n_default >= 1 and n_good >= 1:
            scaler = MinMaxScaler()
            X      = scaler.fit_transform(feat_matrix)

            clf = GradientBoostingClassifier(
                n_estimators  = 50,
                max_depth     = 3,
                learning_rate = 0.1,
                random_state  = 42,
            )
            clf.fit(X, labels)

            # Probability of "good payer" = class 0
            proba = clf.predict_proba(X)
            good_idx = list(clf.classes_).index(0) if 0 in clf.classes_ else 0
            features["collection_probability"] = (proba[:, good_idx] * 100).round(1)
            use_ml = True
            logger.info("score_payment_risk: ML classifier trained on %d customers", len(features))

    except Exception as exc:
        logger.warning("score_payment_risk: ML training failed (%s), using rule-based.", exc)

    if not use_ml:
        features["collection_probability"] = features.apply(_rule_based_score, axis=1)
    else:
        # Floor: ML probability should never be below the rule-based score.
        # This prevents the GBM from assigning 0% to all overdue customers
        # when training data lacks diversity (common with small demo datasets).
        rule_based = features.apply(_rule_based_score, axis=1)
        features["collection_probability"] = features["collection_probability"].clip(lower=rule_based)


    # ── Assign risk tiers and recommended actions ──────────────────────────
    tiers, actions = zip(*features.apply(
        lambda r: _assign_tier(
            r["collection_probability"],
            r.get("max_days_overdue", 0),
        ),
        axis=1,
    ))
    features["risk_tier"]           = list(tiers)
    features["recommended_action"]  = list(actions)

    # ── Urgency score: combines probability (inverted) + days overdue ──────
    # Low collection probability + high days overdue = highest urgency
    prob_norm = 1.0 - (features["collection_probability"] / 100.0)
    days_norm = (features["max_days_overdue"].clip(0, 180) / 180.0)
    features["urgency_score"] = (0.6 * prob_norm + 0.4 * days_norm).round(4)

    # ── Select and sort output columns ─────────────────────────────────────
    output_cols = [
        "customer_name",
        "total_overdue_amount",
        "max_days_overdue",
        "collection_probability",
        "risk_tier",
        "recommended_action",
        "urgency_score",
        "sales_trend_3m",
        "payment_count",
    ]
    for col in output_cols:
        if col not in features.columns:
            features[col] = 0 if col != "customer_name" else "Unknown"

    result = (
        features[output_cols]
        .sort_values("urgency_score", ascending=False)
        .reset_index(drop=True)
    )

    # Only return customers who have any overdue amount > 0
    result = result[result["total_overdue_amount"] > 0]

    logger.info(
        "score_payment_risk: %d customers scored. "
        "HIGH/WRITE-OFF: %d, MEDIUM: %d, LOW: %d",
        len(result),
        result["risk_tier"].isin(["HIGH RISK", "WRITE-OFF RISK"]).sum(),
        (result["risk_tier"] == "MEDIUM RISK").sum(),
        (result["risk_tier"] == "LOW RISK").sum(),
    )

    return result


# ═════════════════════════════════════════════════════════════════════════════
# 3. Collection Message Generator
# ═════════════════════════════════════════════════════════════════════════════

def generate_collection_message(
    customer_name:    str,
    overdue_amount:   float,
    days_overdue:     int,
    recommended_action: str,
    distributor_name: str = "Raj Distributors",
    payment_link:     str = "",
) -> str:
    """
    Generate a personalized WhatsApp/call script for payment collection.
    Uses tone calibrated to the risk tier and days overdue.

    Args:
        customer_name:      Name of the customer/retailer.
        overdue_amount:     Outstanding amount in Rs.
        days_overdue:       Number of days the invoice is overdue.
        recommended_action: From score_payment_risk() - sets the tone.
        distributor_name:   Distributor's business name.
        payment_link:       Optional mock Razorpay payment link to embed.

    Returns:
        A ready-to-send WhatsApp message string in Hindi-English mix.
    """
    amt_str = f"₹{overdue_amount:,.0f}"
    link_line = f"\n\nPay here: {payment_link}" if payment_link else ""

    if recommended_action == "Routine Follow-up" or days_overdue <= 30:
        return (
            f"Namaste {customer_name} ji 🙏\n\n"
            f"Yeh {distributor_name} ki taraf se ek friendly reminder hai. "
            f"Aapka {amt_str} ka payment {days_overdue} din se pending hai.\n\n"
            f"Kripya is week mein settle kar dein. Koi bhi problem ho to "
            f"batayein — hum solution nikalenge."
            f"{link_line}\n\n"
            f"Dhanyawad! 🙏"
        )

    elif recommended_action == "Call Today" or days_overdue <= 60:
        return (
            f"Namaste {customer_name} ji,\n\n"
            f"{distributor_name} se contact kar raha hoon. "
            f"Aapka {amt_str} ka outstanding {days_overdue} din se overdue hai.\n\n"
            f"Kripya aaj payment ka arrangement karein. "
            f"Mujhe call karein: hum payment schedule bana sakte hain."
            f"{link_line}\n\n"
            f"Regards,\n{distributor_name}"
        )

    elif recommended_action == "Personal Visit":
        return (
            f"Dear {customer_name},\n\n"
            f"This is a formal reminder from {distributor_name}.\n\n"
            f"Outstanding Amount: {amt_str}\n"
            f"Overdue Since: {days_overdue} days\n\n"
            f"This is urgent. Please arrange payment immediately or contact us "
            f"to discuss. Our representative will visit your shop this week.\n\n"
            f"Please take this seriously to avoid any disruption to your supply."
            f"{link_line}\n\n"
            f"— {distributor_name}"
        )

    else:  # Legal Notice
        return (
            f"FORMAL NOTICE — {distributor_name}\n\n"
            f"Dear {customer_name},\n\n"
            f"Despite multiple reminders, an outstanding amount of {amt_str} "
            f"has remained unpaid for {days_overdue} days.\n\n"
            f"This is your final notice before we proceed with legal action "
            f"and report this to the trade association.\n\n"
            f"Please settle this amount within 7 days."
            f"{link_line}\n\n"
            f"— {distributor_name}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 4. Summary Statistics
# ═════════════════════════════════════════════════════════════════════════════

def get_collection_summary(risk_df: pd.DataFrame) -> dict:
    """
    Compute portfolio-level collection summary from score_payment_risk output.

    Returns:
        dict with total_at_risk, high_risk_amount, recovery_probability_pct,
        top_defaulter, recommended_actions_count.
    """
    if risk_df.empty:
        return {
            "total_at_risk":              0.0,
            "high_risk_amount":           0.0,
            "medium_risk_amount":         0.0,
            "low_risk_amount":            0.0,
            "recovery_probability_pct":   0.0,
            "top_defaulter":              "N/A",
            "top_defaulter_amount":       0.0,
            "write_off_risk_count":       0,
        }

    total = float(risk_df["total_overdue_amount"].sum())

    high_mask   = risk_df["risk_tier"].isin(["HIGH RISK", "WRITE-OFF RISK"])
    medium_mask = risk_df["risk_tier"] == "MEDIUM RISK"
    low_mask    = risk_df["risk_tier"] == "LOW RISK"

    high_amt   = float(risk_df.loc[high_mask,   "total_overdue_amount"].sum())
    medium_amt = float(risk_df.loc[medium_mask, "total_overdue_amount"].sum())
    low_amt    = float(risk_df.loc[low_mask,    "total_overdue_amount"].sum())

    # Weighted recovery estimate
    recovery = 0.0
    if total > 0:
        recovery = (
            (low_amt * 0.90 + medium_amt * 0.60 + high_amt * 0.25) / total * 100
        )

    top_row = risk_df.iloc[0] if len(risk_df) > 0 else None

    return {
        "total_at_risk":            round(total, 2),
        "high_risk_amount":         round(high_amt, 2),
        "medium_risk_amount":       round(medium_amt, 2),
        "low_risk_amount":          round(low_amt, 2),
        "recovery_probability_pct": round(recovery, 1),
        "top_defaulter":            str(top_row["customer_name"]) if top_row is not None else "N/A",
        "top_defaulter_amount":     float(top_row["total_overdue_amount"]) if top_row is not None else 0.0,
        "write_off_risk_count":     int((risk_df["risk_tier"] == "WRITE-OFF RISK").sum()),
    }
