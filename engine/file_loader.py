"""
engine/file_loader.py
=====================
Robust file loader for real-world ERP exports.

Handles all the messy things real Indian ERP software produces:
- Excel (.xlsx, .xls) and CSV files
- Header junk rows (company name, logo placeholder rows at top)
- ₹ symbol and comma formatting in price columns (₹1,23,456.00)
- Total / Grand Total rows at the bottom
- Merged cell artifacts (unnamed columns)
- Hindi column names (transliterated to canonical)
- Multiple sheets in Excel (auto-picks the correct one)
- BOM characters in UTF-8 CSV files from Tally

Author: Rahul Jain | JECRC Foundation, Jaipur
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hindi / transliterated column name aliases (common in older Tally / Kuber)
# ---------------------------------------------------------------------------
HINDI_ALIASES: dict[str, str] = {
    # Sales
    "दिनांक": "date",
    "तारीख": "date",
    "बिल नं": "invoice_no",
    "बिल संख्या": "invoice_no",
    "ग्राहक": "customer_name",
    "पार्टी": "customer_name",
    "पार्टी नाम": "customer_name",
    "क्षेत्र": "customer_area",
    "माल": "product_name",
    "आइटम": "product_name",
    "मात्रा": "quantity",
    "दर": "sale_price",
    "बिक्री दर": "sale_price",
    "खरीद दर": "purchase_price",
    "छूट": "discount_pct",
    "भुगतान": "payment_status",
    # Stock
    "स्टॉक": "current_stock",
    "शेष": "current_stock",
    "क्रय मूल्य": "purchase_price",
}

# ---------------------------------------------------------------------------
# Rows that indicate junk / header / total rows to skip
# ---------------------------------------------------------------------------
JUNK_ROW_PATTERNS: list[str] = [
    r"^grand\s+total",
    r"^total$",
    r"^subtotal",
    r"^कुल\s+योग",
    r"opening\s+balance",
    r"closing\s+balance",
    r"^sr\.?\s*no\.?$",       # duplicate header rows inside body
    r"^s\.?\s*no\.?$",
    r"^#$",
]

# Columns that are definitely numeric — used to detect junk/header rows
NUMERIC_SENTINEL_COLS = ["quantity", "qty", "sale_price", "rate", "rate (sale)",
                          "purchase_price", "rate (cost)", "amount", "invoice_value"]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def read_file(
    source: Union[str, Path, bytes, io.BytesIO, io.StringIO],
    sheet_name: Union[str, int, None] = None,
) -> pd.DataFrame:
    """
    Read a CSV or Excel file from disk path, bytes, or file-like object.

    Handles:
    - .csv, .xlsx, .xls, .ods
    - UTF-8 BOM (Tally exports)
    - Auto-sheet detection for multi-sheet Excel

    Args:
        source: File path, raw bytes, or file-like object.
        sheet_name: For Excel — sheet name/index to read. None = auto-detect.

    Returns:
        Raw DataFrame (no standardization applied yet).
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        ext = path.suffix.lower()
        raw_bytes = path.read_bytes()
    elif isinstance(source, bytes):
        raw_bytes = source
        ext = _sniff_extension(raw_bytes)
    elif isinstance(source, (io.BytesIO, io.RawIOBase)):
        source.seek(0)
        raw_bytes = source.read()
        ext = _sniff_extension(raw_bytes)
    elif isinstance(source, io.StringIO):
        source.seek(0)
        raw_bytes = source.getvalue().encode('utf-8')
        ext = _sniff_extension(raw_bytes)
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    buf = io.BytesIO(raw_bytes)

    if ext in (".xlsx", ".xls", ".ods"):
        df = _read_excel(buf, sheet_name)
    else:
        df = _read_csv(buf)

    return df


def preprocess_erp_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a raw ERP DataFrame before column standardization.

    Steps:
    1. Strip BOM and whitespace from column names.
    2. Drop fully empty columns (Unnamed:X artifacts from merged cells).
    3. Detect and skip header-junk rows at the top (company name, logo rows).
    4. Drop total/subtotal rows at the bottom.
    5. Clean currency formatting from numeric-looking columns (₹, commas).
    6. Apply Hindi column alias mapping.
    7. Drop completely empty rows.

    Args:
        df: Raw DataFrame from read_file().

    Returns:
        Cleaned DataFrame ready for column standardization.
    """
    # 1. Clean column names
    df = _clean_column_names(df)

    # 2. Drop unnamed/empty columns (merged cell artifacts)
    df = _drop_unnamed_columns(df)

    # 3. Detect junk rows at top and skip them
    df = _skip_junk_header_rows(df)

    # 4. Drop total/summary rows
    df = _drop_total_rows(df)

    # 5. Clean ₹ and comma formatting from numeric columns
    df = _clean_currency_formatting(df)

    # 6. Apply Hindi aliases
    df = _apply_hindi_aliases(df)

    # 7. Drop completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    logger.info("preprocess_erp_dataframe: %d rows, %d cols after cleaning",
                len(df), len(df.columns))
    return df


def detect_schema_type(df: pd.DataFrame) -> str:
    """
    Auto-detect whether a DataFrame looks like sales, inventory, or customer data.

    Uses column presence heuristics. Useful when the user uploads a single file
    without specifying its type.

    Args:
        df: Preprocessed DataFrame.

    Returns:
        One of: 'sales', 'inventory', 'customer', 'unknown'
    """
    cols_lower = {c.lower().strip() for c in df.columns}

    sales_signals     = {"bill", "invoice", "party", "qty", "rate", "sale", "discount", "payment"}
    inventory_signals = {"stock", "closing", "reorder", "on hand", "available"}
    customer_signals  = {"outstanding", "balance", "credit limit", "ledger", "debtor"}

    sales_score     = len(cols_lower & sales_signals)
    inventory_score = len(cols_lower & inventory_signals)
    customer_score  = len(cols_lower & customer_signals)

    best = max(sales_score, inventory_score, customer_score)
    if best == 0:
        return "unknown"
    if sales_score == best:
        return "sales"
    if inventory_score == best:
        return "inventory"
    return "customer"


def get_unmapped_columns(df: pd.DataFrame, alias_map: dict[str, str]) -> list[str]:
    """
    Return column names in df that have NO mapping in alias_map.

    Useful for showing the user which columns were not recognized and
    may need manual mapping.

    Args:
        df: DataFrame after preprocess_erp_dataframe().
        alias_map: The SALES_ALIASES / INVENTORY_ALIASES etc. dict.

    Returns:
        List of unrecognised column names.
    """
    lower_alias = {k.lower().strip() for k in alias_map}
    return [c for c in df.columns if c.lower().strip() not in lower_alias]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sniff_extension(raw_bytes: bytes) -> str:
    """Detect file type from magic bytes."""
    # Excel: PK header (ZIP) = xlsx; D0CF = xls
    if raw_bytes[:4] == b"PK\x03\x04":
        return ".xlsx"
    if raw_bytes[:4] == b"\xd0\xcf\x11\xe0":
        return ".xls"
    return ".csv"


def _read_csv(buf: io.BytesIO) -> pd.DataFrame:
    """Read CSV with encoding fallback chain: utf-8-sig → cp1252 → latin-1."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            buf.seek(0)
            return pd.read_csv(buf, encoding=enc, dtype=str, skip_blank_lines=True)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    buf.seek(0)
    return pd.read_csv(buf, encoding="latin-1", dtype=str, skip_blank_lines=True)


def _read_excel(buf: io.BytesIO, sheet_name=None) -> pd.DataFrame:
    """Read Excel, auto-detecting the best sheet if sheet_name is None."""
    xl = pd.ExcelFile(buf)
    sheets = xl.sheet_names

    if sheet_name is not None:
        return pd.read_excel(xl, sheet_name=sheet_name, dtype=str)

    # Auto-detect: pick the sheet with the most rows
    best_sheet, best_rows = sheets[0], 0
    for s in sheets:
        try:
            tmp = pd.read_excel(xl, sheet_name=s, dtype=str, nrows=5)
            rows = len(pd.read_excel(xl, sheet_name=s, dtype=str))
            if rows > best_rows:
                best_sheet, best_rows = s, rows
        except Exception:
            continue

    logger.info("_read_excel: chose sheet '%s' (%d rows)", best_sheet, best_rows)
    return pd.read_excel(xl, sheet_name=best_sheet, dtype=str)


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip BOM, extra whitespace, and newlines from column names."""
    df.columns = [
        str(c).replace("\ufeff", "").replace("\n", " ").strip()
        for c in df.columns
    ]
    return df


def _drop_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop columns that are completely empty or Pandas auto-named Unnamed:X."""
    cols_to_drop = [
        c for c in df.columns
        if re.match(r"^unnamed[:\s]\d+", str(c).lower().strip())
        or df[c].isna().all()
    ]
    return df.drop(columns=cols_to_drop, errors="ignore")


def _skip_junk_header_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Many Tally/Kuber exports prepend 2-5 rows with company name, address,
    report title etc. before the actual data header. Detect and skip these.

    Strategy: the real header row is the one where most values look like
    column names (non-numeric, non-empty). We check up to the first 8 rows.
    """
    if len(df) < 2:
        return df

    # If first row has many nulls or looks like a company name row, re-read
    # by promoting the first non-null row to header.
    first_row = df.iloc[0]
    non_null_count = first_row.notna().sum()

    # Heuristic: real header rows have >= 3 non-null string values
    # AND at least one looks like a known column alias keyword
    HEADER_KEYWORDS = {
        "date", "bill", "invoice", "party", "item", "qty", "rate",
        "stock", "name", "amount", "narration", "ledger", "sr", "no",
        "quantity", "price", "balance", "outstanding",
    }

    def _row_looks_like_header(row: pd.Series) -> bool:
        vals = [str(v).lower().strip() for v in row if pd.notna(v) and str(v).strip()]
        keyword_hits = sum(
            1 for v in vals
            if any(kw in v for kw in HEADER_KEYWORDS)
        )
        return keyword_hits >= 2

    # Walk down until we find a row that looks like a real header
    for skip in range(min(8, len(df))):
        row = df.iloc[skip]
        if _row_looks_like_header(row):
            if skip > 0:
                # Promote this row to header
                new_header = df.iloc[skip]
                df = df.iloc[skip + 1:].copy()
                df.columns = [str(c).strip() for c in new_header]
                df = df.reset_index(drop=True)
                logger.info("_skip_junk_header_rows: skipped %d junk rows", skip)
            break

    return df


def _drop_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop rows whose first non-null cell matches a 'Total' / 'Grand Total' pattern.
    These are typically the last 1-5 rows of Tally/Marg exports.
    """
    compiled = [re.compile(p, re.IGNORECASE) for p in JUNK_ROW_PATTERNS]

    def _is_total_row(row: pd.Series) -> bool:
        for val in row:
            if pd.isna(val):
                continue
            s = str(val).strip()
            if any(pat.search(s) for pat in compiled):
                return True
            break  # only check first non-null value
        return False

    mask = df.apply(_is_total_row, axis=1)
    dropped = mask.sum()
    if dropped:
        logger.info("_drop_total_rows: dropped %d total/summary rows", dropped)
    return df[~mask].reset_index(drop=True)


def _clean_currency_formatting(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove ₹ symbol, commas, and extra spaces from cells that look like
    Indian currency values (₹1,23,456.00 → 123456.00).

    Only applies to columns whose names suggest numeric content.
    """
    CURRENCY_PATTERN = re.compile(r"[₹,\s]")
    NUMERIC_KEYWORDS = {
        "rate", "price", "amount", "qty", "quantity", "value",
        "discount", "balance", "outstanding", "stock", "cost",
    }

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in NUMERIC_KEYWORDS):
            df[col] = df[col].apply(
                lambda x: CURRENCY_PATTERN.sub("", str(x)).strip()
                if pd.notna(x) else x
            )
    return df


def _apply_hindi_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Hindi column names to their English canonical equivalents."""
    rename = {c: HINDI_ALIASES[c] for c in df.columns if c in HINDI_ALIASES}
    if rename:
        logger.info("_apply_hindi_aliases: renamed %d Hindi columns: %s",
                    len(rename), list(rename.keys()))
        df = df.rename(columns=rename)
    return df
