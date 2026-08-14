"""
engine/__init__.py
==================
Engine package for the Wholesale BI System.

Exposes the primary public API from all seven engine modules so that
Streamlit pages and FastAPI routes can import with a single line:

    from engine import standardize_sales, detect_dead_stock, forecast_demand

Modules:
    data_cleaner     — Canonical schema standardizer
    analytics        — Business analytics (dead stock, payments, margins)
    scoring          — Urgency and risk scoring formulas
    forecasting      — Facebook Prophet demand forecasting
    segmentation     — RFM + K-Means customer segmentation
    anomaly_detector — Isolation Forest anomaly detection
    recommender      — Recommendation engine orchestrator

Author: Wholesale BI System
Python: 3.12
"""

# Data cleaning & validation
from engine.data_cleaner import (
    standardize_sales,
    standardize_inventory,
    standardize_customers,
    standardize_purchases,
    clean_dataframe,
    validate_csv_upload,
    load_and_standardize,
)

# Business analytics
from engine.analytics import (
    detect_dead_stock,
    get_outstanding_payments,
    calculate_margins,
    area_sales_ranking,
    monthly_revenue_trend,
    category_month_heatmap,
)

# Scoring formulas
from engine.scoring import (
    urgency_score,
    normalize_factor,
    risk_score_payment,
    dead_stock_score,
    compute_days_factor,
    compute_amount_factor,
    compute_trend_factor,
    score_payment_dataframe,
)

# Demand forecasting
from engine.forecasting import (
    forecast_demand,
    detect_demand_spikes,
    detect_declining_products,
    get_days_coverage,
    INDIAN_FESTIVALS,
)

# Customer segmentation
from engine.segmentation import (
    compute_rfm,
    segment_customers,
    get_segment_recommendations,
    cohort_retention,
)

# Anomaly detection
from engine.anomaly_detector import (
    detect_anomalies,
    flag_discount_anomalies,
    flag_salesperson_anomalies,
    get_anomaly_summary,
)

# Recommendation engine
from engine.recommender import (
    Recommendation,
    generate_recommendations,
    ceo_morning_briefing,
    filter_by_category,
    recommendations_to_dataframe,
)

__all__ = [
    # data_cleaner
    "standardize_sales",
    "standardize_inventory",
    "standardize_customers",
    "standardize_purchases",
    "clean_dataframe",
    "validate_csv_upload",
    "load_and_standardize",
    # analytics
    "detect_dead_stock",
    "get_outstanding_payments",
    "calculate_margins",
    "area_sales_ranking",
    "monthly_revenue_trend",
    "category_month_heatmap",
    # scoring
    "urgency_score",
    "normalize_factor",
    "risk_score_payment",
    "dead_stock_score",
    "compute_days_factor",
    "compute_amount_factor",
    "compute_trend_factor",
    "score_payment_dataframe",
    # forecasting
    "forecast_demand",
    "detect_demand_spikes",
    "detect_declining_products",
    "get_days_coverage",
    "INDIAN_FESTIVALS",
    # segmentation
    "compute_rfm",
    "segment_customers",
    "get_segment_recommendations",
    "cohort_retention",
    # anomaly_detector
    "detect_anomalies",
    "flag_discount_anomalies",
    "flag_salesperson_anomalies",
    "get_anomaly_summary",
    # recommender
    "Recommendation",
    "generate_recommendations",
    "ceo_morning_briefing",
    "filter_by_category",
    "recommendations_to_dataframe",
]
