"""
engine/segmentation.py
======================
RFM analysis and K-Means customer segmentation for the Wholesale BI System.

Features:
- RFM scoring with pd.qcut (quintile-based 1–5 scoring).
- K-Means clustering with Elbow Method and Silhouette Score validation.
- Elbow and silhouette plots saved as PNG to the data/ folder.
- Cluster-to-segment name mapping: Champions / Loyal / At Risk / Lost.
- Plain-English recommendation generation per customer.
- Cohort retention analysis (month-0 cohort table).
- Full MLflow tracking under experiment 'wholesale_segmentation'.

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MLFLOW_EXPERIMENT = "wholesale_segmentation"
PLOT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)

# Segment labels ordered from best to worst customer value
SEGMENT_LABELS: list[str] = ["Champions", "Loyal", "At Risk", "Lost"]


# ---------------------------------------------------------------------------
# 1. RFM Computation
# ---------------------------------------------------------------------------

def compute_rfm(
    sales_df: pd.DataFrame,
    customer_df: pd.DataFrame,
    reference_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Compute Recency, Frequency, and Monetary (RFM) scores for each customer.

    Scoring method: quintile-based using pd.qcut (1 = worst, 5 = best).
    Recency score is inverted (lower days = higher score).

    RFM_Score = R_score + F_score + M_score (range: 3–15)

    Args:
        sales_df:       Standardized sales DataFrame with ``date``,
                        ``customer_name``, ``sale_price``, ``quantity``.
        customer_df:    Standardized customer DataFrame for area/type metadata.
        reference_date: "Today" for recency calculation. Defaults to max
                        sale date + 1 day.

    Returns:
        DataFrame with columns:
        ``['customer_name', 'recency_days', 'frequency', 'monetary',
           'R_score', 'F_score', 'M_score', 'RFM_score',
           'area', 'customer_type']``

    Raises:
        ValueError: If required columns are missing.
    """
    required_sales = {"date", "customer_name", "sale_price", "quantity"}
    missing = required_sales - set(sales_df.columns)
    if missing:
        raise ValueError(f"compute_rfm: missing sales columns {missing!r}.")

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).clip(lower=1)
    df["discount_pct"] = pd.to_numeric(
        df.get("discount_pct", pd.Series(0, index=df.index)), errors="coerce"
    ).fillna(0)
    df["line_value"] = df["sale_price"] * (1 - df["discount_pct"] / 100) * df["quantity"]

    ref = pd.Timestamp(reference_date) if reference_date else (
        df["date"].max() + pd.Timedelta(days=1)
    )

    rfm = (
        df.groupby("customer_name")
        .agg(
            recency_days=("date", lambda x: (ref - x.max()).days),
            frequency=("date", "count"),
            monetary=("line_value", "sum"),
        )
        .reset_index()
    )

    # Quintile scoring — handle ties with duplicates="drop"
    def _safe_qcut(series: pd.Series, ascending: bool = True) -> pd.Series:
        """Apply qcut with fallback for low-cardinality data."""
        try:
            labels = [1, 2, 3, 4, 5] if ascending else [5, 4, 3, 2, 1]
            return pd.qcut(series, q=5, labels=labels, duplicates="drop").astype(float)
        except ValueError:
            # If not enough distinct values, use rank-based approach
            return pd.cut(
                series,
                bins=5,
                labels=[1, 2, 3, 4, 5] if ascending else [5, 4, 3, 2, 1],
                duplicates="drop",
            ).astype(float)

    # Recency: lower days = better = higher score → descending
    rfm["R_score"] = _safe_qcut(rfm["recency_days"], ascending=False)
    rfm["F_score"] = _safe_qcut(rfm["frequency"], ascending=True)
    rfm["M_score"] = _safe_qcut(rfm["monetary"], ascending=True)

    # Fill NaN scores (from single-bin qcut) with median score 3
    for col in ["R_score", "F_score", "M_score"]:
        rfm[col] = rfm[col].fillna(3.0).astype(int)

    rfm["RFM_score"] = rfm["R_score"] + rfm["F_score"] + rfm["M_score"]

    # Merge customer metadata
    meta_cols = ["customer_name"]
    for col in ["area", "customer_type", "outstanding_amount", "total_business_ytd"]:
        if col in customer_df.columns:
            meta_cols.append(col)

    cust_meta = customer_df[meta_cols].drop_duplicates("customer_name")
    rfm = rfm.merge(cust_meta, on="customer_name", how="left")

    logger.info(
        "compute_rfm: %d customers scored. RFM range: %d–%d.",
        len(rfm), rfm["RFM_score"].min(), rfm["RFM_score"].max(),
    )
    return rfm


# ---------------------------------------------------------------------------
# 2. K-Means Segmentation
# ---------------------------------------------------------------------------

def segment_customers(
    rfm_df: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Apply K-Means clustering to RFM scores and map to business segment names.

    Validation:
    - Elbow Method: inertia for k=2..6
    - Silhouette Score: for k=2..6
    Both plots are saved as PNG files to the ``data/`` folder.

    Cluster-to-segment mapping (by RFM_score centroid rank):
    1st (highest centroid) → Champions
    2nd → Loyal
    3rd → At Risk
    4th (lowest) → Lost

    Args:
        rfm_df:       Output of ``compute_rfm`` with columns
                      ``['R_score', 'F_score', 'M_score', 'RFM_score']``.
        n_clusters:   Number of K-Means clusters (default 4).
        random_state: Random seed for reproducibility.

    Returns:
        Copy of ``rfm_df`` with added columns:
        ``['cluster', 'segment', 'cluster_rfm_mean']``

    Raises:
        ValueError: If required score columns are missing or too few customers.
    """
    required = {"R_score", "F_score", "M_score", "RFM_score"}
    missing = required - set(rfm_df.columns)
    if missing:
        raise ValueError(
            f"segment_customers: missing columns {missing!r} in rfm_df."
        )
    if len(rfm_df) < n_clusters:
        logger.warning(
            f"segment_customers: {len(rfm_df)} customers < n_clusters={n_clusters}. Returning default segment."
        )
        df = rfm_df.copy()
        df["cluster"] = 0
        df["segment"] = "Champions"
        df["cluster_rfm_mean"] = df["RFM_score"].round(2)
        return df

    features = rfm_df[["R_score", "F_score", "M_score"]].values.astype(float)
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # ---- Elbow + Silhouette validation ----
    k_range = range(2, min(7, len(rfm_df)))
    inertias: list[float] = []
    sil_scores: list[float] = []

    for k in k_range:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(features_scaled)
        inertias.append(km.inertia_)
        if k > 1:
            sil_scores.append(float(silhouette_score(features_scaled, labels)))
        else:
            sil_scores.append(0.0)

    # Save elbow plot
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    elbow_path = os.path.join(PLOT_OUTPUT_DIR, "kmeans_elbow_plot.png")
    _plot_elbow(list(k_range), inertias, elbow_path)

    # Save silhouette plot
    sil_path = os.path.join(PLOT_OUTPUT_DIR, "kmeans_silhouette_plot.png")
    _plot_silhouette(list(k_range), sil_scores, sil_path)

    # Fit final model
    final_model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    cluster_labels = final_model.fit_predict(features_scaled)
    final_inertia = float(final_model.inertia_)

    try:
        final_sil = float(silhouette_score(features_scaled, cluster_labels))
    except ValueError:
        final_sil = 0.0

    # Map clusters to segment names by centroid RFM mean (descending = Champions first)
    df = rfm_df.copy()
    df["cluster"] = cluster_labels

    cluster_means = (
        df.groupby("cluster")["RFM_score"].mean().sort_values(ascending=False)
    )
    cluster_to_segment = {
        int(cluster_id): SEGMENT_LABELS[min(rank, len(SEGMENT_LABELS) - 1)]
        for rank, cluster_id in enumerate(cluster_means.index)
    }
    df["segment"] = df["cluster"].map(cluster_to_segment)
    df["cluster_rfm_mean"] = df["cluster"].map(
        df.groupby("cluster")["RFM_score"].mean().round(2)
    )

    # MLflow logging (non-fatal)
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name="customer_segmentation"):
            mlflow.log_param("n_clusters", n_clusters)
            mlflow.log_param("random_state", random_state)
            mlflow.log_param("n_customers", len(df))
            mlflow.log_metric("silhouette_score", round(final_sil, 4))
            mlflow.log_metric("inertia", round(final_inertia, 2))
            mlflow.log_artifact(elbow_path)
            mlflow.log_artifact(sil_path)
            try:
                mlflow.sklearn.log_model(final_model, artifact_path="kmeans_model")
            except Exception as exc:  # noqa: BLE001
                logger.warning("segment_customers: could not log KMeans model: %s", exc)
    except Exception as exc:
        logger.warning("MLflow logging failed (non-fatal): %s", exc)

    logger.info(
        "segment_customers: silhouette=%.4f, inertia=%.2f. Segments: %s",
        final_sil, final_inertia,
        df["segment"].value_counts().to_dict(),
    )
    return df


# ---------------------------------------------------------------------------
# 3. Segment Recommendations
# ---------------------------------------------------------------------------

def get_segment_recommendations(segment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate plain-English recommendations for each customer based on segment.

    Recommendation templates:
    - Champions : 'Priority customer - offer bulk discount'
    - Loyal     : 'Maintain relationship - monthly check-in'
    - At Risk   : 'RETENTION ALERT: No order in X days, last ₹Y/month'
    - Lost      : 'RECOVERY: Last order Z days ago - visit in person'

    Args:
        segment_df: Output of ``segment_customers`` with ``segment``,
                    ``recency_days``, ``monetary``, ``frequency`` columns.

    Returns:
        Copy of ``segment_df`` with an added ``recommendation`` column.

    Raises:
        ValueError: If ``segment`` column is missing.
    """
    if "segment" not in segment_df.columns:
        raise ValueError(
            "get_segment_recommendations: 'segment' column missing. "
            "Run segment_customers() first."
        )

    df = segment_df.copy()

    def _recommend(row: pd.Series) -> str:
        segment = row.get("segment", "Unknown")
        recency = int(row.get("recency_days", 0))
        monetary = float(row.get("monetary", 0))
        frequency = int(row.get("frequency", 0))
        monthly_spend = round(monetary / max((recency / 30), 1), 0)

        if segment == "Champions":
            return (
                f"🏆 Priority customer — offer bulk discount & priority delivery. "
                f"Orders {frequency}x with ₹{monetary:,.0f} lifetime spend. "
                f"Last order {recency} days ago — keep engaged!"
            )
        elif segment == "Loyal":
            return (
                f"✅ Loyal customer — maintain relationship with monthly check-in. "
                f"{frequency} orders totalling ₹{monetary:,.0f}. "
                f"Last order {recency} days ago. "
                f"Consider loyalty programme or early access to new stock."
            )
        elif segment == "At Risk":
            return (
                f"⚠️ RETENTION ALERT: No order in {recency} days. "
                f"Last spending ≈ ₹{monthly_spend:,.0f}/month. "
                f"Lifetime value ₹{monetary:,.0f}. "
                f"Call personally — offer 5% retention discount."
            )
        elif segment == "Lost":
            return (
                f"🚨 RECOVERY: Last order {recency} days ago. "
                f"Customer appears inactive (only {frequency} order(s), "
                f"₹{monetary:,.0f} total). "
                f"Visit in person — understand reason for churn."
            )
        else:
            return f"Segment '{segment}' — review customer manually."

    df["recommendation"] = df.apply(_recommend, axis=1)
    logger.info(
        "get_segment_recommendations: generated %d recommendations.", len(df)
    )
    return df


# ---------------------------------------------------------------------------
# 4. Cohort Retention
# ---------------------------------------------------------------------------

def cohort_retention(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a month-0 cohort retention table.

    Groups customers by their first purchase month (cohort) and tracks what
    percentage return in subsequent months (month 1, 2, …).

    This is a standard interview talking point demonstrating customer loyalty
    analysis capability.

    Args:
        sales_df: Standardized sales DataFrame with ``date`` and
                  ``customer_name`` columns.

    Returns:
        Pivot DataFrame where:
        - Index: cohort month (YYYY-MM string)
        - Columns: months since first purchase (0, 1, 2, …)
        - Values: retention percentage (0–100), with cohort size in column 0

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"date", "customer_name"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"cohort_retention: missing columns {missing!r}."
        )

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["order_period"] = df["date"].dt.to_period("M")

    # First purchase month per customer (cohort assignment)
    first_purchase = (
        df.groupby("customer_name")["order_period"].min().reset_index()
    )
    first_purchase.columns = ["customer_name", "cohort_period"]

    df = df.merge(first_purchase, on="customer_name", how="left")
    df["period_number"] = (
        df["order_period"].apply(lambda p: p.ordinal)
        - df["cohort_period"].apply(lambda p: p.ordinal)
    )

    # Count unique customers per (cohort, period_number)
    cohort_data = (
        df.groupby(["cohort_period", "period_number"])["customer_name"]
        .nunique()
        .reset_index()
    )
    cohort_data.columns = ["cohort_period", "period_number", "n_customers"]

    # Pivot
    cohort_pivot = cohort_data.pivot_table(
        index="cohort_period", columns="period_number", values="n_customers"
    )

    # Cohort sizes (month 0)
    cohort_sizes = cohort_pivot[0]

    # Retention percentages
    retention = cohort_pivot.divide(cohort_sizes, axis=0).round(4) * 100

    # Convert Period index to strings
    retention.index = retention.index.astype(str)
    retention.columns = [int(c) for c in retention.columns]
    retention = retention.fillna(0).round(1)

    logger.info(
        "cohort_retention: %d cohorts, max %d months tracked.",
        len(retention), len(retention.columns),
    )
    return retention


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _plot_elbow(k_range: list[int], inertias: list[float], save_path: str) -> None:
    """
    Save an elbow plot of KMeans inertia vs k.

    Args:
        k_range:   List of k values tested.
        inertias:  Inertia for each k.
        save_path: File path for the output PNG.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(k_range, inertias, marker="o", linewidth=2, color="#2196F3")
    ax.set_xlabel("Number of Clusters (k)", fontsize=12)
    ax.set_ylabel("Inertia (Within-Cluster SSE)", fontsize=12)
    ax.set_title("K-Means Elbow Method", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(k_range)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Elbow plot saved to %s", save_path)


def _plot_silhouette(k_range: list[int], scores: list[float], save_path: str) -> None:
    """
    Save a silhouette score plot vs k.

    Args:
        k_range:   List of k values tested.
        scores:    Silhouette score for each k.
        save_path: File path for the output PNG.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(k_range, scores, marker="s", linewidth=2, color="#4CAF50")
    ax.set_xlabel("Number of Clusters (k)", fontsize=12)
    ax.set_ylabel("Silhouette Score", fontsize=12)
    ax.set_title("K-Means Silhouette Score", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(k_range)
    ax.set_ylim(0, 1)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Silhouette plot saved to %s", save_path)
