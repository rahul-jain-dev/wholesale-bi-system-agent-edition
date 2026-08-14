"""
engine/scoring.py
=================
Scoring and normalization formulas for the Wholesale BI System.

All scores are deterministic and stateless — pure functions with no side effects.
Used by analytics.py, recommender.py, and the dashboard layer.

Urgency Score Formula (system-wide):
    urgency_score = (days_factor × 0.4) + (amount_factor × 0.4) + (trend_factor × 0.2)

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

URGENCY_WEIGHTS: dict[str, float] = {
    "days_factor": 0.4,
    "amount_factor": 0.4,
    "trend_factor": 0.2,
}

# Sigmoid midpoint: 90 days overdue → factor ≈ 1.0
DAYS_SIGMOID_MIDPOINT: float = 90.0
DAYS_SIGMOID_STEEPNESS: float = 0.07

# Dead stock score weights
DEAD_STOCK_WEIGHTS: dict[str, float] = {
    "days_weight": 0.40,
    "capital_weight": 0.40,
    "margin_weight": 0.20,
}

# Payment risk thresholds
PAYMENT_RISK_HIGH_DAYS: int = 90
PAYMENT_RISK_HIGH_AMOUNT: float = 10_000.0
PAYMENT_RISK_MAX_SCORE: float = 100.0


# ---------------------------------------------------------------------------
# 1. Core Urgency Score
# ---------------------------------------------------------------------------

def urgency_score(
    days_factor: float,
    amount_factor: float,
    trend_factor: float,
) -> float:
    """
    Compute the system urgency score using weighted combination.

    Formula:
        urgency_score = (days_factor × 0.4) + (amount_factor × 0.4) + (trend_factor × 0.2)

    All input factors should be in the range [0, 1]. The result is clipped to [0, 1].

    Args:
        days_factor:   Normalized days component (0 = no urgency, 1 = maximum).
        amount_factor: Normalized financial exposure component (0–1).
        trend_factor:  Demand/risk trend component (0–1).

    Returns:
        Float urgency score in [0, 1], rounded to 4 decimal places.
    """
    score = (
        days_factor * URGENCY_WEIGHTS["days_factor"]
        + amount_factor * URGENCY_WEIGHTS["amount_factor"]
        + trend_factor * URGENCY_WEIGHTS["trend_factor"]
    )
    return round(float(np.clip(score, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# 2. Normalization
# ---------------------------------------------------------------------------

def normalize_factor(
    value: float,
    min_val: float,
    max_val: float,
) -> float:
    """
    Min-max normalize a value to the [0, 1] range.

    Args:
        value:   The raw value to normalize.
        min_val: The minimum of the expected range (maps to 0).
        max_val: The maximum of the expected range (maps to 1).

    Returns:
        Normalized float in [0, 1]. Returns 0.0 if ``max_val == min_val``
        to avoid division by zero.

    Raises:
        TypeError: If any argument is not numeric.
    """
    if not all(isinstance(v, (int, float)) for v in (value, min_val, max_val)):
        raise TypeError(
            "normalize_factor requires numeric arguments; "
            f"got value={type(value)}, min_val={type(min_val)}, max_val={type(max_val)}."
        )
    # Guard against NaN / inf propagation
    if any(math.isnan(v) or math.isinf(v) for v in (value, min_val, max_val)):
        logger.debug(
            "normalize_factor: NaN or inf detected (value=%s, min=%s, max=%s). Returning 0.0.",
            value, min_val, max_val,
        )
        return 0.0
    if max_val == min_val:
        logger.debug("normalize_factor: min_val == max_val (%s). Returning 0.0.", min_val)
        return 0.0
    normalized = (value - min_val) / (max_val - min_val)
    return float(np.clip(normalized, 0.0, 1.0))


# ---------------------------------------------------------------------------
# 3. Payment Risk Score
# ---------------------------------------------------------------------------

def risk_score_payment(
    outstanding_amount: float,
    days_overdue: int,
) -> float:
    """
    Compute a composite payment risk score on a 0–100 scale.

    The score combines two dimensions:
    - Days overdue: sigmoid-transformed, 90 days → ~0.9 risk
    - Outstanding amount: log-normalized against a reference maximum

    Formula:
        days_component   = sigmoid(days_overdue, midpoint=90, k=0.07) × 50
        amount_component = log_norm(amount, ref=₹10,000) × 50
        risk_score       = days_component + amount_component (clipped to 100)

    Args:
        outstanding_amount: Total unpaid amount in INR (≥ 0).
        days_overdue:       Days since payment due date (< 0 = not yet due).

    Returns:
        Risk score in [0, 100], rounded to 1 decimal place.
    """
    if days_overdue < 0:
        days_component = 0.0
    else:
        days_component = _sigmoid(float(days_overdue), DAYS_SIGMOID_MIDPOINT, DAYS_SIGMOID_STEEPNESS)

    amount_component = compute_amount_factor(
        max(outstanding_amount, 0.0), PAYMENT_RISK_HIGH_AMOUNT
    )

    raw = (days_component * 50.0) + (amount_component * 50.0)
    return round(float(np.clip(raw, 0.0, PAYMENT_RISK_MAX_SCORE)), 1)


# ---------------------------------------------------------------------------
# 4. Dead Stock Priority Score
# ---------------------------------------------------------------------------

def dead_stock_score(
    days_unsold: int,
    capital_blocked: float,
    margin_pct: float,
) -> float:
    """
    Compute a dead-stock urgency priority score on a 0–100 scale.

    Combines three dimensions:
    - Days unsold       : normalized against 180 days (6 months = max urgency)
    - Capital blocked   : log-normalized against ₹50,000 reference
    - Margin percentage : inverted (low margin = higher urgency)

    Formula:
        days_component   = min(days_unsold / 180, 1.0) × 40
        capital_component = log_norm(capital, ref=50000) × 40
        margin_component  = (1 - min(margin_pct/50, 1)) × 20
        score             = sum of components (clipped to 100)

    Args:
        days_unsold:     Days since last sale (0 = sold today).
        capital_blocked: Current stock × purchase price in INR.
        margin_pct:      Gross margin percentage (e.g. 15.0 for 15%).

    Returns:
        Priority score in [0, 100], rounded to 1 decimal place.
    """
    days_component = min(float(days_unsold) / 180.0, 1.0) * 40.0
    capital_component = compute_amount_factor(max(capital_blocked, 0.0), 50_000.0) * 40.0
    margin_inv = 1.0 - min(max(margin_pct, 0.0) / 50.0, 1.0)
    margin_component = margin_inv * 20.0

    raw = days_component + capital_component + margin_component
    return round(float(np.clip(raw, 0.0, 100.0)), 1)


# ---------------------------------------------------------------------------
# 5. Days Factor (Sigmoid)
# ---------------------------------------------------------------------------

def compute_days_factor(days: int) -> float:
    """
    Compute a sigmoid-normalized days factor for urgency scoring.

    The sigmoid is calibrated so that:
    - 0 days  → ≈ 0.0
    - 45 days → ≈ 0.3
    - 90 days → ≈ 0.88
    - 180 days → ≈ 1.0

    Args:
        days: Days overdue (negative values return 0.0).

    Returns:
        Float in [0, 1] representing urgency due to elapsed time.
    """
    if days <= 0:
        return 0.0
    result = _sigmoid(float(days), DAYS_SIGMOID_MIDPOINT, DAYS_SIGMOID_STEEPNESS)
    return round(float(np.clip(result, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# 6. Amount Factor (Log-Normalized)
# ---------------------------------------------------------------------------

def compute_amount_factor(amount: float, max_amount: float) -> float:
    """
    Compute a log-normalized amount factor for urgency scoring.

    Uses natural logarithm to compress large amounts, preventing a single
    very large invoice from dominating the score.

    Formula:
        factor = log(1 + amount) / log(1 + max_amount)

    Args:
        amount:     Raw INR amount (≥ 0).
        max_amount: Reference maximum amount for normalization (> 0).

    Returns:
        Float in [0, 1]. Returns 0.0 if ``max_amount`` ≤ 0.

    Raises:
        ValueError: If ``amount`` is negative.
    """
    if amount < 0:
        raise ValueError(
            f"compute_amount_factor: amount must be ≥ 0, got {amount}."
        )
    if max_amount <= 0:
        logger.warning("compute_amount_factor: max_amount=%s ≤ 0. Returning 0.0.", max_amount)
        return 0.0

    numerator = math.log1p(amount)
    denominator = math.log1p(max_amount)
    result = numerator / denominator if denominator > 0 else 0.0
    return round(float(np.clip(result, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# 7. Trend Factor (From Sales Data)
# ---------------------------------------------------------------------------

def compute_trend_factor(
    sales_df: pd.DataFrame,
    product_name: str,
    lookback_months: int = 3,
) -> float:
    """
    Compute a trend factor in [0, 1] based on 3-month sales slope.

    A positive slope (growing demand) → higher factor (closer to 1.0).
    A negative slope (declining demand) → lower factor (closer to 0.0).
    No data → 0.5 (neutral).

    Method:
    1. Filter sales to the given product over the past ``lookback_months`` months.
    2. Group by month and sum quantity.
    3. Compute linear regression slope.
    4. Normalize using tanh to map slope to [0, 1].

    Args:
        sales_df:        Standardized sales DataFrame with ``date``,
                         ``product_name``, and ``quantity`` columns.
        product_name:    Product to analyse.
        lookback_months: Number of trailing months to include (default 3).

    Returns:
        Float in [0, 1]. Returns 0.5 if insufficient data.
    """
    required = {"date", "product_name", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        logger.warning(
            "compute_trend_factor: missing columns %s. Returning 0.5.", missing
        )
        return 0.5

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    product_df = df[df["product_name"] == product_name].copy()

    if product_df.empty:
        logger.debug(
            "compute_trend_factor: no sales data for '%s'. Returning 0.5.",
            product_name,
        )
        return 0.5

    # Limit to lookback window
    cutoff = product_df["date"].max() - pd.DateOffset(months=lookback_months)
    product_df = product_df[product_df["date"] >= cutoff]

    if len(product_df) < 2:
        return 0.5

    # Monthly aggregation
    product_df["month_num"] = (
        product_df["date"].dt.year * 12 + product_df["date"].dt.month
    )
    monthly = product_df.groupby("month_num")["quantity"].sum().reset_index()

    if len(monthly) < 2:
        return 0.5

    # Linear regression slope via numpy polyfit
    x = monthly["month_num"].values.astype(float)
    y = monthly["quantity"].values.astype(float)
    x_norm = x - x.mean()  # centre for numerical stability

    try:
        slope, _ = np.polyfit(x_norm, y, 1)
    except (np.linalg.LinAlgError, ValueError) as exc:
        logger.warning("compute_trend_factor: polyfit failed (%s). Returning 0.5.", exc)
        return 0.5

    # Tanh normalization: slope of +10 units/month → ~0.76, -10 → ~0.24
    # Shift from [-1, 1] to [0, 1]
    factor = (math.tanh(slope / 10.0) + 1.0) / 2.0
    return round(float(np.clip(factor, 0.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float, midpoint: float, steepness: float) -> float:
    """
    Compute a sigmoid function value.

    Formula: 1 / (1 + exp(-steepness × (x - midpoint)))

    Args:
        x:          Input value.
        midpoint:   Value of x at which the sigmoid returns 0.5.
        steepness:  Controls how steeply the function rises.

    Returns:
        Float in (0, 1).
    """
    try:
        return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
    except OverflowError:
        return 0.0 if x < midpoint else 1.0


# ---------------------------------------------------------------------------
# Batch scoring utility
# ---------------------------------------------------------------------------

def score_payment_dataframe(
    outstanding_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply ``risk_score_payment`` and ``urgency_score`` to an entire DataFrame.

    Expects columns ``invoice_amount`` (or ``outstanding_amount``) and
    ``days_overdue``. Adds columns:
    - ``risk_score``    : 0–100 payment risk score
    - ``days_factor``   : sigmoid-normalized days component
    - ``amount_factor`` : log-normalized amount component
    - ``urgency_score`` : system urgency score [0–1]

    Args:
        outstanding_df: DataFrame of outstanding payments.

    Returns:
        Copy of the DataFrame with the four new columns added.
    """
    df = outstanding_df.copy()

    amount_col = "invoice_amount" if "invoice_amount" in df.columns else "outstanding_amount"
    if amount_col not in df.columns:
        df["risk_score"] = 0.0
        df["days_factor"] = 0.0
        df["amount_factor"] = 0.0
        df["urgency_score"] = 0.0
        return df

    amounts = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
    days = pd.to_numeric(df.get("days_overdue", pd.Series(0, index=df.index)), errors="coerce").fillna(0).astype(int)
    max_amount = float(amounts.max()) or 1.0

    df["risk_score"] = [
        risk_score_payment(a, d) for a, d in zip(amounts, days)
    ]
    df["days_factor"] = [compute_days_factor(int(d)) for d in days]
    df["amount_factor"] = [compute_amount_factor(float(a), max_amount) for a in amounts]
    df["urgency_score"] = [
        urgency_score(df_val, af, 0.5)
        for df_val, af in zip(df["days_factor"], df["amount_factor"])
    ]

    return df
