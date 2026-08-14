"""
engine/data_cleaner.py
======================
Canonical schema standardizer for the Wholesale BI System.

Handles column name variations, type coercion, null handling, deduplication,
and schema validation for all four CSV data sources: sales, inventory,
customers, and purchases.

Author: Wholesale BI System
Python: 3.12
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column alias dictionaries — every known variant maps to canonical name
# ---------------------------------------------------------------------------

SALES_ALIASES: dict[str, str] = {
    # invoice_no
    "invoice_no": "invoice_no",
    "invoice": "invoice_no",
    "invoice_number": "invoice_no",
    "bill_no": "invoice_no",
    "bill_number": "invoice_no",
    "inv_no": "invoice_no",
    "bill no.": "invoice_no",       # Kuber ERP
    "bill no": "invoice_no",
    "voucher_no": "invoice_no",     # Tally
    "vch no.": "invoice_no",
    # date
    "date": "date",
    "Date": "date",
    "DATE": "date",
    "invoice_date": "date",
    "sale_date": "date",
    "transaction_date": "date",
    "order_date": "date",
    "bill date": "date",            # Kuber ERP
    "bill_date": "date",
    "voucher date": "date",         # Tally
    # customer_name
    "customer_name": "customer_name",
    "customer": "customer_name",
    "cust_name": "customer_name",
    "client_name": "customer_name",
    "buyer": "customer_name",
    "party name": "customer_name",  # Kuber ERP
    "party_name": "customer_name",
    "ledger name": "customer_name", # Tally
    "ledger_name": "customer_name",
    # customer_area
    "customer_area": "customer_area",
    "area": "customer_area",
    "town": "customer_area",
    "location": "customer_area",
    "city": "customer_area",
    "region": "customer_area",
    "place": "customer_area",       # Kuber ERP
    "delivery_area": "customer_area",
    # product_name
    "product_name": "product_name",
    "product": "product_name",
    "item_name": "product_name",
    "item": "product_name",
    "product_desc": "product_name",
    "description": "product_name",
    "item name": "product_name",    # Kuber ERP
    "goods name": "product_name",   # Marg ERP
    # category
    "category": "category",
    "cat": "category",
    "product_category": "category",
    "dept": "category",
    "product cat": "category",      # Kuber ERP
    "product_cat": "category",
    "group": "category",            # Marg ERP
    # company
    "company": "company",
    "brand": "company",
    "manufacturer": "company",
    "vendor": "company",
    "supplier": "company",
    # size_variant
    "size_variant": "size_variant",
    "size": "size_variant",
    "variant": "size_variant",
    "pack_size": "size_variant",
    "sku_variant": "size_variant",
    "pack": "size_variant",         # Kuber ERP
    "packing": "size_variant",
    # quantity
    "quantity": "quantity",
    "qty": "quantity",
    "units": "quantity",
    "pieces": "quantity",
    "nos": "quantity",
    # purchase_price
    "purchase_price": "purchase_price",
    "cost_price": "purchase_price",
    "buying_price": "purchase_price",
    "cp": "purchase_price",
    "landing_price": "purchase_price",
    "rate (cost)": "purchase_price", # Kuber ERP
    "rate(cost)": "purchase_price",
    "cost rate": "purchase_price",
    # sale_price
    "sale_price": "sale_price",
    "selling_price": "sale_price",
    "sp": "sale_price",
    "mrp": "sale_price",
    "unit_price": "sale_price",
    "rate (sale)": "sale_price",    # Kuber ERP
    "rate(sale)": "sale_price",
    "sale rate": "sale_price",
    "rate": "sale_price",           # Marg ERP
    # discount_pct
    "discount_pct": "discount_pct",
    "discount": "discount_pct",
    "disc_pct": "discount_pct",
    "discount_percent": "discount_pct",
    "disc": "discount_pct",
    "disc%": "discount_pct",        # Kuber ERP
    "discount%": "discount_pct",
    # salesperson
    "salesperson": "salesperson",
    "sales_rep": "salesperson",
    "sales_person": "salesperson",
    "rep": "salesperson",
    "executive": "salesperson",
    # payment_status
    "payment_status": "payment_status",
    "pay_status": "payment_status",
    "status": "payment_status",
    "payment_state": "payment_status",
    "pay status": "payment_status",  # Kuber ERP
    # payment_due_date
    "payment_due_date": "payment_due_date",
    "due_date": "payment_due_date",
    "payment_due": "payment_due_date",
    "due": "payment_due_date",
    "due date": "payment_due_date",  # Kuber ERP
}

INVENTORY_ALIASES: dict[str, str] = {
    # product_name
    "product_name": "product_name",
    "product": "product_name",
    "item_name": "product_name",
    "item": "product_name",
    # category
    "category": "category",
    "cat": "category",
    "product_category": "category",
    # company
    "company": "company",
    "brand": "company",
    "manufacturer": "company",
    # size_variant
    "size_variant": "size_variant",
    "size": "size_variant",
    "variant": "size_variant",
    "pack_size": "size_variant",
    # current_stock
    "current_stock": "current_stock",
    "stock": "current_stock",
    "qty_on_hand": "current_stock",
    "on_hand": "current_stock",
    "available_qty": "current_stock",
    "closing_stock": "current_stock",
    # last_purchase_date
    "last_purchase_date": "last_purchase_date",
    "last_purchase": "last_purchase_date",
    "purchase_date": "last_purchase_date",
    # last_sale_date
    "last_sale_date": "last_sale_date",
    "last_sale": "last_sale_date",
    "last_sold": "last_sale_date",
    "sale_date": "last_sale_date",
    # purchase_price
    "purchase_price": "purchase_price",
    "cost_price": "purchase_price",
    "buying_price": "purchase_price",
    "cp": "purchase_price",
    # mrp
    "mrp": "mrp",
    "max_retail_price": "mrp",
    "retail_price": "mrp",
    "selling_price": "mrp",
    "sale_price": "mrp",
    # reorder_level
    "reorder_level": "reorder_level",
    "reorder": "reorder_level",
    "min_stock": "reorder_level",
    "reorder_point": "reorder_level",
}

CUSTOMER_ALIASES: dict[str, str] = {
    # customer_id
    "customer_id": "customer_id",
    "cust_id": "customer_id",
    "id": "customer_id",
    "customer_code": "customer_id",
    # customer_name
    "customer_name": "customer_name",
    "customer": "customer_name",
    "cust_name": "customer_name",
    "name": "customer_name",
    # area
    "area": "area",
    "town": "area",
    "location": "area",
    "city": "area",
    "customer_area": "area",
    # pincode
    "pincode": "pincode",
    "pin": "pincode",
    "postal_code": "pincode",
    "zip": "pincode",
    # customer_type
    "customer_type": "customer_type",
    "type": "customer_type",
    "cust_type": "customer_type",
    "category": "customer_type",
    # credit_limit
    "credit_limit": "credit_limit",
    "credit": "credit_limit",
    "limit": "credit_limit",
    "credit_line": "credit_limit",
    # outstanding_amount
    "outstanding_amount": "outstanding_amount",
    "outstanding": "outstanding_amount",
    "balance": "outstanding_amount",
    "due_amount": "outstanding_amount",
    "pending_amount": "outstanding_amount",
    # last_order_date
    "last_order_date": "last_order_date",
    "last_order": "last_order_date",
    "last_purchase_date": "last_order_date",
    # last_payment_date
    "last_payment_date": "last_payment_date",
    "last_payment": "last_payment_date",
    "payment_date": "last_payment_date",
    # total_business_ytd
    "total_business_ytd": "total_business_ytd",
    "total_business": "total_business_ytd",
    "ytd_sales": "total_business_ytd",
    "annual_business": "total_business_ytd",
}

PURCHASE_ALIASES: dict[str, str] = {
    # po_number
    "po_number": "po_number",
    "po_no": "po_number",
    "purchase_order": "po_number",
    "order_no": "po_number",
    # date
    "date": "date",
    "po_date": "date",
    "purchase_date": "date",
    "order_date": "date",
    # supplier_name
    "supplier_name": "supplier_name",
    "supplier": "supplier_name",
    "vendor": "supplier_name",
    "vendor_name": "supplier_name",
    # product_name
    "product_name": "product_name",
    "product": "product_name",
    "item_name": "product_name",
    # size_variant
    "size_variant": "size_variant",
    "size": "size_variant",
    "variant": "size_variant",
    # quantity
    "quantity": "quantity",
    "qty": "quantity",
    "units": "quantity",
    # landing_cost
    "landing_cost": "landing_cost",
    "cost": "landing_cost",
    "purchase_price": "landing_cost",
    "unit_cost": "landing_cost",
    # invoice_value
    "invoice_value": "invoice_value",
    "total_value": "invoice_value",
    "amount": "invoice_value",
    "total_amount": "invoice_value",
}

# Canonical column lists per schema
SALES_COLUMNS: list[str] = [
    "invoice_no", "date", "customer_name", "customer_area", "product_name",
    "category", "company", "size_variant", "quantity", "purchase_price",
    "sale_price", "discount_pct", "salesperson", "payment_status", "payment_due_date",
]

INVENTORY_COLUMNS: list[str] = [
    "product_name", "category", "company", "size_variant", "current_stock",
    "last_purchase_date", "last_sale_date", "purchase_price", "mrp", "reorder_level",
]

CUSTOMER_COLUMNS: list[str] = [
    "customer_id", "customer_name", "area", "pincode", "customer_type",
    "credit_limit", "outstanding_amount", "last_order_date",
    "last_payment_date", "total_business_ytd",
]

PURCHASE_COLUMNS: list[str] = [
    "po_number", "date", "supplier_name", "product_name", "size_variant",
    "quantity", "landing_cost", "invoice_value",
]

VALID_PAYMENT_STATUSES: set[str] = {"PAID", "UNPAID", "PENDING", "PARTIAL", "OVERDUE"}
VALID_CATEGORIES: set[str] = {
    "FMCG", "Personal Care", "Beverages", "Snacks",
    "Household", "Dairy", "Stationery", "Electronics Accessories",
    "Clothing Accessories", "Agricultural",
}
VALID_TOWNS: set[str] = {
    "Uniara", "Tonk", "Deoli", "Niwai",
    "Malpura", "Todaraisingh", "Khanpur", "Sawai Madhopur",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rename_columns(df: pd.DataFrame, alias_map: dict[str, str]) -> pd.DataFrame:
    """
    Rename DataFrame columns using the provided alias map.

    Matching is case-insensitive and strips whitespace. Only columns present
    in the alias map are renamed; unrecognised columns are left untouched.

    Args:
        df: Input DataFrame with raw column names.
        alias_map: Mapping of {raw_name → canonical_name}.

    Returns:
        DataFrame with columns renamed to canonical names.
    """
    lower_alias = {k.lower().strip(): v for k, v in alias_map.items()}
    rename_dict: dict[str, str] = {}
    for col in df.columns:
        canonical = lower_alias.get(col.lower().strip())
        if canonical and col != canonical:
            rename_dict[col] = canonical
    return df.rename(columns=rename_dict)


def _ensure_columns(
    df: pd.DataFrame, required: list[str], source: str
) -> pd.DataFrame:
    """
    Add missing canonical columns as NaN and log a warning for each.

    Args:
        df: DataFrame after column renaming.
        required: List of canonical column names expected.
        source: Human-readable label for log messages (e.g. 'sales').

    Returns:
        DataFrame with all required columns present (missing ones filled with NaN).
    """
    for col in required:
        if col not in df.columns:
            logger.warning(
                "Column '%s' missing from %s data — filling with NaN.", col, source
            )
            df[col] = np.nan
    return df


def _coerce_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    """
    Coerce specified columns to datetime, setting unparseable values to NaT.

    Args:
        df: Input DataFrame.
        date_cols: Column names to coerce.

    Returns:
        DataFrame with date columns as datetime64[ns].
    """
    for col in date_cols:
        if col in df.columns:
            # Our data is ISO format (YYYY-MM-DD); dayfirst=False avoids pandas warning
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=False)
    return df


def _coerce_numerics(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    """
    Coerce specified columns to float, setting unparseable values to NaN.

    Args:
        df: Input DataFrame.
        numeric_cols: Column names to coerce.

    Returns:
        DataFrame with numeric columns as float64.
    """
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _coerce_strings(df: pd.DataFrame, str_cols: list[str]) -> pd.DataFrame:
    """
    Coerce specified columns to stripped title-case strings, replacing NaN
    with empty string.

    Args:
        df: Input DataFrame.
        str_cols: Column names to coerce.

    Returns:
        DataFrame with string columns cleaned.
    """
    for col in str_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .replace("nan", "")
                .replace("None", "")
                .replace("NaN", "")
            )
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply generic data quality fixes to any DataFrame.

    Operations performed:
    1. Strip whitespace from column names.
    2. Drop fully duplicate rows.
    3. Drop rows where every value is NaN.
    4. Reset index.

    Args:
        df: Raw input DataFrame.

    Returns:
        Cleaned DataFrame with reset index.

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__!r}.")

    original_len = len(df)
    df = df.copy()

    # Strip column name whitespace
    df.columns = [str(c).strip() for c in df.columns]

    # Drop full duplicates
    df = df.drop_duplicates()

    # Drop completely empty rows
    df = df.dropna(how="all")

    dropped = original_len - len(df)
    if dropped:
        logger.info("clean_dataframe: removed %d rows (duplicates/empty).", dropped)

    return df.reset_index(drop=True)


def standardize_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize a raw sales DataFrame to the canonical sales schema.

    Canonical columns:
        invoice_no, date, customer_name, customer_area, product_name,
        category, company, size_variant, quantity, purchase_price,
        sale_price, discount_pct, salesperson, payment_status,
        payment_due_date

    Args:
        df: Raw sales DataFrame (column names may vary).

    Returns:
        Standardized sales DataFrame with canonical column names, correct
        dtypes, and only canonical columns (in order).

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__!r}.")

    df = clean_dataframe(df)
    df = _rename_columns(df, SALES_ALIASES)
    df = _ensure_columns(df, SALES_COLUMNS, "sales")

    # Type coercions
    df = _coerce_dates(df, ["date", "payment_due_date"])
    df = _coerce_numerics(
        df, ["quantity", "purchase_price", "sale_price", "discount_pct"]
    )
    df = _coerce_strings(
        df,
        [
            "invoice_no", "customer_name", "customer_area", "product_name",
            "category", "company", "size_variant", "salesperson",
            "payment_status",
        ],
    )

    # Normalise payment_status to uppercase
    if "payment_status" in df.columns:
        df["payment_status"] = df["payment_status"].str.upper()

    # Fill numeric defaults
    df["quantity"] = df["quantity"].fillna(0).clip(lower=0)
    df["discount_pct"] = df["discount_pct"].fillna(0).clip(lower=0, upper=100)
    df["purchase_price"] = df["purchase_price"].fillna(0).clip(lower=0)
    df["sale_price"] = df["sale_price"].fillna(0).clip(lower=0)

    logger.info("standardize_sales: returned %d rows.", len(df))
    return df[SALES_COLUMNS].copy()


def standardize_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize a raw inventory DataFrame to the canonical inventory schema.

    Canonical columns:
        product_name, category, company, size_variant, current_stock,
        last_purchase_date, last_sale_date, purchase_price, mrp,
        reorder_level

    Args:
        df: Raw inventory DataFrame (column names may vary).

    Returns:
        Standardized inventory DataFrame with canonical column names, correct
        dtypes, and only canonical columns (in order).

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__!r}.")

    df = clean_dataframe(df)
    df = _rename_columns(df, INVENTORY_ALIASES)
    df = _ensure_columns(df, INVENTORY_COLUMNS, "inventory")

    # Type coercions
    df = _coerce_dates(df, ["last_purchase_date", "last_sale_date"])
    df = _coerce_numerics(
        df, ["current_stock", "purchase_price", "mrp", "reorder_level"]
    )
    df = _coerce_strings(
        df, ["product_name", "category", "company", "size_variant"]
    )

    # Fill numeric defaults
    df["current_stock"] = df["current_stock"].fillna(0).clip(lower=0)
    df["purchase_price"] = df["purchase_price"].fillna(0).clip(lower=0)
    df["mrp"] = df["mrp"].fillna(0).clip(lower=0)
    df["reorder_level"] = df["reorder_level"].fillna(0).clip(lower=0)

    logger.info("standardize_inventory: returned %d rows.", len(df))
    return df[INVENTORY_COLUMNS].copy()


def standardize_customers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize a raw customer DataFrame to the canonical customer schema.

    Canonical columns:
        customer_id, customer_name, area, pincode, customer_type,
        credit_limit, outstanding_amount, last_order_date,
        last_payment_date, total_business_ytd

    Args:
        df: Raw customer DataFrame (column names may vary).

    Returns:
        Standardized customer DataFrame with canonical column names, correct
        dtypes, and only canonical columns (in order).

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__!r}.")

    df = clean_dataframe(df)
    df = _rename_columns(df, CUSTOMER_ALIASES)
    df = _ensure_columns(df, CUSTOMER_COLUMNS, "customers")

    # Type coercions
    df = _coerce_dates(df, ["last_order_date", "last_payment_date"])
    df = _coerce_numerics(
        df, ["credit_limit", "outstanding_amount", "total_business_ytd"]
    )
    df = _coerce_strings(
        df,
        [
            "customer_id", "customer_name", "area", "pincode",
            "customer_type",
        ],
    )

    # Fill numeric defaults
    df["credit_limit"] = df["credit_limit"].fillna(0).clip(lower=0)
    df["outstanding_amount"] = df["outstanding_amount"].fillna(0)
    df["total_business_ytd"] = df["total_business_ytd"].fillna(0).clip(lower=0)

    logger.info("standardize_customers: returned %d rows.", len(df))
    return df[CUSTOMER_COLUMNS].copy()


def standardize_purchases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize a raw purchase DataFrame to the canonical purchase schema.

    Canonical columns:
        po_number, date, supplier_name, product_name, size_variant,
        quantity, landing_cost, invoice_value

    Args:
        df: Raw purchase DataFrame (column names may vary).

    Returns:
        Standardized purchase DataFrame with canonical column names, correct
        dtypes, and only canonical columns (in order).

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__!r}.")

    df = clean_dataframe(df)
    df = _rename_columns(df, PURCHASE_ALIASES)
    df = _ensure_columns(df, PURCHASE_COLUMNS, "purchases")

    # Type coercions
    df = _coerce_dates(df, ["date"])
    df = _coerce_numerics(df, ["quantity", "landing_cost", "invoice_value"])
    df = _coerce_strings(
        df, ["po_number", "supplier_name", "product_name", "size_variant"]
    )

    # Fill numeric defaults
    df["quantity"] = df["quantity"].fillna(0).clip(lower=0)
    df["landing_cost"] = df["landing_cost"].fillna(0).clip(lower=0)
    df["invoice_value"] = df["invoice_value"].fillna(0).clip(lower=0)

    logger.info("standardize_purchases: returned %d rows.", len(df))
    return df[PURCHASE_COLUMNS].copy()


def validate_csv_upload(
    df: pd.DataFrame, schema_type: str
) -> tuple[bool, list[str]]:
    """
    Validate an uploaded CSV DataFrame against a named schema.

    Performs structural and data-quality checks:
    - Required columns present
    - No completely empty required columns
    - Date columns parseable
    - Numeric columns positive where required
    - Enum-like columns contain valid values (with warning, not error)

    Args:
        df: DataFrame to validate (may be raw or already standardized).
        schema_type: One of ``'sales'``, ``'inventory'``, ``'customers'``,
            ``'purchases'``.

    Returns:
        A tuple ``(is_valid, errors)`` where ``is_valid`` is ``True`` if no
        errors were found, and ``errors`` is a list of human-readable error
        strings (empty if valid).

    Raises:
        ValueError: If ``schema_type`` is not one of the four supported values.
    """
    schema_type = schema_type.lower().strip()
    supported = {"sales", "inventory", "customers", "purchases"}
    if schema_type not in supported:
        raise ValueError(
            f"schema_type must be one of {supported!r}, got {schema_type!r}."
        )

    errors: list[str] = []

    # ---- 1. Normalise column names for lookup ----
    alias_map = {
        "sales": SALES_ALIASES,
        "inventory": INVENTORY_ALIASES,
        "customers": CUSTOMER_ALIASES,
        "purchases": PURCHASE_ALIASES,
    }[schema_type]

    required_cols = {
        "sales": SALES_COLUMNS,
        "inventory": INVENTORY_COLUMNS,
        "customers": CUSTOMER_COLUMNS,
        "purchases": PURCHASE_COLUMNS,
    }[schema_type]

    lower_alias = {k.lower().strip(): v for k, v in alias_map.items()}
    # Build reverse mapping: canonical → list of present raw col names
    canonical_present: dict[str, str] = {}
    for raw_col in df.columns:
        canonical = lower_alias.get(raw_col.lower().strip())
        if canonical:
            canonical_present[canonical] = raw_col

    # ---- 2. Missing required columns ----
    missing = [c for c in required_cols if c not in canonical_present]
    for col in missing:
        errors.append(f"Missing required column: '{col}'.")

    if missing:
        # Cannot continue without columns
        return False, errors

    # ---- 3. Empty checks on critical columns ----
    critical: dict[str, list[str]] = {
        "sales": ["invoice_no", "date", "product_name", "quantity", "sale_price"],
        "inventory": ["product_name", "current_stock", "purchase_price"],
        "customers": ["customer_id", "customer_name"],
        "purchases": ["po_number", "date", "product_name", "quantity"],
    }
    for col in critical[schema_type]:
        raw = canonical_present.get(col)
        if raw and df[raw].isna().all():
            errors.append(f"Column '{col}' is entirely empty.")

    # ---- 4. Numeric value checks ----
    numeric_positive: dict[str, list[str]] = {
        "sales": ["quantity", "sale_price", "purchase_price"],
        "inventory": ["current_stock", "purchase_price", "mrp"],
        "customers": ["credit_limit", "total_business_ytd"],
        "purchases": ["quantity", "landing_cost", "invoice_value"],
    }
    for col in numeric_positive[schema_type]:
        raw = canonical_present.get(col)
        if raw:
            numeric_series = pd.to_numeric(df[raw], errors="coerce")
            n_negative = (numeric_series < 0).sum()
            n_invalid = numeric_series.isna().sum() - df[raw].isna().sum()
            if n_negative > 0:
                errors.append(
                    f"Column '{col}' has {n_negative} negative value(s)."
                )
            if n_invalid > 0:
                errors.append(
                    f"Column '{col}' has {n_invalid} non-numeric value(s)."
                )

    # ---- 5. Date column checks ----
    date_cols_map: dict[str, list[str]] = {
        "sales": ["date", "payment_due_date"],
        "inventory": ["last_purchase_date", "last_sale_date"],
        "customers": ["last_order_date", "last_payment_date"],
        "purchases": ["date"],
    }
    for col in date_cols_map[schema_type]:
        raw = canonical_present.get(col)
        if raw:
            parsed = pd.to_datetime(df[raw], errors="coerce", dayfirst=False)
            n_bad = parsed.isna().sum() - df[raw].isna().sum()
            if n_bad > 0:
                errors.append(
                    f"Column '{col}' has {n_bad} unparseable date value(s)."
                )

    # ---- 6. Enum / set membership warnings (logged, not errors) ----
    if schema_type == "sales":
        ps_raw = canonical_present.get("payment_status")
        if ps_raw:
            unique_vals = set(
                df[ps_raw].dropna().astype(str).str.upper().unique()
            )
            invalid_ps = unique_vals - VALID_PAYMENT_STATUSES
            if invalid_ps:
                logger.warning(
                    "validate_csv_upload: unknown payment_status values: %s",
                    invalid_ps,
                )

        cat_raw = canonical_present.get("category")
        if cat_raw:
            unique_cats = set(df[cat_raw].dropna().astype(str).unique())
            invalid_cats = unique_cats - VALID_CATEGORIES
            if invalid_cats:
                logger.warning(
                    "validate_csv_upload: unknown category values: %s",
                    invalid_cats,
                )

    # ---- 7. Row count sanity ----
    if len(df) == 0:
        errors.append("DataFrame is empty — no rows to process.")

    is_valid = len(errors) == 0
    return is_valid, errors


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------

def load_and_standardize(
    filepath: str, schema_type: str, **read_kwargs: Any
) -> pd.DataFrame:
    """
    Read a CSV file and immediately standardize it to the canonical schema.

    Args:
        filepath: Absolute or relative path to the CSV file.
        schema_type: One of ``'sales'``, ``'inventory'``, ``'customers'``,
            ``'purchases'``.
        **read_kwargs: Extra keyword arguments forwarded to ``pd.read_csv``.

    Returns:
        Standardized DataFrame.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If schema_type is not supported.
    """
    import os

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"CSV file not found: {filepath!r}")

    df = pd.read_csv(filepath, **read_kwargs)
    standardizers = {
        "sales": standardize_sales,
        "inventory": standardize_inventory,
        "customers": standardize_customers,
        "purchases": standardize_purchases,
    }
    schema_type = schema_type.lower().strip()
    if schema_type not in standardizers:
        raise ValueError(
            f"schema_type must be one of {list(standardizers)!r}, got {schema_type!r}."
        )
    return standardizers[schema_type](df)
