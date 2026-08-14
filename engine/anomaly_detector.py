"""
engine/anomaly_detector.py
==========================
Isolation Forest–based anomaly detection for the Wholesale BI System.

Detects suspicious sales transactions using unsupervised machine learning:
- Overall anomaly detection on multiple features (discount, quantity, margin).
- Discount anomaly flagging using statistical thresholding (mean + 2σ).
- Per-salesperson outlier detection for discount abuse and unusual patterns.
- Summary reporting of flagged anomalies.

MLflow experiment: 'wholesale_anomaly_detection'

Contamination rationale:
    A contamination=0.05 (5%) is set based on the expected anomaly rate in
    a small wholesale business — roughly 1 in 20 transactions may involve
    unusual discounting, data entry errors, or policy violations.

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
from typing import Optional

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MLFLOW_EXPERIMENT = "wholesale_anomaly_detection"

# Features used for Isolation Forest
ANOMALY_FEATURES: list[str] = [
    "discount_pct",
    "quantity",
    "sale_price",
    "purchase_price",
    "margin_ratio",  # Derived: (sale_price - purchase_price) / purchase_price
]


# ---------------------------------------------------------------------------
# 1. Overall Anomaly Detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    sales_df: pd.DataFrame,
    contamination: float = 0.05,
    n_estimators: int = 100,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Detect anomalous transactions using Isolation Forest.

    Features used:
    - ``discount_pct``  : percentage discount applied
    - ``quantity``      : units sold per transaction
    - ``sale_price``    : selling price per unit
    - ``purchase_price``: cost price per unit
    - ``margin_ratio``  : (sale_price - purchase_price) / purchase_price

    Contamination (0.05) is chosen based on the expected 5% anomaly rate
    in a small wholesale business.

    Added columns:
    - ``anomaly_score``  : Isolation Forest anomaly score (more negative = more anomalous)
    - ``is_anomaly``     : True if flagged as anomaly by the model

    Args:
        sales_df:      Standardized sales DataFrame.
        contamination: Fraction of expected anomalies (default 0.05).
        n_estimators:  Number of trees in the Isolation Forest (default 100).
        random_state:  Random seed for reproducibility.

    Returns:
        Copy of ``sales_df`` with ``anomaly_score`` and ``is_anomaly`` columns.

    Raises:
        ValueError: If required columns are missing or fewer than 10 rows.
    """
    required = {"discount_pct", "quantity", "sale_price", "purchase_price"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"detect_anomalies: missing columns {missing!r} in sales_df."
        )
    if len(sales_df) < 10:
        raise ValueError(
            f"detect_anomalies: need at least 10 rows, got {len(sales_df)}."
        )

    df = sales_df.copy()

    # Prepare features
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0)

    # Derived feature: margin ratio
    safe_purchase = df["purchase_price"].replace(0, np.nan)
    df["margin_ratio"] = (
        (df["sale_price"] - df["purchase_price"]) / safe_purchase
    ).fillna(0)

    feature_matrix = df[["discount_pct", "quantity", "sale_price",
                          "purchase_price", "margin_ratio"]].values

    # Scale features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(feature_matrix)

    # Fit Isolation Forest
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    raw_predictions = model.fit_predict(features_scaled)
    anomaly_scores = model.decision_function(features_scaled)

    # Isolation Forest: -1 = anomaly, +1 = normal
    df["anomaly_score"] = anomaly_scores.round(6)
    df["is_anomaly"] = raw_predictions == -1

    n_anomalies = int(df["is_anomaly"].sum())
    anomaly_rate = n_anomalies / len(df)

    # MLflow logging (non-fatal)
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name="isolation_forest_anomaly"):
            mlflow.log_param("contamination", contamination)
            mlflow.log_param("n_estimators", n_estimators)
            mlflow.log_param("random_state", random_state)
            mlflow.log_param("n_rows", len(df))
            mlflow.log_param("features_used", str(["discount_pct", "quantity",
                                                    "sale_price", "purchase_price",
                                                    "margin_ratio"]))
            mlflow.log_metric("n_anomalies", n_anomalies)
            mlflow.log_metric("anomaly_rate", round(anomaly_rate, 4))
            try:
                mlflow.sklearn.log_model(model, artifact_path="isolation_forest_model")
            except Exception as exc:  # noqa: BLE001
                logger.warning("detect_anomalies: could not log model: %s", exc)
    except Exception as exc:
        logger.warning("MLflow logging failed (non-fatal): %s", exc)

    logger.info(
        "detect_anomalies: %d anomalies detected (%.1f%% of %d transactions).",
        n_anomalies, anomaly_rate * 100, len(df),
    )
    return df


# ---------------------------------------------------------------------------
# 2. Discount Anomalies (Statistical)
# ---------------------------------------------------------------------------

def flag_discount_anomalies(
    sales_df: pd.DataFrame,
    sigma_threshold: float = 2.0,
    absolute_min_discount: float = 5.0,
) -> pd.DataFrame:
    """
    Flag transactions with unusually high discount percentages.

    A transaction is flagged if:
        discount_pct > mean(discount_pct) + sigma_threshold × std(discount_pct)
    AND
        discount_pct >= absolute_min_discount

    Added columns:
    - ``discount_mean``         : population mean discount
    - ``discount_std``          : population standard deviation
    - ``discount_threshold``    : mean + sigma_threshold × std
    - ``is_discount_anomaly``   : True if flagged
    - ``discount_severity``     : 'EXTREME' (>3σ) | 'HIGH' (>2σ) | 'NORMAL'

    Args:
        sales_df:            Standardized sales DataFrame.
        sigma_threshold:     Standard deviations above mean to flag (default 2.0).
        absolute_min_discount: Minimum discount % to consider (default 5.0).

    Returns:
        Copy of ``sales_df`` with the five new columns added.

    Raises:
        ValueError: If ``discount_pct`` column is missing.
    """
    if "discount_pct" not in sales_df.columns:
        raise ValueError(
            "flag_discount_anomalies: 'discount_pct' column missing."
        )

    df = sales_df.copy()
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0)

    mean_disc = float(df["discount_pct"].mean())
    std_disc = float(df["discount_pct"].std())
    threshold = mean_disc + sigma_threshold * std_disc

    df["discount_mean"] = round(mean_disc, 2)
    df["discount_std"] = round(std_disc, 2)
    df["discount_threshold"] = round(threshold, 2)

    df["is_discount_anomaly"] = (
        (df["discount_pct"] > threshold)
        & (df["discount_pct"] >= absolute_min_discount)
    )

    def _severity(row: pd.Series) -> str:
        if not row["is_discount_anomaly"]:
            return "NORMAL"
        z = (row["discount_pct"] - mean_disc) / std_disc if std_disc > 0 else 0
        return "EXTREME" if z > 3 else "HIGH"

    df["discount_severity"] = df.apply(_severity, axis=1)

    n_flagged = int(df["is_discount_anomaly"].sum())
    logger.info(
        "flag_discount_anomalies: %d transactions flagged (threshold=%.1f%%).",
        n_flagged, threshold,
    )
    return df


# ---------------------------------------------------------------------------
# 3. Salesperson Anomalies
# ---------------------------------------------------------------------------

def flag_salesperson_anomalies(
    sales_df: pd.DataFrame,
    min_transactions: int = 5,
) -> pd.DataFrame:
    """
    Detect per-salesperson outliers in discount and return patterns.

    For each salesperson, computes:
    - Mean discount given
    - Fraction of high-discount transactions (> 15%)
    - Total transactions count

    A salesperson is flagged if their mean discount exceeds the overall
    salesperson-level mean + 1.5σ.

    Args:
        sales_df:          Standardized sales DataFrame.
        min_transactions:  Minimum transactions to include a salesperson
                           in analysis (default 5).

    Returns:
        DataFrame with one row per salesperson and columns:
        ``['salesperson', 'n_transactions', 'mean_discount_pct',
           'high_discount_count', 'high_discount_rate',
           'total_revenue', 'total_quantity',
           'discount_z_score', 'is_flagged', 'flag_reason']``
        Sorted by ``discount_z_score`` descending.

    Raises:
        ValueError: If ``salesperson`` or ``discount_pct`` columns are missing.
    """
    required = {"salesperson", "discount_pct", "sale_price", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"flag_salesperson_anomalies: missing columns {missing!r}."
        )

    df = sales_df.copy()
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0)
    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).clip(lower=1)
    df["line_revenue"] = df["sale_price"] * df["quantity"]

    # Per-salesperson aggregation
    sp_agg = (
        df.groupby("salesperson")
        .agg(
            n_transactions=("discount_pct", "count"),
            mean_discount_pct=("discount_pct", "mean"),
            high_discount_count=("discount_pct", lambda x: (x > 15).sum()),
            total_revenue=("line_revenue", "sum"),
            total_quantity=("quantity", "sum"),
        )
        .reset_index()
    )
    sp_agg = sp_agg[sp_agg["n_transactions"] >= min_transactions].copy()
    sp_agg["mean_discount_pct"] = sp_agg["mean_discount_pct"].round(2)
    sp_agg["high_discount_rate"] = (
        sp_agg["high_discount_count"] / sp_agg["n_transactions"] * 100
    ).round(1)

    # Z-score of mean discount across salespersons
    overall_mean = float(sp_agg["mean_discount_pct"].mean())
    overall_std = float(sp_agg["mean_discount_pct"].std())

    if overall_std > 0:
        sp_agg["discount_z_score"] = (
            (sp_agg["mean_discount_pct"] - overall_mean) / overall_std
        ).round(3)
    else:
        sp_agg["discount_z_score"] = 0.0

    # Flag: z-score > 1.5 (i.e., 1.5σ above average)
    sp_agg["is_flagged"] = sp_agg["discount_z_score"] > 1.5

    def _flag_reason(row: pd.Series) -> str:
        if not row["is_flagged"]:
            return ""
        reasons = []
        if row["mean_discount_pct"] > overall_mean + 1.5 * overall_std:
            reasons.append(
                f"Mean discount {row['mean_discount_pct']:.1f}% "
                f"({row['discount_z_score']:.1f}σ above average)"
            )
        if row["high_discount_rate"] > 30:
            reasons.append(
                f"{row['high_discount_rate']:.0f}% of transactions have >15% discount"
            )
        return "; ".join(reasons) if reasons else "Unusual discount pattern"

    sp_agg["flag_reason"] = sp_agg.apply(_flag_reason, axis=1)

    result = sp_agg.sort_values("discount_z_score", ascending=False).reset_index(drop=True)

    n_flagged = int(result["is_flagged"].sum())
    logger.info(
        "flag_salesperson_anomalies: %d of %d salespersons flagged.",
        n_flagged, len(result),
    )
    return result


# ---------------------------------------------------------------------------
# 4. Anomaly Summary Report
# ---------------------------------------------------------------------------

def get_anomaly_summary(
    anomaly_df: pd.DataFrame,
    top_n: int = 5,
) -> dict:
    """
    Generate a summary report of detected anomalies.

    Args:
        anomaly_df: Output of ``detect_anomalies`` with ``is_anomaly``,
                    ``anomaly_score``, ``sale_price``, ``quantity`` columns.
        top_n:      Number of top flagged transactions to return (default 5).

    Returns:
        Dictionary with keys:
        - ``'total_transactions'``  : int
        - ``'n_anomalies'``         : int
        - ``'anomaly_rate_pct'``    : float (0–100)
        - ``'total_anomaly_value'`` : float (INR) — sum of flagged transaction values
        - ``'avg_anomaly_score'``   : float — mean score of flagged transactions
        - ``'top_anomalies'``       : list of dicts, top-N by most negative anomaly score
        - ``'summary_text'``        : plain-English one-line summary

    Raises:
        ValueError: If ``is_anomaly`` or ``anomaly_score`` columns are missing.
    """
    required = {"is_anomaly", "anomaly_score"}
    missing = required - set(anomaly_df.columns)
    if missing:
        raise ValueError(
            f"get_anomaly_summary: missing columns {missing!r}. "
            "Run detect_anomalies() first."
        )

    df = anomaly_df.copy()
    df["sale_price"] = pd.to_numeric(df.get("sale_price", pd.Series(0, index=df.index)),
                                     errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df.get("quantity", pd.Series(1, index=df.index)),
                                   errors="coerce").fillna(1).clip(lower=1)
    df["transaction_value"] = df["sale_price"] * df["quantity"]

    anomalies = df[df["is_anomaly"]].copy()
    n_anomalies = len(anomalies)
    total = len(df)
    anomaly_rate = (n_anomalies / total * 100) if total > 0 else 0.0

    total_anomaly_value = float(anomalies["transaction_value"].sum())
    avg_score = float(anomalies["anomaly_score"].mean()) if n_anomalies > 0 else 0.0

    # Top N most anomalous (most negative score)
    top_cols = ["invoice_no", "date", "customer_name", "product_name",
                "discount_pct", "sale_price", "quantity",
                "anomaly_score", "transaction_value"]
    available_cols = [c for c in top_cols if c in anomalies.columns]

    top_anomalies_df = anomalies.sort_values("anomaly_score").head(top_n)[available_cols]
    top_anomalies = top_anomalies_df.to_dict(orient="records")

    summary_text = (
        f"Anomaly Detection: {n_anomalies} suspicious transactions detected "
        f"({anomaly_rate:.1f}% of {total} total). "
        f"Total value of flagged transactions: ₹{total_anomaly_value:,.0f}."
    )

    return {
        "total_transactions": total,
        "n_anomalies": n_anomalies,
        "anomaly_rate_pct": round(anomaly_rate, 2),
        "total_anomaly_value": round(total_anomaly_value, 2),
        "avg_anomaly_score": round(avg_score, 6),
        "top_anomalies": top_anomalies,
        "summary_text": summary_text,
    }
