"""
engine/forecasting.py
=====================
Facebook Prophet demand forecasting for the Wholesale BI System.

Features:
- Real Indian festival holidays (2023–2027) as Prophet custom regressors.
- Per-category demand forecasting with MLflow experiment tracking.
- 30-day holdout validation with MAE and RMSE metrics.
- Demand spike detection against current inventory.
- Declining product detection (3 consecutive months of decline).
- Days-to-stockout calculation per SKU.

MLflow experiment: 'wholesale_forecasting'

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime
from typing import Optional

import mlflow
import mlflow.pyfunc
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*Stan.*")

logger = logging.getLogger(__name__)

MLFLOW_EXPERIMENT = "wholesale_forecasting"

# ---------------------------------------------------------------------------
# Indian Festival Holidays 2023–2027
# ---------------------------------------------------------------------------

INDIAN_FESTIVALS: pd.DataFrame = pd.DataFrame(
    {
        "holiday": [
            # Diwali (2023-2027)
            "Diwali", "Diwali", "Diwali", "Diwali", "Diwali",
            # Holi (2023-2027)
            "Holi", "Holi", "Holi", "Holi", "Holi",
            # Navratri (2023-2027)
            "Navratri", "Navratri", "Navratri", "Navratri", "Navratri",
            # Dussehra (2023-2027)
            "Dussehra", "Dussehra", "Dussehra", "Dussehra", "Dussehra",
            # Eid-ul-Fitr (2023-2027)
            "Eid_ul_Fitr", "Eid_ul_Fitr", "Eid_ul_Fitr", "Eid_ul_Fitr", "Eid_ul_Fitr",
            # Eid-ul-Adha (2025-2027)
            "Eid_ul_Adha", "Eid_ul_Adha", "Eid_ul_Adha",
            # Ganesh Chaturthi (2025-2027)
            "Ganesh_Chaturthi", "Ganesh_Chaturthi", "Ganesh_Chaturthi",
            # Makar Sankranti (2025-2027)
            "Makar_Sankranti", "Makar_Sankranti", "Makar_Sankranti",
            # Raksha Bandhan (2025-2027)
            "Raksha_Bandhan", "Raksha_Bandhan", "Raksha_Bandhan",
            # Janmashtami (2025-2027)
            "Janmashtami", "Janmashtami", "Janmashtami",
            # Pongal (2025-2027)
            "Pongal", "Pongal", "Pongal",
            # Fixed holidays (2023-2027)
            "Republic_Day", "Republic_Day",
            "Independence_Day", "Independence_Day",
            "Gandhi_Jayanti", "Gandhi_Jayanti",
            "Christmas", "Christmas",
            "New_Year", "New_Year",
        ],
        "ds": [
            # Diwali
            "2023-11-12", "2024-11-01", "2025-10-20", "2026-11-08", "2027-10-29",
            # Holi
            "2023-03-08", "2024-03-25", "2025-03-14", "2026-03-03", "2027-03-22",
            # Navratri (start)
            "2023-10-15", "2024-10-03", "2025-10-02", "2026-10-21", "2027-10-11",
            # Dussehra
            "2023-10-24", "2024-10-12", "2025-10-02", "2026-10-20", "2027-10-09",
            # Eid-ul-Fitr
            "2023-03-30", "2024-04-10", "2025-03-31", "2026-03-21", "2027-03-10",
            # Eid-ul-Adha
            "2025-06-07", "2026-05-27", "2027-05-17",
            # Ganesh Chaturthi
            "2025-08-27", "2026-09-15", "2027-09-04",
            # Makar Sankranti
            "2025-01-14", "2026-01-14", "2027-01-14",
            # Raksha Bandhan
            "2025-08-09", "2026-08-28", "2027-08-18",
            # Janmashtami
            "2025-08-16", "2026-09-04", "2027-08-25",
            # Pongal
            "2025-01-14", "2026-01-14", "2027-01-14",
            # Republic Day
            "2023-01-26", "2024-01-26",
            # Independence Day
            "2023-08-15", "2024-08-15",
            # Gandhi Jayanti
            "2023-10-02", "2024-10-02",
            # Christmas
            "2023-12-25", "2024-12-25",
            # New Year
            "2023-01-01", "2024-01-01",
        ],
        "lower_window": [
            # Diwali
            -2, -2, -2, -2, -2,
            # Holi
            -1, -1, -1, -1, -1,
            # Navratri
            -1, -1, -1, -1, -1,
            # Dussehra
            -1, -1, -1, -1, -1,
            # Eid-ul-Fitr
            -1, -1, -1, -1, -1,
            # Eid-ul-Adha
            -1, -1, -1,
            # Ganesh Chaturthi
            -1, -1, -1,
            # Makar Sankranti
            0, 0, 0,
            # Raksha Bandhan
            -1, -1, -1,
            # Janmashtami
            -1, -1, -1,
            # Pongal
            0, 0, 0,
            # Fixed holidays
            0, 0,
            0, 0,
            0, 0,
            -1, -1,
            -1, -1,
        ],
        "upper_window": [
            # Diwali
            3, 3, 3, 3, 3,
            # Holi
            1, 1, 1, 1, 1,
            # Navratri (lasts 9 days)
            9, 9, 9, 9, 9,
            # Dussehra
            1, 1, 1, 1, 1,
            # Eid-ul-Fitr
            1, 1, 1, 1, 1,
            # Eid-ul-Adha
            1, 1, 1,
            # Ganesh Chaturthi
            1, 1, 1,
            # Makar Sankranti
            0, 0, 0,
            # Raksha Bandhan
            1, 1, 1,
            # Janmashtami
            1, 1, 1,
            # Pongal
            1, 1, 1,
            # Fixed holidays
            0, 0,
            0, 0,
            0, 0,
            1, 1,
            0, 0,
        ],
    }
)
INDIAN_FESTIVALS["ds"] = pd.to_datetime(INDIAN_FESTIVALS["ds"])


# ---------------------------------------------------------------------------
# 1. Demand Forecasting
# ---------------------------------------------------------------------------

def forecast_demand(
    sales_df: pd.DataFrame,
    category: str,
    periods: int = 30,
    changepoint_prior_scale: float = 0.05,
    seasonality_mode: str = "multiplicative",
    product_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Forecast daily demand for a category (or specific product) using Prophet.

    The last 30 days of data are held out for validation. MAE and RMSE are
    computed on the holdout and logged to MLflow under experiment
    ``'wholesale_forecasting'``.

    Args:
        sales_df:                 Standardized sales DataFrame with ``date``,
                                  ``category``, ``product_name``, and ``quantity``.
        category:                 Category to filter (e.g. ``'Beverages'``).
        periods:                  Number of future days to forecast (default 30).
        changepoint_prior_scale:  Prophet flexibility parameter (default 0.05).
        seasonality_mode:         ``'multiplicative'`` or ``'additive'``.
        product_name:             If provided, filter to this specific product
                                  within the category.

    Returns:
        Prophet forecast DataFrame with additional columns:
        ``['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'category',
           'product_filter']``
        Only future rows (beyond the training period) are returned.

    Raises:
        ValueError: If no data is found for the given category/product.
        ValueError: If fewer than 10 data points after filtering.
    """
    required = {"date", "category", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"forecast_demand: missing columns {missing!r} in sales_df."
        )

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    # Filter
    mask = df["category"].str.strip() == category.strip()
    if product_name:
        mask &= df["product_name"].str.strip() == product_name.strip()

    filtered = df[mask].copy()

    if filtered.empty:
        filter_desc = f"category='{category}'"
        if product_name:
            filter_desc += f", product='{product_name}'"
        raise ValueError(
            f"forecast_demand: no sales data found for {filter_desc}."
        )

    # Aggregate to daily total demand
    daily = (
        filtered.groupby("date")["quantity"]
        .sum()
        .reset_index()
        .rename(columns={"date": "ds", "quantity": "y"})
        .sort_values("ds")
    )

    # Fill missing dates with 0
    full_range = pd.date_range(daily["ds"].min(), daily["ds"].max(), freq="D")
    daily = daily.set_index("ds").reindex(full_range, fill_value=0).reset_index()
    daily.columns = ["ds", "y"]

    if len(daily) < 10:
        raise ValueError(
            f"forecast_demand: only {len(daily)} data points — need at least 10 "
            f"for '{category}'."
        )

    # 30-day holdout split
    holdout_days = min(30, len(daily) // 5)
    train = daily.iloc[:-holdout_days].copy()
    test = daily.iloc[-holdout_days:].copy()

    product_label = product_name or category

    # Build and fit model
    model = Prophet(
        holidays=INDIAN_FESTIVALS,
        changepoint_prior_scale=changepoint_prior_scale,
        seasonality_mode=seasonality_mode,
        weekly_seasonality=True,
        yearly_seasonality=True if len(train) >= 365 else False,
        daily_seasonality=False,
        interval_width=0.80,
    )
    model.add_seasonality(name="monthly", period=30.5, fourier_order=5)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(train)

    # Holdout evaluation
    holdout_future = model.make_future_dataframe(
        periods=holdout_days, freq="D"
    )
    holdout_forecast = model.predict(holdout_future)
    holdout_pred = holdout_forecast.tail(holdout_days)["yhat"].clip(lower=0).values
    holdout_actual = test["y"].values

    mae = float(mean_absolute_error(holdout_actual, holdout_pred))
    rmse = float(np.sqrt(mean_squared_error(holdout_actual, holdout_pred)))

    logger.info(
        "forecast_demand [%s]: MAE=%.2f, RMSE=%.2f, holdout=%d days",
        product_label, mae, rmse, holdout_days,
    )

    # Full forecast (train + future)
    future = model.make_future_dataframe(periods=periods, freq="D")
    forecast = model.predict(future)
    forecast["yhat"] = forecast["yhat"].clip(lower=0)
    forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=0)
    forecast["yhat_upper"] = forecast["yhat_upper"].clip(lower=0)

    # Return only future rows
    last_training_date = train["ds"].max()
    result = forecast[forecast["ds"] > last_training_date].copy()
    result = result[["ds", "yhat", "yhat_lower", "yhat_upper"]].reset_index(drop=True)
    result["category"] = category
    result["product_filter"] = product_name or "all"

    # MLflow logging (non-fatal)
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name=f"forecast_{product_label}"):
            mlflow.log_param("category", category)
            mlflow.log_param("product_name", product_name or "all")
            mlflow.log_param("changepoint_prior_scale", changepoint_prior_scale)
            mlflow.log_param("seasonality_mode", seasonality_mode)
            mlflow.log_param("forecast_periods", periods)
            mlflow.log_param("training_rows", len(train))
            mlflow.log_param("holdout_rows", holdout_days)
            mlflow.log_metric("mae", round(mae, 4))
            mlflow.log_metric("rmse", round(rmse, 4))
            try:
                mlflow.prophet.log_model(model, artifact_path="prophet_model")
            except Exception as exc:  # noqa: BLE001
                logger.warning("forecast_demand: could not log Prophet model: %s", exc)
    except Exception as exc:
        logger.warning("MLflow logging failed (non-fatal): %s", exc)

    return result


# ---------------------------------------------------------------------------
# 2. Demand Spike Detection
# ---------------------------------------------------------------------------

def detect_demand_spikes(
    forecast_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    spike_multiplier: float = 1.5,
) -> pd.DataFrame:
    """
    Flag forecast periods where predicted demand exceeds current stock × multiplier.

    A spike is flagged when:
        sum(yhat over period) > current_stock × spike_multiplier

    Args:
        forecast_df:      Output of ``forecast_demand`` with ``yhat`` column.
        inventory_df:     Standardized inventory DataFrame with ``current_stock``,
                          ``product_name``, and ``category``.
        spike_multiplier: Demand-to-stock ratio above which a spike is flagged
                          (default 1.5).

    Returns:
        DataFrame of spike alerts with columns:
        ``['category', 'product_filter', 'total_predicted_demand',
           'current_stock', 'stock_gap', 'spike_severity', 'alert']``

    Raises:
        ValueError: If required columns are missing.
    """
    required_fc = {"category", "yhat"}
    required_inv = {"category", "current_stock"}
    missing_fc = required_fc - set(forecast_df.columns)
    missing_inv = required_inv - set(inventory_df.columns)

    if missing_fc:
        raise ValueError(
            f"detect_demand_spikes: forecast_df missing columns {missing_fc!r}."
        )
    if missing_inv:
        raise ValueError(
            f"detect_demand_spikes: inventory_df missing columns {missing_inv!r}."
        )

    # Aggregate forecast demand per category/product
    group_cols = ["category"]
    if "product_filter" in forecast_df.columns:
        group_cols.append("product_filter")

    fc_agg = (
        forecast_df.groupby(group_cols)["yhat"]
        .sum()
        .reset_index()
        .rename(columns={"yhat": "total_predicted_demand"})
    )

    # Aggregate inventory by category
    inv_agg = (
        inventory_df.groupby("category")["current_stock"]
        .sum()
        .reset_index()
    )

    merged = fc_agg.merge(inv_agg, on="category", how="left")
    merged["current_stock"] = merged["current_stock"].fillna(0)
    merged["spike_threshold"] = merged["current_stock"] * spike_multiplier
    merged["is_spike"] = merged["total_predicted_demand"] > merged["spike_threshold"]

    spikes = merged[merged["is_spike"]].copy()
    spikes["stock_gap"] = (
        spikes["total_predicted_demand"] - spikes["current_stock"]
    ).round(0)
    spikes["spike_severity"] = spikes.apply(
        lambda r: "CRITICAL" if r["total_predicted_demand"] > r["current_stock"] * 3
        else "HIGH" if r["total_predicted_demand"] > r["current_stock"] * 2
        else "MEDIUM",
        axis=1,
    )
    spikes["alert"] = spikes.apply(
        lambda r: (
            f"⚠️ STOCK ALERT [{r['spike_severity']}]: "
            f"Category '{r['category']}' — forecasted demand "
            f"{r['total_predicted_demand']:.0f} units, "
            f"current stock {r['current_stock']:.0f}. "
            f"Gap: {r['stock_gap']:.0f} units. Restock immediately!"
        ),
        axis=1,
    )

    logger.info(
        "detect_demand_spikes: %d spike(s) detected across %d category/products.",
        len(spikes), len(fc_agg)
    )
    return spikes.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Declining Products
# ---------------------------------------------------------------------------

def detect_declining_products(
    sales_df: pd.DataFrame,
    consecutive_months: int = 3,
) -> pd.DataFrame:
    """
    Identify products with consecutive monthly sales decline.

    A product is flagged if its monthly sales quantity has declined for
    ``consecutive_months`` months in a row (ending at the most recent month).

    Args:
        sales_df:             Standardized sales DataFrame.
        consecutive_months:   Number of consecutive declining months required
                              to flag a product (default 3).

    Returns:
        DataFrame of declining products with columns:
        ``['product_name', 'category', 'company', 'decline_months',
           'latest_monthly_qty', 'peak_monthly_qty', 'decline_pct',
           'recommendation']``

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"date", "product_name", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"detect_declining_products: missing columns {missing!r}."
        )

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["period"] = df["date"].dt.to_period("M")

    # Monthly quantity per product
    monthly = (
        df.groupby(["product_name", "period"])["quantity"]
        .sum()
        .reset_index()
        .sort_values(["product_name", "period"])
    )

    results = []
    for product, grp in monthly.groupby("product_name"):
        grp = grp.sort_values("period")
        qty = grp["quantity"].tolist()

        if len(qty) < consecutive_months:
            continue

        # Check last N months for consecutive decline
        recent = qty[-(consecutive_months):]
        is_declining = all(
            recent[i] < recent[i - 1] for i in range(1, len(recent))
        )

        if is_declining:
            latest_qty = recent[-1]
            peak_qty = max(qty)
            decline_pct = (
                (peak_qty - latest_qty) / peak_qty * 100 if peak_qty > 0 else 0.0
            )

            # Get category and company from last available row
            meta = df[df["product_name"] == product].iloc[-1]
            category = meta.get("category", "Unknown")
            company = meta.get("company", "Unknown")

            results.append(
                {
                    "product_name": product,
                    "category": category,
                    "company": company,
                    "decline_months": consecutive_months,
                    "latest_monthly_qty": round(latest_qty, 0),
                    "peak_monthly_qty": round(peak_qty, 0),
                    "decline_pct": round(decline_pct, 1),
                    "recommendation": (
                        f"Sales declined for {consecutive_months} consecutive months "
                        f"({decline_pct:.1f}% from peak). "
                        "Consider: promotion, price review, or discontinue."
                    ),
                }
            )

    result_df = pd.DataFrame(results).sort_values("decline_pct", ascending=False).reset_index(drop=True)
    logger.info(
        "detect_declining_products: %d products flagged with %d-month decline.",
        len(result_df), consecutive_months,
    )
    return result_df


# ---------------------------------------------------------------------------
# 4. Days Coverage (Stockout Prediction)
# ---------------------------------------------------------------------------

def get_days_coverage(
    inventory_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate how many days of stock remain for each SKU based on forecast.

    Uses the average daily forecasted demand (``yhat``) to estimate when
    stock will run out.

    days_coverage = current_stock / avg_daily_demand

    Args:
        inventory_df: Standardized inventory DataFrame with ``product_name``,
                      ``category``, ``current_stock``.
        forecast_df:  Output of ``forecast_demand`` with ``category``, ``yhat``.

    Returns:
        DataFrame with columns:
        ``['product_name', 'category', 'current_stock', 'avg_daily_demand',
           'days_coverage', 'stockout_date', 'status']``
        where ``status`` is one of:
        - ``'CRITICAL'``   : < 7 days coverage
        - ``'WARNING'``    : 7–14 days coverage
        - ``'LOW'``        : 15–30 days coverage
        - ``'ADEQUATE'``   : > 30 days coverage

    Raises:
        ValueError: If required columns are missing.
    """
    required_inv = {"product_name", "category", "current_stock"}
    missing_inv = required_inv - set(inventory_df.columns)
    if missing_inv:
        raise ValueError(
            f"get_days_coverage: inventory_df missing columns {missing_inv!r}."
        )
    if "yhat" not in forecast_df.columns or "category" not in forecast_df.columns:
        raise ValueError(
            "get_days_coverage: forecast_df must contain 'yhat' and 'category'."
        )

    # Average daily demand from forecast per category
    fc_daily = (
        forecast_df.groupby("category")["yhat"]
        .mean()
        .reset_index()
        .rename(columns={"yhat": "avg_daily_demand"})
    )

    inv = inventory_df[["product_name", "category", "current_stock"]].copy()
    inv["current_stock"] = pd.to_numeric(inv["current_stock"], errors="coerce").fillna(0)

    merged = inv.merge(fc_daily, on="category", how="left")
    merged["avg_daily_demand"] = merged["avg_daily_demand"].fillna(0.0)

    def _days(stock: float, demand: float) -> float:
        if demand <= 0:
            return 999.0  # Unknown / no demand
        return round(stock / demand, 1)

    merged["days_coverage"] = merged.apply(
        lambda r: _days(r["current_stock"], r["avg_daily_demand"]), axis=1
    )

    today = pd.Timestamp(datetime.today().date())
    merged["stockout_date"] = merged["days_coverage"].apply(
        lambda d: (today + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d")
        if d < 999 else "N/A"
    )

    def _status(days: float) -> str:
        if days < 7:
            return "CRITICAL"
        elif days < 15:
            return "WARNING"
        elif days < 30:
            return "LOW"
        else:
            return "ADEQUATE"

    merged["status"] = merged["days_coverage"].apply(_status)

    result = merged[
        ["product_name", "category", "current_stock",
         "avg_daily_demand", "days_coverage", "stockout_date", "status"]
    ].sort_values("days_coverage").reset_index(drop=True)

    logger.info(
        "get_days_coverage: CRITICAL=%d, WARNING=%d, LOW=%d, ADEQUATE=%d",
        (result["status"] == "CRITICAL").sum(),
        (result["status"] == "WARNING").sum(),
        (result["status"] == "LOW").sum(),
        (result["status"] == "ADEQUATE").sum(),
    )
    return result
