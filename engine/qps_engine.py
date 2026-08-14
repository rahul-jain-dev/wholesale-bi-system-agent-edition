"""
engine/qps_engine.py
====================
Quantity Purchase Scheme (QPS) Tracker for the Wholesale BI System.

Handles:
- Scheme registry CRUD (load/save from JSON)
- Claim calculation: cross-references active schemes against sales data
  to compute how much each FMCG company owes the distributor for
  promotional free-goods schemes (e.g., "Buy 5 Get 1 Free").

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default path for scheme persistence
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
SCHEMES_FILE = os.path.join(_DATA_DIR, "active_schemes.json")

# ---------------------------------------------------------------------------
# 1. Scheme Data Structure
# ---------------------------------------------------------------------------

SCHEME_COLUMNS = [
    "scheme_name",
    "company",
    "buy_product",
    "min_qty",
    "free_product",
    "free_qty",
    "start_date",
    "end_date",
    "town_filter",
    "is_active",
]


def empty_scheme_df() -> pd.DataFrame:
    """Return an empty DataFrame with the correct scheme columns and types."""
    return pd.DataFrame(
        columns=SCHEME_COLUMNS,
    ).astype(
        {
            "scheme_name": str,
            "company": str,
            "buy_product": str,
            "min_qty": int,
            "free_product": str,
            "free_qty": int,
            "start_date": str,
            "end_date": str,
            "town_filter": str,
            "is_active": bool,
        }
    )


def default_scheme_row() -> dict:
    """Return a single default row for new scheme entry."""
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "scheme_name": "New Scheme",
        "company": "",
        "buy_product": "",
        "min_qty": 5,
        "free_product": "",
        "free_qty": 1,
        "start_date": today,
        "end_date": today,
        "town_filter": "",
        "is_active": True,
    }


# ---------------------------------------------------------------------------
# 2. Scheme Persistence (JSON)
# ---------------------------------------------------------------------------


def load_schemes(path: Optional[str] = None) -> pd.DataFrame:
    """
    Load saved schemes from a JSON file.

    Args:
        path: Path to the JSON file. Defaults to ``data/active_schemes.json``.

    Returns:
        DataFrame of schemes. Empty DataFrame with correct columns if file
        doesn't exist or is empty.
    """
    path = path or SCHEMES_FILE
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                df = pd.DataFrame(data)
                # Ensure all expected columns exist
                for col in SCHEME_COLUMNS:
                    if col not in df.columns:
                        df[col] = "" if col != "is_active" else True
                return df[SCHEME_COLUMNS]
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning("load_schemes: failed to load %s: %s", path, exc)

    return empty_scheme_df()


def save_schemes(schemes_df: pd.DataFrame, path: Optional[str] = None) -> None:
    """
    Save schemes DataFrame to JSON file.

    Args:
        schemes_df: DataFrame with scheme data.
        path:       Output file path. Defaults to ``data/active_schemes.json``.
    """
    path = path or SCHEMES_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Clean up before saving
    df = schemes_df.copy()
    for col in ["start_date", "end_date"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    records = df.to_dict(orient="records")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    logger.info("save_schemes: saved %d schemes to %s", len(records), path)


# ---------------------------------------------------------------------------
# 3. Claim Calculation Engine
# ---------------------------------------------------------------------------


def calculate_claims(
    sales_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    schemes_df: pd.DataFrame,
) -> dict:
    """
    Cross-reference active schemes against sales data to calculate claims.

    Algorithm:
        For each active scheme:
        1. Filter sales by date range, product match, and optional town.
        2. Group by invoice to find total quantity of buy_product per invoice.
        3. Calculate scheme cycles: qty // min_qty
        4. Calculate free items given: cycles × free_qty
        5. Value each free item at purchase_price from inventory.
        6. Aggregate total claim per company.

    Args:
        sales_df:     Standardized sales DataFrame.
        inventory_df: Standardized inventory DataFrame (for purchase_price).
        schemes_df:   Active schemes from the registry.

    Returns:
        dict with keys:
        - ``total_claim``: float — Grand total of all claims (₹).
        - ``by_company``:  DataFrame — Claim amount grouped by company.
        - ``by_scheme``:   DataFrame — Claim amount grouped by scheme.
        - ``details``:     DataFrame — Invoice-level detail of every claim.
        - ``n_schemes``:   int — Number of active schemes processed.
        - ``n_invoices``:  int — Number of qualifying invoices found.
    """
    result = {
        "total_claim": 0.0,
        "by_company": pd.DataFrame(columns=["company", "claim_amount", "n_invoices", "free_units"]),
        "by_scheme": pd.DataFrame(columns=["scheme_name", "company", "claim_amount", "n_invoices", "free_units"]),
        "details": pd.DataFrame(columns=[
            "scheme_name", "company", "invoice_no", "date", "customer_name",
            "buy_product", "qty_sold", "scheme_cycles", "free_units",
            "free_product", "unit_cost", "claim_value",
        ]),
        "n_schemes": 0,
        "n_invoices": 0,
    }

    # Validate inputs
    if schemes_df.empty:
        logger.info("calculate_claims: no schemes registered.")
        return result

    if sales_df.empty:
        logger.info("calculate_claims: no sales data.")
        return result

    # Filter to active schemes only
    active = schemes_df[schemes_df.get("is_active", pd.Series(True, index=schemes_df.index)) == True].copy()  # noqa: E712
    if active.empty:
        logger.info("calculate_claims: no active schemes.")
        return result

    result["n_schemes"] = len(active)

    # Prepare sales data
    sales = sales_df.copy()
    sales["date"] = pd.to_datetime(sales["date"], errors="coerce")
    sales["quantity"] = pd.to_numeric(sales["quantity"], errors="coerce").fillna(0)

    # Build purchase price lookup from inventory
    price_lookup = {}
    if not inventory_df.empty and "product_name" in inventory_df.columns:
        # Simple dict lookup
        price_df = inventory_df[["product_name", "purchase_price"]].drop_duplicates("product_name")
        price_df["purchase_price"] = pd.to_numeric(price_df["purchase_price"], errors="coerce").fillna(0)
        price_lookup = dict(zip(
            price_df["product_name"].str.strip().str.lower(),
            price_df["purchase_price"],
        ))

    all_details = []

    for _, scheme in active.iterrows():
        scheme_name = str(scheme.get("scheme_name", "Unnamed"))
        company = str(scheme.get("company", "Unknown"))
        buy_product = str(scheme.get("buy_product", "")).strip()
        min_qty = int(scheme.get("min_qty", 1))
        free_product = str(scheme.get("free_product", "")).strip()
        free_qty = int(scheme.get("free_qty", 1))
        town_filter = str(scheme.get("town_filter", "")).strip()

        if not buy_product or min_qty <= 0:
            continue

        # Parse date range
        try:
            start_dt = pd.to_datetime(scheme.get("start_date"), errors="coerce")
            end_dt = pd.to_datetime(scheme.get("end_date"), errors="coerce")
        except Exception:
            start_dt, end_dt = pd.NaT, pd.NaT

        # Filter sales for this scheme
        mask = sales["product_name"].str.strip().str.lower() == buy_product.lower()

        if pd.notna(start_dt):
            mask &= sales["date"] >= start_dt
        if pd.notna(end_dt):
            mask &= sales["date"] <= end_dt

        # Optional town filter
        if town_filter:
            area_col = "customer_area" if "customer_area" in sales.columns else "area"
            if area_col in sales.columns:
                mask &= sales[area_col].str.strip().str.lower() == town_filter.lower()

        filtered = sales[mask].copy()
        if filtered.empty:
            continue

        # Get purchase price for the FREE product (what it costs the distributor)
        free_key = (free_product or buy_product).strip().lower()
        unit_cost = price_lookup.get(free_key, 0.0)

        # If no inventory price, try the sale_price from sales as approximation
        if unit_cost == 0.0 and "sale_price" in filtered.columns:
            unit_cost = pd.to_numeric(filtered["sale_price"], errors="coerce").median()
            unit_cost = float(unit_cost) if pd.notna(unit_cost) else 0.0

        # Group by invoice to get total quantity per invoice
        invoice_col = "invoice_no" if "invoice_no" in filtered.columns else None
        if invoice_col:
            grouped = filtered.groupby(["invoice_no"]).agg(
                date=("date", "first"),
                customer_name=("customer_name", "first") if "customer_name" in filtered.columns else ("date", "first"),
                qty_sold=("quantity", "sum"),
            ).reset_index()
        else:
            # No invoice column — group by date + customer
            group_cols = ["date"]
            if "customer_name" in filtered.columns:
                group_cols.append("customer_name")
            grouped = filtered.groupby(group_cols).agg(
                qty_sold=("quantity", "sum"),
            ).reset_index()
            grouped["invoice_no"] = "N/A"
            if "customer_name" not in grouped.columns:
                grouped["customer_name"] = "Unknown"

        # Calculate scheme cycles and free units per invoice
        grouped["scheme_cycles"] = (grouped["qty_sold"] // min_qty).astype(int)
        grouped = grouped[grouped["scheme_cycles"] > 0]

        if grouped.empty:
            continue

        grouped["free_units"] = grouped["scheme_cycles"] * free_qty
        grouped["unit_cost"] = unit_cost
        grouped["claim_value"] = grouped["free_units"] * unit_cost
        grouped["scheme_name"] = scheme_name
        grouped["company"] = company
        grouped["buy_product"] = buy_product
        grouped["free_product"] = free_product or buy_product

        all_details.append(grouped)

    # Combine all scheme results
    if all_details:
        details = pd.concat(all_details, ignore_index=True)

        # Ensure correct column order
        detail_cols = [
            "scheme_name", "company", "invoice_no", "date", "customer_name",
            "buy_product", "qty_sold", "scheme_cycles", "free_units",
            "free_product", "unit_cost", "claim_value",
        ]
        for col in detail_cols:
            if col not in details.columns:
                details[col] = ""
        details = details[detail_cols]

        # Aggregations
        by_company = (
            details.groupby("company")
            .agg(
                claim_amount=("claim_value", "sum"),
                n_invoices=("invoice_no", "nunique"),
                free_units=("free_units", "sum"),
            )
            .reset_index()
            .sort_values("claim_amount", ascending=False)
        )

        by_scheme = (
            details.groupby(["scheme_name", "company"])
            .agg(
                claim_amount=("claim_value", "sum"),
                n_invoices=("invoice_no", "nunique"),
                free_units=("free_units", "sum"),
            )
            .reset_index()
            .sort_values("claim_amount", ascending=False)
        )

        result["total_claim"] = float(details["claim_value"].sum())
        result["by_company"] = by_company
        result["by_scheme"] = by_scheme
        result["details"] = details
        result["n_invoices"] = int(details["invoice_no"].nunique())

    logger.info(
        "calculate_claims: %d active schemes, %d qualifying invoices, "
        "total claim = ₹%.2f",
        result["n_schemes"],
        result["n_invoices"],
        result["total_claim"],
    )
    return result
