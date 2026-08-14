"""
engine/analytics.py
===================
Core business analytics functions for the Wholesale BI System.

Provides:
- Dead stock detection with capital-blocked calculation and action suggestions.
- Outstanding payment tracking with risk scoring and WhatsApp collection reminders.
- GST-aware margin calculation per product / company / category.
- Town-wise (area) sales ranking.
- Month-by-month revenue trend analysis.
- Category × month heatmap pivot table.

All functions accept already-standardized DataFrames (output of data_cleaner.py).

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GST rates by category
# ---------------------------------------------------------------------------

GST_RATES: dict[str, float] = {
    "Snacks": 0.12,
    "Beverages": 0.12,
    "Personal Care": 0.18,
    "FMCG": 0.05,
    "Dairy": 0.05,
    "Household": 0.12,
    "Stationery": 0.12,
    "Electronics Accessories": 0.12,
    "Clothing Accessories": 0.12,
    "Agricultural": 0.12,
}
DEFAULT_GST_RATE: float = 0.12

# Dead stock thresholds (days since last sale)
DEAD_THRESHOLD: int = 60
SLOW_THRESHOLD: int = 30

# Payment risk thresholds (days overdue)
HIGH_OVERDUE: int = 90
MEDIUM_OVERDUE: int = 45
NPA_THRESHOLD: int = 120  # Non-Performing Asset — practically unrecoverable


# ---------------------------------------------------------------------------
# 1. Dead Stock Detection
# ---------------------------------------------------------------------------

def detect_dead_stock(
    inventory_df: pd.DataFrame,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    Identify slow-moving and dead inventory items.

    Classifies each SKU based on days since last sale:
    - ACTIVE  : ≤ 30 days
    - SLOW    : 31–60 days
    - DEAD    : > 60 days

    Added columns:
    - ``days_unsold``           : days since last_sale_date (NaT → 999)
    - ``stock_status``          : 'ACTIVE' | 'SLOW' | 'DEAD'
    - ``capital_blocked``       : current_stock × purchase_price
    - ``suggested_discount_pct``: 0 / 10 / 20 for ACTIVE / SLOW / DEAD
    - ``recommended_action``    : plain-English action string

    Args:
        inventory_df: Standardized inventory DataFrame containing at minimum
            ``last_sale_date``, ``current_stock``, and ``purchase_price``.
        reference_date: The "today" reference for age calculation. Defaults
            to the current system date.

    Returns:
        Copy of ``inventory_df`` with the five new columns appended.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"last_sale_date", "current_stock", "purchase_price"}
    missing = required - set(inventory_df.columns)
    if missing:
        raise ValueError(
            f"detect_dead_stock: missing columns {missing!r} in inventory_df."
        )

    ref = pd.Timestamp(reference_date or datetime.today().date())
    df = inventory_df.copy()

    last_sale = pd.to_datetime(df["last_sale_date"], errors="coerce")
    days_unsold = (ref - last_sale).dt.days.fillna(999).astype(int)
    df["days_unsold"] = days_unsold

    # Classification
    conditions = [
        days_unsold <= SLOW_THRESHOLD,
        (days_unsold > SLOW_THRESHOLD) & (days_unsold <= DEAD_THRESHOLD),
    ]
    choices = ["ACTIVE", "SLOW"]
    df["stock_status"] = np.select(conditions, choices, default="DEAD")

    # Capital blocked
    df["capital_blocked"] = (
        df["current_stock"].fillna(0) * df["purchase_price"].fillna(0)
    ).round(2)

    # Suggested discount
    discount_map = {"ACTIVE": 0, "SLOW": 10, "DEAD": 20}
    df["suggested_discount_pct"] = df["stock_status"].map(discount_map)

    # Recommended action
    def _action(row: pd.Series) -> str:
        status = row["stock_status"]
        cap = row["capital_blocked"]
        days = row["days_unsold"]
        if status == "ACTIVE":
            return "No action needed — stock moving well."
        elif status == "SLOW":
            return (
                f"Monitor closely. Offer 10% discount to push {row.get('product_name', 'item')}. "
                f"₹{cap:,.0f} capital at risk after {days} days without sale."
            )
        else:  # DEAD
            return (
                f"URGENT: {row.get('product_name', 'item')} unsold for {days} days. "
                f"₹{cap:,.0f} blocked. Offer 20% discount or return to supplier."
            )

    df["recommended_action"] = df.apply(_action, axis=1)

    logger.info(
        "detect_dead_stock: ACTIVE=%d, SLOW=%d, DEAD=%d",
        (df["stock_status"] == "ACTIVE").sum(),
        (df["stock_status"] == "SLOW").sum(),
        (df["stock_status"] == "DEAD").sum(),
    )
    return df


# ---------------------------------------------------------------------------
# 2. Outstanding Payments
# ---------------------------------------------------------------------------

def get_outstanding_payments(
    sales_df: pd.DataFrame,
    customer_df: pd.DataFrame,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    Build an outstanding-payment report with risk levels and WhatsApp messages.

    Filters ``sales_df`` for unpaid / partial / overdue transactions, merges
    customer contact info, then computes:

    Added columns:
    - ``days_overdue``    : days since payment_due_date (negative = not yet due)
    - ``risk_level``      : 'HIGH' (>90d) | 'MEDIUM' (45–90d) | 'LOW' (<45d)
    - ``urgency_score``   : weighted score from scoring module formula
    - ``whatsapp_message``: ready-to-send Hindi/English collection reminder

    Args:
        sales_df: Standardized sales DataFrame.
        customer_df: Standardized customer DataFrame for customer metadata.
        reference_date: Reference "today" for overdue calculation. Defaults
            to the current system date.

    Returns:
        DataFrame of outstanding transactions with the four new columns.

    Raises:
        ValueError: If required columns are missing from either DataFrame.
    """
    required_sales = {"payment_status", "payment_due_date", "customer_name",
                      "invoice_no", "sale_price", "quantity"}
    missing_s = required_sales - set(sales_df.columns)
    if missing_s:
        raise ValueError(
            f"get_outstanding_payments: missing sales columns {missing_s!r}."
        )

    ref = pd.Timestamp(reference_date or datetime.today().date())
    df = sales_df.copy()

    # Filter to unpaid / overdue / partial
    df["payment_status"] = df["payment_status"].astype(str).str.upper()
    outstanding_mask = df["payment_status"].isin({"UNPAID", "OVERDUE", "PARTIAL"})
    outstanding = df[outstanding_mask].copy()

    if outstanding.empty:
        logger.info("get_outstanding_payments: no outstanding transactions found.")
        outstanding["days_overdue"] = pd.Series(dtype=int)
        outstanding["npa_status"] = pd.Series(dtype=str)
        outstanding["invoice_amount"] = pd.Series(dtype=float)
        outstanding["risk_level"] = pd.Series(dtype=str)
        outstanding["urgency_score"] = pd.Series(dtype=float)
        outstanding["whatsapp_message"] = pd.Series(dtype=str)
        outstanding["outstanding_amount"] = pd.Series(dtype=float)
        outstanding["credit_limit"] = pd.Series(dtype=float)
        outstanding["area"] = pd.Series(dtype=str)
        return outstanding

    # Days overdue — cap at 999 to avoid synthetic data inflating to 800+ days
    due = pd.to_datetime(outstanding["payment_due_date"], errors="coerce")
    raw_days = (ref - due).dt.days.fillna(0).astype(int)
    outstanding["days_overdue"] = raw_days.clip(lower=0)  # no negative overdue

    # NPA classification: >365 days is practically a bad debt
    outstanding["npa_status"] = outstanding["days_overdue"].apply(
        lambda d: "NPA" if d > NPA_THRESHOLD else "ACTIVE"
    )

    # Invoice value (sale_price × quantity)
    outstanding["invoice_amount"] = (
        outstanding["sale_price"].fillna(0) * outstanding["quantity"].fillna(1)
    ).round(2)

    # Risk level
    def _risk(days: int) -> str:
        if days > HIGH_OVERDUE:
            return "HIGH"
        elif days >= MEDIUM_OVERDUE:
            return "MEDIUM"
        else:
            return "LOW"

    outstanding["risk_level"] = outstanding["days_overdue"].apply(_risk)

    # Urgency score using the system formula
    max_amount = outstanding["invoice_amount"].max() or 1.0
    max_days = outstanding["days_overdue"].clip(lower=0).max() or 1.0

    def _urgency(row: pd.Series) -> float:
        days_factor = min(row["days_overdue"] / 90.0, 1.0) if row["days_overdue"] > 0 else 0.0
        amount_factor = min(row["invoice_amount"] / max_amount, 1.0)
        trend_factor = 1.0 if row["risk_level"] == "HIGH" else (
            0.5 if row["risk_level"] == "MEDIUM" else 0.2
        )
        return round(
            days_factor * 0.4 + amount_factor * 0.4 + trend_factor * 0.2, 4
        )

    outstanding["urgency_score"] = outstanding.apply(_urgency, axis=1)

    # Merge customer info if available
    if "area" in customer_df.columns and "customer_name" in customer_df.columns:
        cust_cols = ["customer_name", "area", "credit_limit", "outstanding_amount"]
        cust_cols = [c for c in cust_cols if c in customer_df.columns]
        cust_subset = customer_df[cust_cols].drop_duplicates("customer_name")
        outstanding = outstanding.merge(
            cust_subset, on="customer_name", how="left", suffixes=("", "_cust")
        )

    # ── Multi-bill WhatsApp message (grouped by customer) ────────────────────
    # Build a customer-level summary with all invoices listed
    def _build_multibill_message(group: pd.DataFrame) -> str:
        name = group.name
        area = group.get("area", group.get("customer_area", pd.Series([""]*len(group)))).iloc[0]
        area_str = f" ({area})" if area and str(area).strip() else ""
        total_amt = group["invoice_amount"].sum()
        risk = group["risk_level"].iloc[0]  # highest risk (sorted desc)
        num_bills = len(group)

        # Build bill list (max 5 shown)
        bill_lines = []
        for _, row in group.head(5).iterrows():
            bill_lines.append(
                f"  • {row['invoice_no']}: ₹{row['invoice_amount']:,.0f} ({int(row['days_overdue'])} din)"
            )
        if num_bills > 5:
            bill_lines.append(f"  • ...aur {num_bills - 5} aur bills")
        bills_str = "\n".join(bill_lines)

        if risk == "HIGH":
            return (
                f"🚨 *URGENT Payment Reminder*\n\n"
                f"Namaskar *{name}*{area_str}! 🙏\n\n"
                f"Aapka total outstanding: *₹{total_amt:,.0f}* ({num_bills} bills)\n\n"
                f"{bills_str}\n\n"
                f"Kripya aaj hi payment karein ya hamare saath contact karein.\n"
                f"📞 Please respond immediately."
            )
        elif risk == "MEDIUM":
            return (
                f"⚠️ *Payment Reminder*\n\n"
                f"Namaskar *{name}*{area_str}! 🙏\n\n"
                f"Aapka total outstanding: *₹{total_amt:,.0f}* ({num_bills} bills)\n\n"
                f"{bills_str}\n\n"
                f"Kripya jald payment ki vyavastha karein. Dhanyawaad! 🙏"
            )
        else:
            return (
                f"📋 *Payment Reminder*\n\n"
                f"Dear *{name}*{area_str},\n\n"
                f"Outstanding amount: *₹{total_amt:,.0f}* ({num_bills} bills)\n\n"
                f"{bills_str}\n\n"
                f"Please arrange payment at your convenience. Thank you! 🙏"
            )

    # Assign the customer-level grouped message to every row of that customer
    outstanding = outstanding.sort_values("urgency_score", ascending=False)
    cust_messages = (
        outstanding.groupby("customer_name", sort=False)
        .apply(_build_multibill_message, include_groups=False)
        .reset_index()
        .rename(columns={0: "whatsapp_message"})
    )
    outstanding = outstanding.merge(cust_messages, on="customer_name", how="left")

    logger.info(
        "get_outstanding_payments: HIGH=%d, MEDIUM=%d, LOW=%d, NPA=%d",
        (outstanding["risk_level"] == "HIGH").sum(),
        (outstanding["risk_level"] == "MEDIUM").sum(),
        (outstanding["risk_level"] == "LOW").sum(),
        (outstanding["npa_status"] == "NPA").sum(),
    )
    return outstanding.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2b. Dead Retailer / Churn Detection
# ---------------------------------------------------------------------------

def detect_churned_retailers(
    sales_df: pd.DataFrame,
    churn_days: int = 45,
    min_monthly_orders: int = 2,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    Detect retailers who were previously active but have stopped ordering.

    A customer is CHURNED if they had >= min_monthly_orders/month in the
    prior 6-month baseline but placed ZERO orders in the last churn_days days.
    AT RISK if order frequency dropped >50%.

    Args:
        sales_df: Standardized sales DataFrame.
        churn_days: Days of silence to flag as churned (default 45).
        min_monthly_orders: Min monthly frequency to be considered active (default 2).
        reference_date: Reference date. Defaults to today.

    Returns:
        DataFrame with churn_status, days_since_order, avg_monthly_revenue_before,
        and churn_alert message. Only CHURNED and AT RISK rows returned.
    """
    required = {"customer_name", "date", "sale_price", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(f"detect_churned_retailers: missing columns {missing!r}.")

    ref = pd.Timestamp(reference_date or datetime.today().date())
    cutoff = ref - pd.Timedelta(days=churn_days)
    baseline_start = ref - pd.Timedelta(days=churn_days + 180)

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["revenue"] = df["sale_price"].fillna(0) * df["quantity"].fillna(1)

    baseline = df[(df["date"] >= baseline_start) & (df["date"] < cutoff)]
    recent   = df[df["date"] >= cutoff]

    if baseline.empty:
        logger.warning("detect_churned_retailers: insufficient baseline data.")
        return pd.DataFrame()

    # Build aggregation dict dynamically based on available columns
    _baseline_agg: dict[str, tuple] = {
        "baseline_orders": ("invoice_no", "nunique") if "invoice_no" in baseline.columns else ("date", "count"),
        "baseline_revenue": ("revenue", "sum"),
    }
    if "customer_area" in baseline.columns:
        _baseline_agg["customer_area"] = ("customer_area", "first")

    baseline_stats = (
        baseline.groupby("customer_name", as_index=False)
        .agg(**_baseline_agg)
    )
    baseline_stats["avg_monthly_orders"]  = (baseline_stats["baseline_orders"] / 6).round(1)
    baseline_stats["avg_monthly_revenue"] = (baseline_stats["baseline_revenue"] / 6).round(0)

    active_baseline = baseline_stats[
        baseline_stats["avg_monthly_orders"] >= min_monthly_orders
    ].copy()

    if active_baseline.empty:
        return pd.DataFrame()

    _recent_col, _recent_func = ("invoice_no", "nunique") if "invoice_no" in recent.columns else ("date", "count")
    recent_counts = (
        recent.groupby("customer_name", as_index=False)
        .agg(recent_orders=(_recent_col, _recent_func))
    )

    merged = active_baseline.merge(recent_counts, on="customer_name", how="left")
    merged["recent_orders"] = merged["recent_orders"].fillna(0).astype(int)

    last_orders = (
        df.groupby("customer_name")["date"].max()
        .reset_index().rename(columns={"date": "last_order_date"})
    )
    merged = merged.merge(last_orders, on="customer_name", how="left")
    merged["days_since_order"] = (ref - merged["last_order_date"]).dt.days.fillna(999).astype(int)

    def _status(row: pd.Series) -> str:
        if row["recent_orders"] == 0:
            return "CHURNED"
        elif row["recent_orders"] < row["avg_monthly_orders"] * 0.5:
            return "AT RISK"
        return "STABLE"

    merged["churn_status"] = merged.apply(_status, axis=1)

    def _alert(row: pd.Series) -> str:
        name = row["customer_name"]
        area = row.get("customer_area", "")
        days = int(row["days_since_order"])
        rev  = row["avg_monthly_revenue"]
        if row["churn_status"] == "CHURNED":
            return (
                f"🔴 [CHURN ALERT] {name} ({area}) has not ordered in {days} days. "
                f"Was averaging ₹{rev:,.0f}/month. Competitor may have captured this counter."
            )
        elif row["churn_status"] == "AT RISK":
            return (
                f"⚠️ [AT RISK] {name} ({area}) order frequency dropped >50% in last {churn_days} days. "
                f"Visit or call immediately to retain."
            )
        return ""

    merged["churn_alert"] = merged.apply(_alert, axis=1)

    result = (
        merged[merged["churn_status"].isin(["CHURNED", "AT RISK"])]
        [["customer_name", "customer_area", "last_order_date", "days_since_order",
          "avg_monthly_orders", "avg_monthly_revenue", "recent_orders",
          "churn_status", "churn_alert"]]
        .rename(columns={
            "avg_monthly_orders":  "avg_monthly_orders_before",
            "avg_monthly_revenue": "avg_monthly_revenue_before",
        })
        .sort_values("days_since_order", ascending=False)
        .reset_index(drop=True)
    )

    logger.info(
        "detect_churned_retailers: CHURNED=%d, AT_RISK=%d",
        (result["churn_status"] == "CHURNED").sum(),
        (result["churn_status"] == "AT RISK").sum(),
    )
    return result


# ---------------------------------------------------------------------------
# 3. GST-Aware Margin Calculation
# ---------------------------------------------------------------------------

def calculate_margins(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate GST-inclusive and real (ex-GST) margins per line item.

    Margin logic:
        sale_price_ex_gst  = sale_price / (1 + gst_rate)
        real_margin        = (sale_price_ex_gst - purchase_price) / purchase_price × 100
        gross_margin_pct   = (sale_price - purchase_price) / purchase_price × 100

    Added columns:
    - ``gst_rate``           : applicable GST rate for the category (decimal)
    - ``gst_amount``         : GST portion of sale_price per unit
    - ``sale_price_ex_gst``  : sale_price excluding GST
    - ``gross_margin_pct``   : margin before GST adjustment
    - ``real_margin_pct``    : true margin after removing GST from revenue
    - ``profit_per_unit``    : absolute profit per unit (ex-GST)
    - ``total_profit``       : profit_per_unit × quantity

    Returns a summary pivot with columns:
    ``['grouping', 'product_name', 'category', 'company',
       'avg_gross_margin_pct', 'avg_real_margin_pct', 'total_profit',
       'total_revenue', 'total_quantity']``

    Args:
        sales_df: Standardized sales DataFrame.

    Returns:
        Summary DataFrame with margins grouped by product, company, and category.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"category", "sale_price", "purchase_price", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"calculate_margins: missing columns {missing!r} in sales_df."
        )

    df = sales_df.copy()
    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).clip(lower=1)
    df["discount_pct"] = pd.to_numeric(
        df.get("discount_pct", pd.Series(0, index=df.index)), errors="coerce"
    ).fillna(0)

    # Apply discount to sale_price
    df["effective_sale_price"] = df["sale_price"] * (1 - df["discount_pct"] / 100)

    # GST lookup
    df["gst_rate"] = df["category"].map(GST_RATES).fillna(DEFAULT_GST_RATE)
    df["sale_price_ex_gst"] = df["effective_sale_price"] / (1 + df["gst_rate"])
    df["gst_amount"] = df["effective_sale_price"] - df["sale_price_ex_gst"]

    # Margins — avoid division by zero
    safe_purchase = df["purchase_price"].replace(0, np.nan)
    df["gross_margin_pct"] = (
        (df["effective_sale_price"] - df["purchase_price"]) / safe_purchase * 100
    ).round(2)
    df["real_margin_pct"] = (
        (df["sale_price_ex_gst"] - df["purchase_price"]) / safe_purchase * 100
    ).round(2)
    df["profit_per_unit"] = (df["sale_price_ex_gst"] - df["purchase_price"]).round(2)
    df["total_profit"] = (df["profit_per_unit"] * df["quantity"]).round(2)
    df["total_revenue"] = (df["effective_sale_price"] * df["quantity"]).round(2)

    # Group by product + company + category
    grp = (
        df.groupby(["product_name", "company", "category"], dropna=False)
        .agg(
            avg_gross_margin_pct=("gross_margin_pct", "mean"),
            avg_real_margin_pct=("real_margin_pct", "mean"),
            total_profit=("total_profit", "sum"),
            total_revenue=("total_revenue", "sum"),
            total_quantity=("quantity", "sum"),
        )
        .round(2)
        .reset_index()
        .sort_values("avg_real_margin_pct", ascending=False)
    )

    logger.info(
        "calculate_margins: processed %d line items across %d products.",
        len(df), grp["product_name"].nunique()
    )
    return grp


# ---------------------------------------------------------------------------
# 4. Area Sales Ranking
# ---------------------------------------------------------------------------

def area_sales_ranking(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute town-wise revenue and margin breakdown, ranked by total revenue.

    Args:
        sales_df: Standardized sales DataFrame.

    Returns:
        DataFrame with columns:
        ``['rank', 'customer_area', 'total_revenue', 'total_quantity',
           'total_profit', 'avg_real_margin_pct', 'num_transactions',
           'unique_customers', 'unique_products']``
        sorted by ``total_revenue`` descending.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"customer_area", "sale_price", "purchase_price", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"area_sales_ranking: missing columns {missing!r} in sales_df."
        )

    df = sales_df.copy()
    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).clip(lower=1)
    df["discount_pct"] = pd.to_numeric(
        df.get("discount_pct", pd.Series(0, index=df.index)), errors="coerce"
    ).fillna(0)

    # GST-aware calculations
    df["gst_rate"] = df.get("category", pd.Series("", index=df.index)).map(
        GST_RATES
    ).fillna(DEFAULT_GST_RATE)
    df["effective_sale_price"] = df["sale_price"] * (1 - df["discount_pct"] / 100)
    df["sale_price_ex_gst"] = df["effective_sale_price"] / (1 + df["gst_rate"])
    safe_purchase = df["purchase_price"].replace(0, np.nan)
    df["real_margin_pct"] = (
        (df["sale_price_ex_gst"] - df["purchase_price"]) / safe_purchase * 100
    )
    df["total_revenue_line"] = df["effective_sale_price"] * df["quantity"]
    df["total_profit_line"] = (
        (df["sale_price_ex_gst"] - df["purchase_price"]) * df["quantity"]
    )

    agg_dict: dict[str, tuple] = {
        "total_revenue": ("total_revenue_line", "sum"),
        "total_quantity": ("quantity", "sum"),
        "total_profit": ("total_profit_line", "sum"),
        "avg_real_margin_pct": ("real_margin_pct", "mean"),
        "num_transactions": ("invoice_no", "count") if "invoice_no" in df.columns
                           else ("total_revenue_line", "count"),
    }

    if "customer_name" in df.columns:
        agg_dict["unique_customers"] = ("customer_name", "nunique")
    if "product_name" in df.columns:
        agg_dict["unique_products"] = ("product_name", "nunique")

    ranked = (
        df.groupby("customer_area", dropna=False)
        .agg(**agg_dict)
        .round(2)
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )
    ranked.insert(0, "rank", range(1, len(ranked) + 1))

    logger.info("area_sales_ranking: %d areas processed.", len(ranked))
    return ranked


# ---------------------------------------------------------------------------
# 5. Monthly Revenue Trend
# ---------------------------------------------------------------------------

def monthly_revenue_trend(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute month-by-month revenue, quantity sold, and average real margin.

    Args:
        sales_df: Standardized sales DataFrame with a ``date`` column.

    Returns:
        DataFrame indexed by year-month with columns:
        ``['year_month', 'total_revenue', 'total_quantity', 'avg_real_margin_pct',
           'total_profit', 'num_transactions', 'mom_revenue_change_pct']``
        sorted by ``year_month`` ascending.
        ``mom_revenue_change_pct`` is the month-over-month percentage change
        in total revenue.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"date", "sale_price", "purchase_price", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"monthly_revenue_trend: missing columns {missing!r} in sales_df."
        )

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).clip(lower=1)
    df["discount_pct"] = pd.to_numeric(
        df.get("discount_pct", pd.Series(0, index=df.index)), errors="coerce"
    ).fillna(0)

    df["gst_rate"] = df.get("category", pd.Series("", index=df.index)).map(
        GST_RATES
    ).fillna(DEFAULT_GST_RATE)
    df["effective_sale_price"] = df["sale_price"] * (1 - df["discount_pct"] / 100)
    df["sale_price_ex_gst"] = df["effective_sale_price"] / (1 + df["gst_rate"])
    safe_purchase = df["purchase_price"].replace(0, np.nan)
    df["real_margin_pct"] = (
        (df["sale_price_ex_gst"] - df["purchase_price"]) / safe_purchase * 100
    )
    df["line_revenue"] = df["effective_sale_price"] * df["quantity"]
    df["line_profit"] = (
        (df["sale_price_ex_gst"] - df["purchase_price"]) * df["quantity"]
    )

    df["year_month"] = df["date"].dt.to_period("M")

    agg = (
        df.groupby("year_month")
        .agg(
            total_revenue=("line_revenue", "sum"),
            total_quantity=("quantity", "sum"),
            avg_real_margin_pct=("real_margin_pct", "mean"),
            total_profit=("line_profit", "sum"),
            num_transactions=("line_revenue", "count"),
        )
        .round(2)
        .reset_index()
        .sort_values("year_month")
    )

    agg["mom_revenue_change_pct"] = (
        agg["total_revenue"].pct_change() * 100
    ).round(2)

    # Convert Period to string for JSON-serialisability
    agg["year_month"] = agg["year_month"].astype(str)

    logger.info("monthly_revenue_trend: %d months of data.", len(agg))
    return agg


# ---------------------------------------------------------------------------
# 6. Category × Month Heatmap
# ---------------------------------------------------------------------------

def category_month_heatmap(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a pivot table of total revenue by category (rows) × month (columns).

    Designed to feed a seaborn/plotly heatmap directly.

    Args:
        sales_df: Standardized sales DataFrame with ``date`` and ``category``
            columns.

    Returns:
        Pivot DataFrame where:
        - Index: category names
        - Columns: 'YYYY-MM' strings sorted chronologically
        - Values: total revenue (sale_price × quantity, discount-adjusted)
        Missing combinations are filled with 0.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"date", "category", "sale_price", "quantity"}
    missing = required - set(sales_df.columns)
    if missing:
        raise ValueError(
            f"category_month_heatmap: missing columns {missing!r} in sales_df."
        )

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).clip(lower=1)
    df["discount_pct"] = pd.to_numeric(
        df.get("discount_pct", pd.Series(0, index=df.index)), errors="coerce"
    ).fillna(0)

    df["effective_sale_price"] = df["sale_price"] * (1 - df["discount_pct"] / 100)
    df["line_revenue"] = df["effective_sale_price"] * df["quantity"]
    df["year_month"] = df["date"].dt.to_period("M").astype(str)

    pivot = (
        df.groupby(["category", "year_month"])["line_revenue"]
        .sum()
        .round(2)
        .unstack(fill_value=0)
    )

    # Sort columns chronologically
    pivot = pivot[sorted(pivot.columns)]

    logger.info(
        "category_month_heatmap: %d categories × %d months.",
        len(pivot), len(pivot.columns)
    )
    return pivot
