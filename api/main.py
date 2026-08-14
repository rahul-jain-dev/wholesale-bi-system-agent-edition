"""
api/main.py
===========
FastAPI backend for the Wholesale BI System.
Exposes 5 endpoints for CSV upload, analytics, forecasting,
recommendations, and customer segmentation.

Run with:
    uvicorn api.main:app --reload --port 8000

Author: Rahul Jain | JECRC Foundation, Jaipur
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add project root to path so engine imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.analytics import (
    area_sales_ranking,
    calculate_margins,
    category_month_heatmap,
    detect_dead_stock,
    get_outstanding_payments,
    monthly_revenue_trend,
)
from engine.anomaly_detector import detect_anomalies, get_anomaly_summary
from engine.data_cleaner import (
    standardize_customers,
    standardize_inventory,
    standardize_sales,
)
from engine.forecasting import (
    detect_declining_products,
    detect_demand_spikes,
    forecast_demand,
)
from engine.recommender import ceo_morning_briefing, generate_recommendations
from engine.segmentation import compute_rfm, get_segment_recommendations, segment_customers

# ── App Initialization ────────────────────────────────────────────────────────
app = FastAPI(
    title="Wholesale BI System API",
    description=(
        "AI-powered Business Intelligence API for Indian wholesale distributors. "
        "Converts ERP-exported CSVs into plain-English business recommendations."
    ),
    version="1.0.0",
    contact={
        "name": "Rahul Jain",
        "url": "https://github.com/Rahuljain3851/wholesale-bi-system",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Streamlit localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store (single-user demo) ────────────────────────────────
_SESSION: dict[str, pd.DataFrame] = {}

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_defaults() -> bool:
    """Load generated CSVs as defaults if no upload has been done."""
    try:
        _SESSION["sales"]     = pd.read_csv(DATA_DIR / "sales_data.csv")
        _SESSION["inventory"] = pd.read_csv(DATA_DIR / "inventory_data.csv")
        _SESSION["customers"] = pd.read_csv(DATA_DIR / "customer_data.csv")
        _SESSION["purchases"] = pd.read_csv(DATA_DIR / "purchase_data.csv")
        return True
    except FileNotFoundError:
        return False


def _ensure_data() -> None:
    """Raise HTTP 400 if no data is loaded."""
    if "sales" not in _SESSION:
        if not _load_defaults():
            raise HTTPException(
                status_code=400,
                detail=(
                    "No data loaded. Upload CSVs via POST /upload "
                    "or generate synthetic data with: python data/data_generator.py"
                ),
            )


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Upload
# ═════════════════════════════════════════════════════════════════════════════
class UploadSummary(BaseModel):
    status: str
    files_received: list[str]
    total_sales_rows: int
    total_inventory_rows: int
    total_customers: int
    date_range: str
    total_revenue: float
    message: str


@app.post("/upload", response_model=UploadSummary, tags=["Data"])
async def upload_csvs(
    sales: UploadFile = File(..., description="sales_data.csv from ERP"),
    inventory: UploadFile = File(..., description="inventory_data.csv from ERP"),
    customers: UploadFile = File(..., description="customer_data.csv from ERP"),
    purchases: UploadFile | None = File(None, description="purchase_data.csv (optional)"),
) -> UploadSummary:
    """
    Accept CSV exports from any ERP (Kuber, Tally, Marg) and standardize
    them to the canonical schema. Returns a summary of loaded data.
    """
    try:
        sales_df = standardize_sales(
            pd.read_csv(io.StringIO((await sales.read()).decode("utf-8")))
        )
        inv_df = standardize_inventory(
            pd.read_csv(io.StringIO((await inventory.read()).decode("utf-8")))
        )
        cust_df = standardize_customers(
            pd.read_csv(io.StringIO((await customers.read()).decode("utf-8")))
        )

        _SESSION["sales"]     = sales_df
        _SESSION["inventory"] = inv_df
        _SESSION["customers"] = cust_df

        if purchases:
            _SESSION["purchases"] = pd.read_csv(
                io.StringIO((await purchases.read()).decode("utf-8"))
            )

        date_col = pd.to_datetime(sales_df["date"])
        total_rev = float((sales_df["sale_price"] * sales_df["quantity"]).sum())

        files = ["sales", "inventory", "customers"] + (["purchases"] if purchases else [])

        return UploadSummary(
            status="success",
            files_received=files,
            total_sales_rows=len(sales_df),
            total_inventory_rows=len(inv_df),
            total_customers=len(cust_df),
            date_range=f"{date_col.min().date()} → {date_col.max().date()}",
            total_revenue=round(total_rev, 2),
            message="Data loaded and standardized. All analytics ready.",
        )

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CSV parsing error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — Analytics
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/analytics", tags=["Analytics"])
async def get_analytics() -> dict[str, Any]:
    """
    Returns complete business analytics including:
    - Dead stock analysis with capital blocked
    - Outstanding payments with risk scoring
    - GST-aware margin analysis per company/category
    - Area-wise sales ranking
    - Monthly revenue trend
    """
    _ensure_data()
    try:
        sales_df     = _SESSION["sales"]
        inventory_df = _SESSION["inventory"]
        customer_df  = _SESSION["customers"]

        dead_stock     = detect_dead_stock(inventory_df)
        outstanding    = get_outstanding_payments(sales_df, customer_df)
        margins        = calculate_margins(sales_df)
        area_rank      = area_sales_ranking(sales_df)
        monthly_trend  = monthly_revenue_trend(sales_df)

        return {
            "dead_stock":      dead_stock.to_dict(orient="records"),
            "outstanding":     outstanding.to_dict(orient="records"),
            "margins":         {
                "by_product":  margins["by_product"].head(20).to_dict(orient="records"),
                "by_company":  margins["by_company"].to_dict(orient="records"),
                "by_category": margins["by_category"].to_dict(orient="records"),
            },
            "area_ranking":    area_rank.to_dict(orient="records"),
            "monthly_trend":   monthly_trend.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3 — Forecast
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/forecast", tags=["ML"])
async def get_forecast(periods: int = 30) -> dict[str, Any]:
    """
    Runs Facebook Prophet demand forecasting per category.
    Uses real Indian festival dates as custom seasonality regressors.
    Returns: forecast values, confidence intervals, demand spikes, declining products.
    """
    _ensure_data()
    try:
        sales_df     = _SESSION["sales"]
        inventory_df = _SESSION["inventory"]

        categories = sales_df["category"].dropna().unique().tolist()
        forecasts = {}

        for cat in categories:
            try:
                fc = forecast_demand(sales_df, category=cat, periods=periods)
                forecasts[cat] = fc[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(periods).to_dict(orient="records")
            except Exception:
                forecasts[cat] = []  # sparse data for category — skip gracefully

        spikes   = detect_demand_spikes(
            {cat: pd.DataFrame(v) for cat, v in forecasts.items()},
            inventory_df,
        )
        declining = detect_declining_products(sales_df)

        return {
            "forecasts_by_category": forecasts,
            "demand_spikes":         spikes.to_dict(orient="records") if not spikes.empty else [],
            "declining_products":    declining.to_dict(orient="records") if not declining.empty else [],
            "periods":               periods,
            "note": "Forecasts use real Diwali/Holi/Navratri/Eid/Dussehra dates as custom holiday regressors.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4 — Recommendations
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/recommendations", tags=["Recommendations"])
async def get_recommendations(category: str = "All") -> dict[str, Any]:
    """
    Returns prioritized plain-English business recommendations sorted by ₹ impact.
    Categories: All, Inventory, Payment, Customer, Sales, Anomaly
    Includes CEO Morning Briefing — top 5 actions as one paragraph.
    """
    _ensure_data()
    try:
        sales_df     = _SESSION["sales"]
        inventory_df = _SESSION["inventory"]
        customer_df  = _SESSION["customers"]

        dead_stock  = detect_dead_stock(inventory_df)
        outstanding = get_outstanding_payments(sales_df, customer_df)
        rfm_df      = compute_rfm(sales_df, customer_df)
        segment_df  = segment_customers(rfm_df)
        anomaly_df  = detect_anomalies(sales_df)

        # Simplified forecast spikes (fast path)
        try:
            fc = forecast_demand(sales_df, category="FMCG", periods=30)
            spike_df = detect_demand_spikes({"FMCG": fc}, inventory_df)
        except Exception:
            spike_df = pd.DataFrame()

        recommendations = generate_recommendations(
            dead_stock_df=dead_stock,
            outstanding_df=outstanding,
            forecast_alerts=spike_df,
            segment_df=segment_df,
            anomaly_df=anomaly_df,
        )

        briefing = ceo_morning_briefing(recommendations)

        # Filter by category
        if category != "All":
            recommendations = [r for r in recommendations if r.get("category") == category]

        return {
            "ceo_morning_briefing": briefing,
            "total_recommendations": len(recommendations),
            "total_opportunity_rupees": sum(r.get("impact_rupees", 0) for r in recommendations),
            "recommendations": recommendations,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5 — Customer Segments
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/segments", tags=["ML"])
async def get_segments() -> dict[str, Any]:
    """
    Returns RFM-based K-Means customer segmentation.
    Clusters validated with Elbow Method and Silhouette Score.
    Segments: Champions, Loyal, At Risk, Lost
    """
    _ensure_data()
    try:
        sales_df    = _SESSION["sales"]
        customer_df = _SESSION["customers"]

        rfm_df     = compute_rfm(sales_df, customer_df)
        segment_df = segment_customers(rfm_df)
        recs       = get_segment_recommendations(segment_df)

        segment_summary = (
            segment_df.groupby("segment")
            .agg(
                customer_count=("customer_name", "count"),
                avg_monetary=("monetary", "mean"),
                avg_recency_days=("recency_days", "mean"),
                avg_frequency=("frequency", "mean"),
            )
            .round(2)
            .reset_index()
            .to_dict(orient="records")
        )

        return {
            "segment_summary": segment_summary,
            "customer_segments": segment_df.to_dict(orient="records"),
            "segment_recommendations": recs,
            "model_info": {
                "algorithm": "K-Means (k=4)",
                "features": ["Recency", "Frequency", "Monetary"],
                "validation": "Elbow Method + Silhouette Score",
                "note": "Silhouette plots saved in data/ directory",
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segmentation error: {str(e)}")


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Returns API health status."""
    data_loaded = "sales" in _SESSION
    return {
        "status": "healthy",
        "data_loaded": str(data_loaded),
        "version": "1.0.0",
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
