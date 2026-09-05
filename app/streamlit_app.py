"""
app/streamlit_app.py
====================
Five-Workspace Streamlit Command Center for the Wholesale BI System — Agent Edition.
AI-powered decision support for Indian FMCG distributors.

Workspaces:
  1. ⚡ Command Center          — Business snapshot, KPIs, CEO Briefing, Recommendations
  2. 💳 Revenue Recovery & Risk — Receivables, collection, recovery engine, audit ledger
  3. 📦 Inventory & Operations  — Dead stock, stockout risk, demand forecasting, margins
  4. 👥 Customer Intelligence   — Segmentation, churn, geography, territory performance
  5. 🤖 AI Business Analyst     — ReAct AI agent with full tool access

Run with:
    streamlit run app/streamlit_app.py

Author: Rahul Jain | JECRC Foundation, Jaipur
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Figma-inspired design system ──────────────────────────────────────────────
from app.ui_foundation import (
    inject_global_css,
    render_page_header as _ui_render_page_header,
    render_section_header,
    render_kpi_card,
    render_status_badge,
    render_empty_state,
    render_error_state,
    render_unavailable_state,
    render_success_state,
    render_sidebar_brand,
    render_data_status_sidebar,
    fmt_inr as _ui_fmt_inr,
    fmt_number,
    fmt_percent,
    color_status as _ui_color_status,
    T as DESIGN_TOKENS,
)

from engine.analytics import (
    area_sales_ranking,
    calculate_margins,
    category_month_heatmap,
    detect_dead_stock,
    get_outstanding_payments,
    monthly_revenue_trend,
    detect_churned_retailers,
)
from engine.anomaly_detector import detect_anomalies
from engine.data_cleaner import standardize_customers, standardize_inventory, standardize_sales, SALES_ALIASES, INVENTORY_ALIASES, CUSTOMER_ALIASES
from engine.file_loader import preprocess_erp_dataframe, read_file, get_unmapped_columns
from engine.forecasting import (
    detect_declining_products,
    detect_demand_spikes,
    forecast_demand,
)
from engine.recommender import ceo_morning_briefing, filter_by_category, generate_recommendations

from engine.segmentation import compute_rfm, get_segment_recommendations, segment_customers

# ═════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & THEME
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Wholesale BI System | Raj Distributors",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject Figma-inspired design system CSS ────────────────────────────────
inject_global_css()

# ─── Plotly dark template ─────────────────────────────────────────────────────
PLOTLY_TEMPLATE = "plotly_dark"
PRIMARY_COLORS = px.colors.qualitative.Vivid

# ═════════════════════════════════════════════════════════════════════════════
# SESSION STATE & DATA LOADING
# ═════════════════════════════════════════════════════════════════════════════
DATA_DIR = Path(__file__).parent.parent / "data"

def _default_data_exists() -> bool:
    return (DATA_DIR / "processed" / "demo_sales.csv").exists()

@st.cache_data(show_spinner="Loading and cleaning data...")
def load_and_clean(
    sales_bytes: bytes,
    inventory_bytes: bytes,
    customer_bytes: bytes,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sales_df = standardize_sales(pd.read_csv(pd.io.common.BytesIO(sales_bytes)))
    inv_df   = standardize_inventory(pd.read_csv(pd.io.common.BytesIO(inventory_bytes)))
    cust_df  = standardize_customers(pd.read_csv(pd.io.common.BytesIO(customer_bytes)))
    return sales_df, inv_df, cust_df

@st.cache_data(show_spinner="Loading default data...")
def load_defaults() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sales_df = standardize_sales(pd.read_csv(DATA_DIR / "processed" / "demo_sales.csv"))
    inv_df   = standardize_inventory(pd.read_csv(DATA_DIR / "processed" / "demo_inventory.csv"))
    cust_df  = standardize_customers(pd.read_csv(DATA_DIR / "processed" / "demo_customers.csv"))
    return sales_df, inv_df, cust_df

# ── Analytics cache functions ─────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _get_dead_stock(inv_hash: int, _inv_df: pd.DataFrame) -> pd.DataFrame:
    return detect_dead_stock(_inv_df)

@st.cache_data(show_spinner=False)
def _get_outstanding(s_hash: int, c_hash: int, _sales: pd.DataFrame, _cust: pd.DataFrame) -> pd.DataFrame:
    return get_outstanding_payments(_sales, _cust)

@st.cache_data(show_spinner=False)
def _get_churned_retailers(s_hash: int, _sales: pd.DataFrame) -> pd.DataFrame:
    return detect_churned_retailers(_sales)

@st.cache_data(show_spinner=False)
def _get_margins(s_hash: int, _sales: pd.DataFrame) -> dict:
    """Wrap calculate_margins flat DataFrame into by_product / by_company dicts."""
    flat = calculate_margins(_sales)
    # Rename avg_ prefix columns for simpler UI references
    by_product = flat.rename(columns={
        "avg_real_margin_pct": "real_margin_pct",
        "avg_gross_margin_pct": "gross_margin_pct",
    })
    by_company = (
        flat.groupby("company", dropna=False)
        .agg(
            real_margin_pct=("avg_real_margin_pct", "mean"),
            total_revenue=("total_revenue", "sum"),
            total_profit=("total_profit", "sum"),
            num_products=("product_name", "nunique"),
        )
        .round(2)
        .reset_index()
    )
    by_category = (
        flat.groupby("category", dropna=False)
        .agg(real_margin_pct=("avg_real_margin_pct", "mean"))
        .round(2)
        .reset_index()
    )
    return {"by_product": by_product, "by_company": by_company, "by_category": by_category}

@st.cache_data(show_spinner=False)
def _get_area_rank(s_hash: int, _sales: pd.DataFrame) -> pd.DataFrame:
    return area_sales_ranking(_sales)

@st.cache_data(show_spinner=False)
def _get_monthly_trend(s_hash: int, _sales: pd.DataFrame) -> pd.DataFrame:
    return monthly_revenue_trend(_sales)

@st.cache_data(show_spinner=False)
def _get_heatmap(s_hash: int, _sales: pd.DataFrame) -> pd.DataFrame:
    return category_month_heatmap(_sales)

@st.cache_data(show_spinner="Running segmentation...")
def _get_segments(s_hash: int, c_hash: int, _sales: pd.DataFrame, _cust: pd.DataFrame):
    rfm_df = compute_rfm(_sales, _cust)
    seg_df = segment_customers(rfm_df)
    return seg_df

@st.cache_data(show_spinner="Running anomaly detection...")
def _get_anomalies(s_hash: int, _sales: pd.DataFrame) -> pd.DataFrame:
    return detect_anomalies(_sales)

@st.cache_data(show_spinner="Running forecasting...")
def _get_forecast_spikes(s_hash: int, inv_hash: int, _sales: pd.DataFrame, _inv: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    try:
        top_cat = _sales["category"].mode().iloc[0] if "category" in _sales.columns and not _sales.empty else "FMCG"
        fc = forecast_demand(_sales, top_cat, 30)
        return detect_demand_spikes({top_cat: fc}, _inv), ""
    except Exception as e:
        return pd.DataFrame(), str(e)

# ── Format helpers (thin wrappers — ui_foundation is canonical) ───────────────
def fmt_inr(amount: float) -> str:
    """Format amount in Indian Rupee notation. Delegates to ui_foundation."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "₹—"
    if amount >= 1_00_00_000:
        return f"₹{amount/1_00_00_000:.2f}Cr"
    elif amount >= 1_00_000:
        return f"₹{amount/1_00_000:.1f}L"
    elif amount >= 1_000:
        return f"₹{amount/1_000:.1f}K"
    return f"₹{amount:,.0f}"


def color_status(val: str) -> str:
    """Pandas Styler helper. Uses Figma tokens via ui_foundation."""
    return _ui_color_status(val)


def _render_workspace_header(icon: str, title: str, subtitle: str = "") -> None:
    """Thin wrapper around ui_foundation.render_page_header using new signature."""
    _ui_render_page_header(icon, title, subtitle, meta_right="<b>Business:</b> Tonk, Rajasthan &nbsp;|&nbsp; ERP: Kuber / Tally / Marg")


# ── Backward-compat alias so existing calls like render_page_header("LABEL","Title","desc") still work ──
def render_page_header(label: str, title: str, description: str = "") -> None:
    """Legacy wrapper — keeps existing caller sites functional."""
    # Map old (label, title, description) API to new (icon, title, subtitle)
    _ui_render_page_header("", f"{label} — {title}" if label else title, description)


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Figma-inspired
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # Brand header
    render_sidebar_brand()

    # Navigation
    page = st.radio(
        "Navigate",
        options=[
            "⚡ Command Center",
            "💳 Revenue Recovery & Risk",
            "📦 Inventory & Operations",
            "👥 Customer Intelligence",
            "🤖 AI Business Analyst",
        ],
        label_visibility="collapsed",
    )

# Data status (rendered after sidebar context so session state is available)
if "sales_df" in st.session_state and not st.session_state["sales_df"].empty:
    _n_sales = len(st.session_state["sales_df"])
    _n_cust  = len(st.session_state.get("cust_df", pd.DataFrame()))
    _n_sku   = len(st.session_state.get("inv_df", pd.DataFrame()))
    render_data_status_sidebar({
        "sales_count": _n_sales,
        "cust_count":  _n_cust,
        "sku_count":   _n_sku,
        "months":      "24M",
    })
else:
    render_data_status_sidebar(None)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — ⚡ COMMAND CENTER
# ═════════════════════════════════════════════════════════════════════════════
if page == "⚡ Command Center":

    # ── Load business profile ─────────────────────────────────────────────────
    import json as _json
    _profile_defaults = {"business_name": "Wholesale Distributor", "owner_name": "Owner",
                         "city": "HQ", "state": "Rajasthan", "business_type": "FMCG",
                         "financial_year": "2025-26", "gstin": "—"}
    try:
        _pp = Path(__file__).parent.parent / "data" / "config" / "business_profile.json"
        _profile = _json.loads(_pp.read_text()) if _pp.exists() else _profile_defaults
    except Exception:
        _profile = _profile_defaults

    # ── 1. HEADER ─────────────────────────────────────────────────────────────
    _biz_name = _profile.get("business_name", "Distributor")
    _city     = _profile.get("city", "")
    _state    = _profile.get("state", "")
    _fy       = _profile.get("financial_year", "2025-26")
    _gstin    = _profile.get("gstin", "—")
    _owner    = _profile.get("owner_name", "—")
    _btype    = _profile.get("business_type", "FMCG")

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'padding-bottom:14px;border-bottom:1px solid {DESIGN_TOKENS["border"]};margin-bottom:20px;">'
        f'<div>'
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:{DESIGN_TOKENS["text_muted"]};margin-bottom:6px;">⚡ COMMAND CENTER</div>'
        f'<h1 style="font-size:22px;font-weight:700;color:{DESIGN_TOKENS["text_primary"]};'
        f'margin:0 0 4px;letter-spacing:-0.02em;">What needs your attention right now.</h1>'
        f'<p style="font-size:12px;color:{DESIGN_TOKENS["text_secondary"]};margin:0;">'
        f'{_biz_name} &nbsp;&middot;&nbsp; {_city}, {_state} &nbsp;&middot;&nbsp; FY {_fy}</p>'
        f'</div>'
        f'<div style="text-align:right;font-size:11px;color:{DESIGN_TOKENS["text_muted"]};'
        f'line-height:1.8;padding-top:4px;">'
        f'<b style="color:{DESIGN_TOKENS["text_secondary"]};">ERP:</b> Kuber / Tally / Marg<br>'
        f'<b style="color:{DESIGN_TOKENS["text_secondary"]};">GSTIN:</b> {_gstin}'
        f'</div></div>',
        unsafe_allow_html=True
    )

    # ── 2. DATA SOURCE ────────────────────────────────────────────────────────
    with st.expander("⚙️  Data Configuration — Load Demo Data or Upload CSV",
                     expanded=("sales_df" not in st.session_state)):
        demo_dir = Path(__file__).parent.parent / "data"
        demo_sales_path = demo_dir / "processed" / "demo_sales.csv"
        demo_inv_path   = demo_dir / "processed" / "demo_inventory.csv"
        demo_cust_path  = demo_dir / "processed" / "demo_customers.csv"
        if _default_data_exists():
            st.caption("Loads pre-configured synthetic data for Raj Distributors — no file upload needed.")
            if st.button("🚀 Load Demo Data Instantly", type="primary",
                         use_container_width=True, key="load_demo_btn"):
                with st.spinner("Loading demo data…"):
                    _sd, _id, _cd = load_defaults()
                    st.session_state["sales_df"]    = _sd
                    st.session_state["inv_df"]      = _id
                    st.session_state["cust_df"]     = _cd
                    st.session_state["data_source"] = "synthetic"
                    st.session_state["sales_hash"]  = int(pd.util.hash_pandas_object(_sd).sum())
                    st.session_state["inv_hash"]    = int(pd.util.hash_pandas_object(_id).sum())
                    st.session_state["cust_hash"]   = int(pd.util.hash_pandas_object(_cd).sum())
                st.rerun()
        st.markdown("---")
        if demo_sales_path.exists():
            _dl1, _dl2, _dl3 = st.columns(3)
            with _dl1: st.download_button("📊 Sales", open(demo_sales_path, "rb").read(), "demo_sales.csv", "text/csv", use_container_width=True)
            with _dl2: st.download_button("📦 Inventory", open(demo_inv_path, "rb").read(), "demo_inventory.csv", "text/csv", use_container_width=True)
            with _dl3: st.download_button("👥 Customers", open(demo_cust_path, "rb").read(), "demo_customers.csv", "text/csv", use_container_width=True)
        st.markdown("---")
        _up1, _up2, _up3 = st.columns(3)
        with _up1: sales_file = st.file_uploader("Sales Data", type=["csv", "xlsx", "xls"], key="sales_upload")
        with _up2: inv_file   = st.file_uploader("Inventory Data", type=["csv", "xlsx", "xls"], key="inv_upload")
        with _up3: cust_file  = st.file_uploader("Customer Data", type=["csv", "xlsx", "xls"], key="cust_upload")
        if sales_file or inv_file or cust_file:
            if "sales_df" not in st.session_state and _default_data_exists():
                _s, _i, _c = load_defaults()
                st.session_state["sales_df"], st.session_state["inv_df"], st.session_state["cust_df"] = _s, _i, _c
            def _load_up(file_obj, std_fn, alias, lbl):
                _cdf = preprocess_erp_dataframe(read_file(file_obj.read()))
                _unk = get_unmapped_columns(_cdf, alias)
                if _unk: st.warning(f"⚠️ **{lbl}:** Ignored {len(_unk)} cols")
                return std_fn(_cdf)
            try:
                if sales_file: st.session_state["sales_df"] = _load_up(sales_file, standardize_sales, SALES_ALIASES, "Sales")
                if inv_file:   st.session_state["inv_df"]   = _load_up(inv_file, standardize_inventory, INVENTORY_ALIASES, "Inventory")
                if cust_file:  st.session_state["cust_df"]  = _load_up(cust_file, standardize_customers, CUSTOMER_ALIASES, "Customer")
                st.session_state["data_source"] = "uploaded"
                st.session_state["sales_hash"]  = int(pd.util.hash_pandas_object(st.session_state["sales_df"]).sum())
                st.session_state["inv_hash"]    = int(pd.util.hash_pandas_object(st.session_state["inv_df"]).sum())
                st.session_state["cust_hash"]   = int(pd.util.hash_pandas_object(st.session_state["cust_df"]).sum())
                st.success("✅ Data loaded and standardized.")
            except Exception as _e:
                st.error(f"❌ Error: {_e}")

    if "sales_df" not in st.session_state:
        render_empty_state("🔌", "Awaiting Data Connection",
            "Please load the demo data or upload your ERP exports above to initialize the Command Center.")
        st.stop()

    sales_df = st.session_state["sales_df"]
    inv_df   = st.session_state["inv_df"]
    cust_df  = st.session_state["cust_df"]

    # ── Backend calls (all wrapped defensively) ────────────────────────────────
    try: trend_df = _get_monthly_trend(st.session_state["sales_hash"], sales_df)
    except Exception: trend_df = pd.DataFrame()
    try: area_df = _get_area_rank(st.session_state["sales_hash"], sales_df)
    except Exception: area_df = pd.DataFrame()
    try: dead_stock_df = _get_dead_stock(st.session_state["inv_hash"], inv_df)
    except Exception: dead_stock_df = pd.DataFrame()
    try: outstanding_df = _get_outstanding(st.session_state["sales_hash"], st.session_state["cust_hash"], sales_df, cust_df)
    except Exception: outstanding_df = pd.DataFrame()
    try:
        from engine.payment_intelligence import score_payment_risk, get_collection_summary
        risk_df     = score_payment_risk(sales_df, cust_df)
        col_summary = get_collection_summary(risk_df) if not risk_df.empty else {}
    except Exception:
        risk_df = pd.DataFrame()
        col_summary = {}
    try:
        from engine.analytics import detect_dead_stock as _dds2, get_outstanding_payments as _gop2
        all_recs = generate_recommendations(dead_stock_df=_dds2(inv_df), outstanding_df=_gop2(sales_df, cust_df))
    except Exception:
        all_recs = []

    # ── Derived metrics ────────────────────────────────────────────────────────
    _24m_rev  = trend_df["total_revenue"].sum() if not trend_df.empty else 0
    _12m_rev  = trend_df.tail(12)["total_revenue"].sum() if not trend_df.empty else 0
    _curr_rev = trend_df["total_revenue"].iloc[-1] if not trend_df.empty else 0
    _mom_pct  = trend_df["mom_revenue_change_pct"].iloc[-1] if not trend_df.empty and len(trend_df) > 1 else 0
    # Fix 1: True customer-level Total Outstanding (deduplicated by customer_id)
    _tot_out = cust_df.drop_duplicates("customer_id")["outstanding_amount"].sum() if not cust_df.empty and "outstanding_amount" in cust_df.columns else 0

    # Fix 2: Overdue >30 Days (aged by the customer's oldest unpaid invoice via risk_df)
    _od30 = 0
    if not cust_df.empty and "outstanding_amount" in cust_df.columns and not risk_df.empty and "max_days_overdue" in risk_df.columns:
        _merged_risk = cust_df.drop_duplicates("customer_id").merge(risk_df[["customer_name", "max_days_overdue"]], on="customer_name", how="left")
        _od30 = _merged_risk.loc[_merged_risk["max_days_overdue"] > 30, "outstanding_amount"].sum()
    _active_p = len(cust_df.drop_duplicates("customer_id")[cust_df.drop_duplicates("customer_id")["outstanding_amount"] > 0]) if not cust_df.empty and "outstanding_amount" in cust_df.columns else 0
    _hi_risk  = int(risk_df[risk_df["risk_tier"].isin(["HIGH RISK", "WRITE-OFF RISK"])].shape[0]) if not risk_df.empty else 0
    _wo_cnt   = int(col_summary.get("write_off_risk_count", 0))
    _inv_val  = (inv_df["current_stock"].fillna(0) * inv_df["purchase_price"].fillna(0)).sum()
    _stockout = int((inv_df["current_stock"].fillna(0) <= inv_df["reorder_level"].fillna(0)).sum())
    _top_towns = area_df["customer_area"].tolist() if not area_df.empty else []
    _top_cats  = sales_df.groupby("category")["quantity"].sum().nlargest(3).index.tolist() if not sales_df.empty else []
    _mom_arr  = "▲" if _mom_pct >= 0 else "▼"
    _mom_col  = DESIGN_TOKENS["success"] if _mom_pct >= 0 else DESIGN_TOKENS["danger"]

    DT = DESIGN_TOKENS  # shorthand

    # ── 3. BUSINESS SNAPSHOT ─────────────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:{DT["text_muted"]};margin-bottom:8px;">BUSINESS SNAPSHOT</div>',
        unsafe_allow_html=True
    )

    _tp = "".join(
        f'<span style="display:inline-block;font-size:10px;font-weight:500;padding:2px 8px;'
        f'border-radius:999px;border:1px solid {DT["border"]};color:{DT["text_secondary"]};'
        f'margin:2px 4px 2px 0;">{t}</span>' for t in _top_towns[:8]
    )
    _cp = "".join(
        f'<span style="display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;'
        f'border-radius:999px;background:rgba(109,91,240,0.14);color:{DT["accent"]};'
        f'margin:2px 4px 2px 0;">{c}</span>' for c in _top_cats
    )

    snap_parts = [
        f'<div style="background:{DT["card"]};border:1px solid {DT["border"]};'
        f'border-radius:{DT["radius_card"]};margin-bottom:20px;overflow:hidden;">',
        f'<div style="display:grid;grid-template-columns:1fr 1px 1.3fr 1px 1.2fr;">',
        # Zone A
        f'<div style="padding:20px 22px;">',
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.09em;color:{DT["text_muted"]};margin-bottom:10px;">Identity</div>',
        f'<div style="font-size:17px;font-weight:700;color:{DT["text_primary"]};margin-bottom:3px;letter-spacing:-0.01em;">{_biz_name}</div>',
        f'<div style="font-size:12px;color:{DT["text_secondary"]};margin-bottom:2px;">{_owner}</div>',
        f'<div style="font-size:12px;color:{DT["text_muted"]};margin-bottom:14px;">{_btype}</div>',
        f'<div style="font-size:11px;color:{DT["text_muted"]};line-height:1.9;">&#128205; {_city}, {_state}<br>&#128197; FY {_fy}</div>',
        f'</div>',
        f'<div style="background:{DT["border"]};"></div>',
        # Zone B
        f'<div style="padding:20px 22px;">',
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.09em;color:{DT["text_muted"]};margin-bottom:10px;">Financial Scale</div>',
        f'<div style="margin-bottom:12px;"><div style="font-size:10px;color:{DT["text_muted"]};margin-bottom:2px;">24-Month Revenue</div>',
        f'<div style="font-size:20px;font-weight:700;color:{DT["text_primary"]};font-variant-numeric:tabular-nums;letter-spacing:-0.01em;">{fmt_inr(_24m_rev)}</div></div>',
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">',
        f'<div style="background:{DT["card_elevated"]};border-radius:8px;padding:9px 11px;"><div style="font-size:9px;color:{DT["text_muted"]};margin-bottom:2px;">Current Month</div><div style="font-size:13px;font-weight:600;color:{DT["text_primary"]};font-variant-numeric:tabular-nums;">{fmt_inr(_curr_rev)}</div><div style="font-size:10px;color:{_mom_col};margin-top:1px;">{_mom_arr} {abs(_mom_pct):.1f}% MoM</div></div>',
        f'<div style="background:{DT["card_elevated"]};border-radius:8px;padding:9px 11px;"><div style="font-size:9px;color:{DT["text_muted"]};margin-bottom:2px;">Receivables</div><div style="font-size:13px;font-weight:600;color:{DT["danger"]};font-variant-numeric:tabular-nums;">{fmt_inr(_tot_out)}</div><div style="font-size:10px;color:{DT["text_muted"]};margin-top:1px;">{_active_p} parties</div></div>',
        f'<div style="background:{DT["card_elevated"]};border-radius:8px;padding:9px 11px;"><div style="font-size:9px;color:{DT["text_muted"]};margin-bottom:2px;">Inventory Value</div><div style="font-size:13px;font-weight:600;color:{DT["text_primary"]};font-variant-numeric:tabular-nums;">{fmt_inr(_inv_val)}</div><div style="font-size:10px;color:{DT["text_muted"]};margin-top:1px;">{len(inv_df)} SKUs</div></div>',
        f'<div style="background:{DT["card_elevated"]};border-radius:8px;padding:9px 11px;"><div style="font-size:9px;color:{DT["text_muted"]};margin-bottom:2px;">12-Month Revenue</div><div style="font-size:13px;font-weight:600;color:{DT["text_primary"]};font-variant-numeric:tabular-nums;">{fmt_inr(_12m_rev)}</div><div style="font-size:10px;color:{DT["text_muted"]};margin-top:1px;">trailing 12M</div></div>',
        f'</div></div>',
        f'<div style="background:{DT["border"]};"></div>',
        # Zone C
        f'<div style="padding:20px 22px;">',
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.09em;color:{DT["text_muted"]};margin-bottom:10px;">Coverage &amp; Categories</div>',
        f'<div style="font-size:10px;color:{DT["text_muted"]};margin-bottom:5px;font-weight:600;">{len(_top_towns)} TERRITORIES</div>',
        f'<div style="margin-bottom:12px;line-height:2.2;">{_tp or "<span style=color:#6B7482;font-size:11px;>No data</span>"}</div>',
        f'<div style="font-size:10px;color:{DT["text_muted"]};margin-bottom:5px;font-weight:600;">TOP CATEGORIES</div>',
        f'<div style="line-height:2.2;">{_cp or "<span style=color:#6B7482;font-size:11px;>No data</span>"}</div>',
        f'</div>',
        f'</div></div>',
    ]
    st.markdown("".join(snap_parts), unsafe_allow_html=True)

    # ── 4. EXECUTIVE KPIs ─────────────────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:{DT["text_muted"]};margin-bottom:8px;">EXECUTIVE KPIs</div>',
        unsafe_allow_html=True
    )

    def _kc(col_obj, label, value, sub, tone="neutral"):
        _tc = {"success": DT["success"], "danger": DT["danger"],
               "warning": DT["warning"], "neutral": DT["text_muted"]}
        sc = _tc.get(tone, DT["text_muted"])
        col_obj.markdown(
            f'<div style="background:{DT["card"]};border:1px solid {DT["border"]};'
            f'border-radius:{DT["radius_card"]};padding:16px 16px;">'
            f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;'
            f'color:{DT["text_muted"]};margin-bottom:8px;">{label}</div>'
            f'<div style="font-size:20px;font-weight:700;color:{DT["text_primary"]};'
            f'font-variant-numeric:tabular-nums;letter-spacing:-0.01em;margin-bottom:4px;">{value}</div>'
            f'<div style="font-size:11px;color:{sc};font-weight:500;">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    _k1, _k2, _k3, _k4, _k5 = st.columns(5)
    _od_pct = (_od30 / _tot_out * 100) if _tot_out > 0 else 0
    _kc(_k1, "Total Outstanding", fmt_inr(_tot_out), f"{_active_p} active parties", "danger")
    _kc(_k2, "Active Parties", f"{_active_p:,}", f"{len(cust_df):,} total customers", "neutral")
    _kc(_k3, "Overdue &gt; 30 Days", fmt_inr(_od30), f"{_od_pct:.0f}% of receivables &middot; account-level ageing", "danger")
    _kc(_k4, "High-Risk Customers", f"{_hi_risk:,}", f"{_wo_cnt} write-off risk", "danger" if _hi_risk > 0 else "neutral")
    _kc(_k5, "Stockout Risks", f"{_stockout:,}", "SKUs at/below reorder level", "warning" if _stockout > 0 else "success")

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── 5. CEO MORNING BRIEFING ───────────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:{DT["text_muted"]};margin-bottom:8px;">&#9728;&#65039; CEO MORNING BRIEFING</div>',
        unsafe_allow_html=True
    )

    _top_def = col_summary.get("top_defaulter", "—")
    _top_da  = col_summary.get("top_defaulter_amount", 0)
    _rec_p   = col_summary.get("recovery_probability_pct", 0)
    _hira    = col_summary.get("high_risk_amount", 0)
    _dc      = int((dead_stock_df["stock_status"] == "DEAD").sum()) if not dead_stock_df.empty and "stock_status" in dead_stock_df.columns else 0
    _dcap    = float(dead_stock_df.loc[dead_stock_df["stock_status"] == "DEAD", "capital_blocked"].sum()) if not dead_stock_df.empty and "capital_blocked" in dead_stock_df.columns else 0.0
    _ta      = area_df.iloc[0]["customer_area"] if not area_df.empty else "—"
    _tar     = area_df.iloc[0]["total_revenue"] if not area_df.empty else 0
    _ba      = area_df.iloc[-1]["customer_area"] if not area_df.empty and len(area_df) > 1 else "—"

    def _bc(icon, title, headline, body, nav, tc):
        return (
            f'<div style="background:{DT["card"]};border:1px solid {DT["border"]};'
            f'border-left:3px solid {tc};border-radius:{DT["radius_card"]};'
            f'padding:16px 18px;box-sizing:border-box;">'
            f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;'
            f'color:{tc};margin-bottom:6px;">{icon} {title}</div>'
            f'<div style="font-size:13px;font-weight:600;color:{DT["text_primary"]};'
            f'line-height:1.4;margin-bottom:6px;">{headline}</div>'
            f'<div style="font-size:12px;color:{DT["text_secondary"]};line-height:1.65;'
            f'margin-bottom:12px;">{body}</div>'
            f'<div style="font-size:10px;font-weight:500;color:{DT["link"]};">&#8594; {nav}</div>'
            f'</div>'
        )

    _br1, _br2 = st.columns(2)
    _br3, _br4 = st.columns(2)

    with _br1:
        st.markdown(_bc(
            "&#x1F4B3;", "Cash Recovery",
            f"{fmt_inr(_od30)} overdue for more than 30 days",
            f"{_hi_risk} high-risk accounts hold {fmt_inr(_hira)} at risk. "
            f"Top priority: <b>{_top_def}</b> ({fmt_inr(_top_da)}). Recovery probability: {_rec_p:.0f}%.",
            "Open Revenue Recovery &amp; Risk", DT["danger"]
        ), unsafe_allow_html=True)

    with _br2:
        _ih = f"{_stockout} SKUs at or below reorder level" if _stockout > 0 else "Inventory levels are healthy across all SKUs"
        _ib = "Immediate restocking required to prevent lost sales." if _stockout > 0 else f"No SKUs below reorder. Total inventory value: {fmt_inr(_inv_val)}."
        st.markdown(_bc("&#x1F4E6;", "Inventory", _ih, _ib, "Open Inventory &amp; Operations", DT["warning"]), unsafe_allow_html=True)

    with _br3:
        _wh = f"{fmt_inr(_dcap)} locked in {_dc} dead-stock SKUs" if _dc > 0 else "No dead stock detected — all SKUs are actively selling"
        _wb = "Consider clearance to free working capital." if _dc > 0 else f"All {len(inv_df)} SKUs show recent sales. Inventory value: {fmt_inr(_inv_val)}."
        st.markdown(_bc("&#x1F4B0;", "Working Capital", _wh, _wb, "Open Inventory &amp; Operations", DT["gold"]), unsafe_allow_html=True)

    with _br4:
        _th = f"{_ta} leads with {fmt_inr(_tar)} in revenue" if not area_df.empty else "Territory data unavailable"
        _tb = (f"Serving {len(_top_towns)} territories. {_ba} is the lowest-performing — consider targeted activity."
               if not area_df.empty else "No geographic breakdown available.")
        st.markdown(_bc("&#x1F5FA;&#xFE0F;", "Territory", _th, _tb, "Open Customer Intelligence", DT["info"]), unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── 6. TODAY'S PRIORITY ACTIONS ───────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:{DT["text_muted"]};margin-bottom:8px;">&#x1F525; TODAY\'S PRIORITY ACTIONS</div>',
        unsafe_allow_html=True
    )

    # Priority and category are SEPARATE — priority is NEVER passed to filter_by_category()
    _DMAP = {
        "Payment":   "&#x1F4B3; Revenue Recovery &amp; Risk",
        "Inventory": "&#x1F4E6; Inventory &amp; Operations",
        "Customer":  "&#x1F465; Customer Intelligence",
        "Sales":     "&#x1F4E6; Inventory &amp; Operations",
        "Anomaly":   "&#x26A1; Command Center",
    }
    _PCOL = {
        "HIGH":   DT["danger"],
        "MEDIUM": DT["warning"],
        "LOW":    DT["success"],
    }

    # Sort by urgency descending, deduplicate by customer/title to limit per-invoice noise
    _seen_titles = set()
    _drecs = []
    for _r in sorted(all_recs, key=lambda r: r.urgency_score, reverse=True):
        _key = _r.title[:40]
        if _key not in _seen_titles:
            _seen_titles.add(_key)
            _drecs.append(_r)
        if len(_drecs) >= 6:
            break

    if not _drecs:
        render_success_state("No priority actions today — all business metrics are within normal range.")
    else:
        for _r in _drecs:
            _pc  = _PCOL.get(_r.priority, DT["text_muted"])
            _dst = _DMAP.get(_r.category, "&#x26A1; Command Center")
            st.markdown(
                f'<div style="background:{DT["card"]};border:1px solid {DT["border"]};'
                f'border-left:3px solid {_pc};border-radius:{DT["radius_card"]};'
                f'padding:13px 18px;margin-bottom:8px;'
                f'display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:center;">'
                f'<div><span style="font-size:9px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:0.07em;padding:2px 7px;border-radius:999px;'
                f'background:{_pc}22;color:{_pc};">{_r.priority}</span></div>'
                f'<div>'
                f'<div style="font-size:13px;font-weight:600;color:{DT["text_primary"]};margin-bottom:2px;">{_r.title}</div>'
                f'<div style="font-size:11px;color:{DT["text_secondary"]};line-height:1.5;">{_r.message[:160]}{"…" if len(_r.message)>160 else ""}</div>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<div style="font-size:13px;font-weight:700;color:{DT["success"]};font-variant-numeric:tabular-nums;">{fmt_inr(_r.impact_rupees)}</div>'
                f'<div style="font-size:10px;color:{DT["link"]};margin-top:3px;">&#8594; {_dst}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── 7. BUSINESS TRENDS — 3 compact cards ─────────────────────────────────
    st.markdown(
        f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:{DT["text_muted"]};margin-bottom:8px;">BUSINESS TRENDS</div>',
        unsafe_allow_html=True
    )

    _tr1, _tr2, _tr3 = st.columns(3)
    _pb = dict(margin=dict(l=0, r=0, t=0, b=0), height=155,
               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")

    def _tch(co, title, sub):
        co.markdown(
            f'<div style="background:{DT["card"]};border:1px solid {DT["border"]};'
            f'border-radius:{DT["radius_card"]};padding:12px 14px 4px;margin-bottom:-4px;">'
            f'<div style="font-size:12px;font-weight:600;color:{DT["text_primary"]};margin-bottom:1px;">{title}</div>'
            f'<div style="font-size:10px;color:{DT["text_muted"]};">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with _tr1:
        _tch(_tr1, "Monthly Revenue", "24-month rolling")
        if not trend_df.empty and "year_month" in trend_df.columns:
            _f = px.area(trend_df, x="year_month", y="total_revenue",
                         labels={"year_month": "", "total_revenue": "&#8377;"},
                         template=PLOTLY_TEMPLATE, color_discrete_sequence=[DT["accent"]])
            _f.update_layout(**_pb,
                             xaxis=dict(showgrid=False, color=DT["text_muted"], tickfont_size=9),
                             yaxis=dict(showgrid=True, gridcolor=DT["border"], color=DT["text_muted"], tickfont_size=9))
            st.plotly_chart(_f, use_container_width=True)
        else:
            render_unavailable_state("Monthly Revenue chart", "Not enough data.")

    with _tr2:
        _tch(_tr2, "Receivables by Ageing", "Invoice ageing breakdown")
        if not outstanding_df.empty and "days_overdue" in outstanding_df.columns and "outstanding_amount" in outstanding_df.columns:
            _ad = outstanding_df.copy()
            _ad["band"] = pd.cut(_ad["days_overdue"].clip(lower=0),
                                 bins=[0, 30, 60, 90, float("inf")],
                                 labels=["0-30d", "31-60d", "61-90d", ">90d"], right=False)
            _as = _ad.groupby("band", observed=True)["outstanding_amount"].sum().reset_index()
            _as.columns = ["Age", "Amount"]
            _f2 = px.bar(_as, x="Age", y="Amount", template=PLOTLY_TEMPLATE,
                         labels={"Age": "", "Amount": "&#8377;"},
                         color_discrete_sequence=[DT["danger"]])
            _f2.update_layout(**_pb,
                              xaxis=dict(showgrid=False, color=DT["text_muted"], tickfont_size=9),
                              yaxis=dict(showgrid=True, gridcolor=DT["border"], color=DT["text_muted"], tickfont_size=9))
            st.plotly_chart(_f2, use_container_width=True)
        else:
            render_unavailable_state("Receivables chart", "No receivable data.")

    with _tr3:
        _tch(_tr3, "Sales by Town", "Territory revenue ranking")
        if not area_df.empty:
            _ap = area_df.head(8).sort_values("total_revenue", ascending=True)
            _f3 = px.bar(_ap, y="customer_area", x="total_revenue", orientation="h",
                         labels={"customer_area": "", "total_revenue": "&#8377;"},
                         template=PLOTLY_TEMPLATE, color_discrete_sequence=[DT["link"]])
            _f3.update_layout(**_pb,
                              xaxis=dict(showgrid=True, gridcolor=DT["border"], color=DT["text_muted"], tickfont_size=9),
                              yaxis=dict(showgrid=False, color=DT["text_muted"], tickfont_size=9))
            st.plotly_chart(_f3, use_container_width=True)
        else:
            render_unavailable_state("Territory chart", "No territory data.")


elif page == "\U0001f4b3 Revenue Recovery & Risk":
    from engine.recovery_engine import (
        build_recovery_batch, choose_intervention, execute_recovery_action, simulate_payment_outcome,
        RecoveryState, CustomerRecoveryRecord, INTERVENTION_POLICY, _VALID_TRANSITIONS,
        generate_mock_payment_link, calculate_recovery_priority
    )
    from engine.payment_intelligence import generate_collection_message, score_payment_risk
    from engine.audit_logger import get_audit_log, log_event
    from datetime import datetime
    from pathlib import Path as _RRPath
    import hashlib

    if "sales_df" not in st.session_state:
        render_empty_state("\U0001f50c", "Awaiting Data Connection", "Please load the demo data first in the Command Center.")
        st.stop()

    render_page_header("REVENUE OPERATIONS", "\U0001f4b3 Revenue Recovery & Risk", "Prioritize overdue receivables, take bounded collection actions, and track recovery.")

    st.markdown('''
<div style="background:rgba(255,193,7,0.1); border:1px solid rgba(255,193,7,0.4); padding:6px 12px; border-radius:4px; font-size:11px; color:#D97706; font-weight:600; display:inline-block; margin-bottom:20px;" title="Payment links and recovery outcomes are simulated for demonstration. No real payment is processed.">
  DEMO MODE &middot; MOCK PAYMENTS
</div>
    ''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # A. LOAD RECEIVABLES AS SOURCE OF TRUTH
    # ═══════════════════════════════════════════════════════════════════════
    _recv_path = _RRPath(__file__).resolve().parent.parent / "data" / "raw" / "receivables.csv"
    _cm_path   = _RRPath(__file__).resolve().parent.parent / "data" / "raw" / "customer_master.csv"

    @st.cache_data(show_spinner="Loading receivables ledger...")
    def _load_receivables():
        recv = pd.read_csv(_recv_path)
        recv["outstanding_amount"] = pd.to_numeric(recv["outstanding_amount"], errors="coerce").fillna(0)
        recv["bill_amount"]        = pd.to_numeric(recv["bill_amount"], errors="coerce").fillna(0)
        recv["amount_received"]    = pd.to_numeric(recv["amount_received"], errors="coerce").fillna(0)
        recv["days_overdue"]       = pd.to_numeric(recv["days_overdue"], errors="coerce").fillna(0).astype(int)
        # Load customer master for town mapping
        cm = pd.read_csv(_cm_path) if _cm_path.exists() else pd.DataFrame()
        return recv, cm

    if not _recv_path.exists():
        st.error("Receivables data not found. Please ensure data/raw/receivables.csv exists.")
        st.stop()

    recv_df, cm_df = _load_receivables()

    # Build customer-level recovery dataset from invoice-level records
    unpaid_invoices = recv_df[recv_df["outstanding_amount"] > 0].copy()

    if unpaid_invoices.empty:
        st.info("All invoices are fully paid. No receivables outstanding.")
        st.stop()

    cust_recv = unpaid_invoices.groupby(["customer_id", "party_name"]).agg(
        total_outstanding=("outstanding_amount", "sum"),
        unpaid_invoice_count=("voucher_no", "nunique"),
        max_days_overdue=("days_overdue", "max"),
        oldest_due_date=("due_date", "min"),
        overdue_amount=("outstanding_amount", lambda x: x[unpaid_invoices.loc[x.index, "days_overdue"] > 0].sum()),
        total_billed=("bill_amount", "sum"),
        total_received=("amount_received", "sum"),
    ).reset_index()

    # Join town from customer master
    if not cm_df.empty and "party_name" in cm_df.columns and "city" in cm_df.columns:
        town_map = cm_df[["party_name", "city"]].drop_duplicates("party_name").rename(columns={"city": "Town"})
        cust_recv = cust_recv.merge(town_map, on="party_name", how="left")
    else:
        cust_recv["Town"] = "\u2014"
    cust_recv["Town"] = cust_recv["Town"].fillna("\u2014")
    cust_recv["Beat"] = "\u2014"

    # ═══════════════════════════════════════════════════════════════════════
    # B. RISK SCORING (reuse existing ML/rule-based engine on receivables)
    # ═══════════════════════════════════════════════════════════════════════
    # Build a lightweight risk assessment using rule-based scoring on receivables data
    import numpy as np

    def _assign_risk(row):
        days = row["max_days_overdue"]
        amount = row["total_outstanding"]
        score = 80.0
        if days > 120:   score -= 45
        elif days > 90:  score -= 30
        elif days > 60:  score -= 20
        elif days > 30:  score -= 10
        if amount > 50000: score -= 10
        elif amount > 20000: score -= 5
        prob = max(0, min(100, score))
        if prob >= 75:
            tier, action = "LOW RISK", "Routine Follow-up"
        elif prob >= 55:
            tier, action = "MEDIUM RISK", "Call Today"
        elif prob >= 35:
            if days > 90:
                tier, action = "HIGH RISK", "Personal Visit"
            else:
                tier, action = "HIGH RISK", "Call Today"
        else:
            if days > 120:
                tier, action = "WRITE-OFF RISK", "Legal Notice"
            else:
                tier, action = "HIGH RISK", "Personal Visit"
        return pd.Series({"collection_probability": prob, "risk_tier": tier, "recommended_action": action})

    risk_cols = cust_recv.apply(_assign_risk, axis=1)
    cust_recv = pd.concat([cust_recv, risk_cols], axis=1)
    cust_recv["expected_recovery"] = (cust_recv["total_outstanding"] * cust_recv["collection_probability"] / 100.0).round(2)
    cust_recv["priority_score"] = cust_recv.apply(
        lambda r: calculate_recovery_priority(r["total_outstanding"], r["collection_probability"], r["max_days_overdue"]), axis=1
    )
    cust_recv = cust_recv.sort_values("priority_score", ascending=False).reset_index(drop=True)

    # ═══════════════════════════════════════════════════════════════════════
    # C. BUILD RECOVERY RECORDS (session-persisted)
    # ═══════════════════════════════════════════════════════════════════════
    if "ledger_records" not in st.session_state or st.session_state.get("_recv_source") != "receivables_csv":
        records_dict = {}
        for _, row in cust_recv.iterrows():
            rec = CustomerRecoveryRecord(
                customer_name=row["party_name"],
                outstanding_amount=round(float(row["total_outstanding"]), 2),
                collection_probability=float(row["collection_probability"]),
                risk_tier=row["risk_tier"],
                days_overdue=float(row["max_days_overdue"]),
            )
            rec.priority_score = float(row["priority_score"])
            rec.expected_recovery = round(rec.outstanding_amount * (rec.collection_probability / 100.0), 2)
            records_dict[rec.customer_name] = rec
        st.session_state["ledger_records"] = records_dict
        st.session_state["_recv_source"] = "receivables_csv"

    records_dict = st.session_state["ledger_records"]
    all_recs = list(records_dict.values())

    # ═══════════════════════════════════════════════════════════════════════
    # D. RECONCILIATION CHECK
    # ═══════════════════════════════════════════════════════════════════════
    _total_inv_outstanding = unpaid_invoices["outstanding_amount"].sum()
    _total_cust_outstanding = cust_recv["total_outstanding"].sum()
    _recon_ok = abs(_total_inv_outstanding - _total_cust_outstanding) < 1.0

    # ═══════════════════════════════════════════════════════════════════════
    # E. HERO KPIs
    # ═══════════════════════════════════════════════════════════════════════
    _tot_out = _total_cust_outstanding
    _od30 = cust_recv.loc[cust_recv["max_days_overdue"] > 30, "total_outstanding"].sum()
    _at_risk_mask = cust_recv["max_days_overdue"] >= 45
    _at_risk_amt = cust_recv.loc[_at_risk_mask, "total_outstanding"].sum()
    _at_risk_cnt = int(_at_risk_mask.sum())
    exp_rec = sum(r.expected_recovery for r in all_recs)
    act_rec = sum(r.amount_recovered for r in all_recs)
    _remaining = max(0, _tot_out - act_rec)
    _rec_rate = round((act_rec / _tot_out * 100), 1) if _tot_out > 0 else 0.0

    # KPI strip
    k1, k2, k3, k4, k5 = st.columns(5)

    def _k(col, lbl, val, sub="", tc="neutral"):
        _c = DESIGN_TOKENS.get(tc, DESIGN_TOKENS["text_primary"])
        _sub_html = f'<div style="font-size:11px;color:{DESIGN_TOKENS["text_muted"]};margin-top:4px;">{sub}</div>' if sub else ''
        col.markdown(f'''
        <div style="background:{DESIGN_TOKENS['card']};border:1px solid {DESIGN_TOKENS['border']};border-radius:{DESIGN_TOKENS['radius_card']};padding:14px;">
            <div style="font-size:10px;font-weight:600;text-transform:uppercase;color:{DESIGN_TOKENS['text_muted']};margin-bottom:6px;">{lbl}</div>
            <div style="font-size:18px;font-weight:700;color:{_c};font-variant-numeric:tabular-nums;letter-spacing:-0.01em;">{val}</div>
            {_sub_html}
        </div>
        ''', unsafe_allow_html=True)

    _k(k1, "Total Outstanding", fmt_inr(_tot_out), tc="text_primary")
    _k(k2, "Overdue >30D", fmt_inr(_od30), tc="danger")
    _k(k3, "At Risk \u226545D", fmt_inr(_at_risk_amt), sub=f"{_at_risk_cnt} customers", tc="warning")
    _k(k4, "Expected Recovery", fmt_inr(exp_rec), tc="text_primary")
    _k(k5, "Amount Recovered", fmt_inr(act_rec), tc="success")

    # Recovery Rate + Remaining Outstanding
    rr1, rr2, rr3 = st.columns(3)
    _k(rr1, "Recovery Rate", f"{_rec_rate:.1f}%", tc="success" if _rec_rate > 0 else "text_primary")
    _k(rr2, "Remaining Outstanding", fmt_inr(_remaining), tc="danger" if _remaining > 0 else "success")
    if not _recon_ok:
        rr3.warning(f"\u26a0\ufe0f Reconciliation mismatch: Invoice sum \u2260 Customer sum (diff: {abs(_total_inv_outstanding - _total_cust_outstanding):,.0f})")
    else:
        _k(rr3, "Reconciliation", "\u2705 Verified", sub=f"{len(cust_recv)} customers, {len(unpaid_invoices)} invoices", tc="success")

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # Attention Required
    hold_states = ["WAITING_FOR_PAYMENT", "ESCALATED", "RECOVERED", "STOPPED"]
    on_hold = [r for r in all_recs if (r.state.value if hasattr(r.state, "value") else str(r.state)) in hold_states]
    if on_hold:
        st.markdown(f"<div style='padding:12px; border-left:3px solid {DESIGN_TOKENS['warning']}; background:{DESIGN_TOKENS['card_elevated']}; margin-bottom:20px; font-size:13px;'><b>\U0001f6d1 Attention Required:</b> {len(on_hold)} accounts are currently waiting for payment, escalated, or stopped. Do not repeatedly contact them without reviewing their state.</div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # F. COLLECTION LEDGER
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### \U0001f4cb Collection Ledger")

    data = []
    for r in all_recs:
        st_val = r.state.value if hasattr(r.state, 'value') else str(r.state)
        cust_row = cust_recv[cust_recv["party_name"] == r.customer_name]
        town = cust_row["Town"].iloc[0] if not cust_row.empty else "\u2014"
        unpaid_ct = int(cust_row["unpaid_invoice_count"].iloc[0]) if not cust_row.empty else 0
        data.append({
            "Customer": r.customer_name,
            "Town": town,
            "Beat": "\u2014",
            "Outstanding": r.outstanding_amount,
            "Unpaid Bills": unpaid_ct,
            "Days Overdue": int(r.days_overdue),
            "Risk": r.risk_tier,
            "Probability": r.collection_probability,
            "Expected Recovery": r.expected_recovery,
            "State": st_val,
        })
    df_ledger = pd.DataFrame(data)

    f1, f2, f3, f4 = st.columns(4)
    sel_town = f1.multiselect("Town", sorted(df_ledger["Town"].unique())) if not df_ledger.empty else []
    sel_risk = f2.multiselect("Risk Tier", sorted(df_ledger["Risk"].unique())) if not df_ledger.empty else []
    sel_state = f3.multiselect("Recovery State", sorted(df_ledger["State"].unique())) if not df_ledger.empty else []
    sel_age_opts = ["1\u201330 days", "31\u201360 days", "61\u201390 days", "90+ days"]
    sel_age = f4.multiselect("Overdue Range", sel_age_opts)

    df_filtered = df_ledger.copy()
    if not df_filtered.empty:
        if sel_town:  df_filtered = df_filtered[df_filtered["Town"].isin(sel_town)]
        if sel_risk:  df_filtered = df_filtered[df_filtered["Risk"].isin(sel_risk)]
        if sel_state: df_filtered = df_filtered[df_filtered["State"].isin(sel_state)]
        if sel_age:
            def _in_age_range(d):
                if d <= 0: return False
                if "1\u201330 days" in sel_age and 1 <= d <= 30: return True
                if "31\u201360 days" in sel_age and 31 <= d <= 60: return True
                if "61\u201390 days" in sel_age and 61 <= d <= 90: return True
                if "90+ days" in sel_age and d > 90: return True
                return False
            df_filtered = df_filtered[df_filtered["Days Overdue"].apply(_in_age_range)]

        event = st.dataframe(
            df_filtered[["Customer", "Town", "Beat", "Outstanding", "Unpaid Bills", "Days Overdue", "Risk", "Probability", "Expected Recovery", "State"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row"
        )

        sel_indices = event.selection.rows
        sel_customers = df_filtered.iloc[sel_indices]["Customer"].tolist() if sel_indices else []
    else:
        st.info("No records found matching filters.")
        sel_customers = []

    # ═══════════════════════════════════════════════════════════════════════
    # G. CUSTOMER DETAIL + ACTIONS
    # ═══════════════════════════════════════════════════════════════════════
    if sel_customers:
        sel_out = sum(records_dict[c].outstanding_amount for c in sel_customers if c in records_dict)
        st.markdown(f"**Selected {len(sel_customers)} customer{'s' if len(sel_customers) > 1 else ''} (Total Outstanding: {fmt_inr(sel_out)})**")

        action = st.session_state.get("rr_bulk_action")
        st.markdown("---")

        if len(sel_customers) == 1:
            rec = records_dict[sel_customers[0]]
            cust_row = cust_recv[cust_recv["party_name"] == rec.customer_name]
            rec_action = cust_row["recommended_action"].iloc[0] if not cust_row.empty and "recommended_action" in cust_row.columns else "Call Today"

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"### \U0001f50d Customer Detail: {rec.customer_name}")

                # Customer summary
                _town = cust_row["Town"].iloc[0] if not cust_row.empty else "\u2014"
                st.markdown(f"**Town:** {_town} &nbsp; | &nbsp; **Beat:** \u2014")
                st.markdown(f"""
| Metric | Value |
|---|---|
| **Total Outstanding** | {fmt_inr(rec.outstanding_amount)} |
| **Unpaid Bills** | {int(cust_row['unpaid_invoice_count'].iloc[0]) if not cust_row.empty else 0} |
| **Max Days Overdue** | {int(rec.days_overdue)} |
| **Risk Tier** | {rec.risk_tier} |
| **Collection Probability** | {rec.collection_probability:.0f}% |
| **Expected Recovery** | {fmt_inr(rec.expected_recovery)} |
| **Recommended Action** | {rec_action} |
""")

            with c2:
                st.markdown("### \u26a1 Recovery State")
                c_st = rec.state.value if hasattr(rec.state, 'value') else str(rec.state)
                st.markdown(f"**Current State:** `{c_st}`")
                valid_next = [s.value if hasattr(s, 'value') else str(s) for s in _VALID_TRANSITIONS.get(rec.state, [])]
                if valid_next:
                    st.caption(f"Allowed next: {', '.join(valid_next)}")
                else:
                    st.caption("No further states allowed (Terminal).")

                if rec.amount_recovered > 0:
                    st.success(f"\u2705 Recovered: {fmt_inr(rec.amount_recovered)}")

                st.markdown("---")
                st.markdown("**\U0001f4ac Communication**")
                btn1, btn2 = st.columns(2)
                if btn1.button("\U0001f517 Generate Demo Payment Link", key="rr_link_single"):
                    st.session_state["rr_bulk_action"] = "links"
                    st.rerun()
                if btn2.button("\U0001f4f1 Generate WhatsApp Draft", key="rr_wa_single"):
                    st.session_state["rr_bulk_action"] = "whatsapp"
                    st.rerun()

                st.markdown("---")
                if valid_next:
                    if st.button("\u25b6\ufe0f Advance Allowed Recovery State", type="primary", key="rr_advance_single"):
                        execute_recovery_action(rec, "manual_ledger")
                        simulate_payment_outcome(rec, datetime.now().isoformat())
                        st.session_state["rr_bulk_action"] = None
                        st.rerun()

            # Full Unpaid Invoice List
            st.markdown("### \U0001f4c4 Unpaid Invoice List")
            cust_invoices = unpaid_invoices[unpaid_invoices["party_name"] == rec.customer_name].copy()
            if not cust_invoices.empty:
                cust_invoices = cust_invoices.sort_values("days_overdue", ascending=False)
                inv_display = cust_invoices[["voucher_no", "voucher_date", "due_date", "bill_amount", "amount_received", "outstanding_amount", "days_overdue", "ageing_bucket", "status"]].copy()
                inv_display.columns = ["Invoice No", "Invoice Date", "Due Date", "Bill Amount", "Received", "Outstanding", "Days Overdue", "Ageing", "Status"]
                st.dataframe(inv_display, use_container_width=True, hide_index=True)

                # Reconciliation validation
                inv_total = cust_invoices["outstanding_amount"].sum()
                if abs(inv_total - rec.outstanding_amount) > 1.0:
                    st.warning(f"\u26a0\ufe0f Invoice total ({fmt_inr(inv_total)}) differs from customer record ({fmt_inr(rec.outstanding_amount)})")
                else:
                    st.caption(f"\u2705 Invoice outstanding reconciles with customer total: {fmt_inr(inv_total)}")
            else:
                st.caption("No unpaid invoices found for this customer.")

            # Render communication drafts
            if action == "links":
                st.markdown("---")
                plink = generate_mock_payment_link(rec.customer_name, rec.outstanding_amount)
                st.markdown("**\U0001f517 Mock Razorpay Payment Link (DEMO ONLY)**")
                st.code(f"{plink}", language="text")
                st.caption(f"Amount: {fmt_inr(rec.outstanding_amount)} \u2014 This is a DEMO link. No real payment is processed.")
            elif action == "whatsapp":
                st.markdown("---")
                plink = generate_mock_payment_link(rec.customer_name, rec.outstanding_amount)
                msg = generate_collection_message(
                    rec.customer_name, rec.outstanding_amount, int(rec.days_overdue),
                    rec_action, payment_link=plink
                )
                st.markdown("**\U0001f4f1 WhatsApp Draft**")
                st.code(msg, language="text")

        else:
            # ── Bulk Mode ──
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### \U0001f4ac Bulk Communication")
                btn1, btn2 = st.columns(2)
                if btn1.button("\U0001f517 Generate Demo Payment Links", key="rr_link_bulk"):
                    st.session_state["rr_bulk_action"] = "links"
                    st.rerun()
                if btn2.button("\U0001f4f1 Generate WhatsApp Drafts", key="rr_wa_bulk"):
                    st.session_state["rr_bulk_action"] = "whatsapp"
                    st.rerun()
            with c2:
                st.markdown("### \u26a1 Recovery State")
                if st.button("\u25b6\ufe0f Advance Recovery State for Selected", type="primary", use_container_width=True, key="rr_advance_bulk"):
                    for c_name in sel_customers:
                        rec = records_dict[c_name]
                        execute_recovery_action(rec, "manual_ledger")
                        simulate_payment_outcome(rec, datetime.now().isoformat())
                    st.session_state["rr_bulk_action"] = None
                    st.rerun()

            if action:
                st.markdown("---")
                st.markdown(f"### \U0001f4cb Bulk Action Results ({len(sel_customers)} customers)")
                with st.expander("View Generated Items", expanded=True):
                    for c_name in sel_customers:
                        rec = records_dict[c_name]
                        if action == "links":
                            plink = generate_mock_payment_link(rec.customer_name, rec.outstanding_amount)
                            st.markdown(f"**{rec.customer_name}** \u2014 {fmt_inr(rec.outstanding_amount)}")
                            st.code(f"{plink}  (DEMO ONLY / MOCK PAYMENT)", language="text")
                        elif action == "whatsapp":
                            plink = generate_mock_payment_link(rec.customer_name, rec.outstanding_amount)
                            cust_row_b = cust_recv[cust_recv["party_name"] == rec.customer_name]
                            rec_action_b = cust_row_b["recommended_action"].iloc[0] if not cust_row_b.empty and "recommended_action" in cust_row_b.columns else "Call Today"
                            msg = generate_collection_message(
                                rec.customer_name, rec.outstanding_amount, int(rec.days_overdue),
                                rec_action_b, payment_link=plink
                            )
                            st.markdown(f"**{rec.customer_name}**")
                            st.text(msg)
                            st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # H. RECOVERY OUTCOME
    # ═══════════════════════════════════════════════════════════════════════
    _any_recovered = any(r.amount_recovered > 0 for r in all_recs)
    if _any_recovered:
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown("### \U0001f4b0 Recovery Outcome")
        _amt_targeted = sum(r.outstanding_amount for r in all_recs)
        _amt_recovered = sum(r.amount_recovered for r in all_recs)
        _amt_remaining = max(0, _amt_targeted - _amt_recovered)
        _rate = round((_amt_recovered / _amt_targeted * 100), 1) if _amt_targeted > 0 else 0.0
        _n_recovered = sum(1 for r in all_recs if r.state == RecoveryState.RECOVERED)
        _n_escalated = sum(1 for r in all_recs if r.state == RecoveryState.ESCALATED)
        _n_waiting   = sum(1 for r in all_recs if r.state == RecoveryState.WAITING_FOR_PAYMENT)

        # Safety checks
        if _amt_recovered > _amt_targeted:
            st.error(f"\u26a0\ufe0f Data integrity: Recovered ({fmt_inr(_amt_recovered)}) exceeds targeted ({fmt_inr(_amt_targeted)})")
        if _rate > 100:
            _rate = 100.0

        o1, o2, o3, o4 = st.columns(4)
        _k(o1, "Amount Targeted", fmt_inr(_amt_targeted), tc="text_primary")
        _k(o2, "Amount Recovered", fmt_inr(_amt_recovered), sub=f"{_n_recovered} customers", tc="success")
        _k(o3, "Remaining Outstanding", fmt_inr(_amt_remaining), tc="danger" if _amt_remaining > 0 else "success")
        _k(o4, "Recovery Rate", f"{_rate:.1f}%", sub=f"{_n_escalated} escalated, {_n_waiting} waiting", tc="success" if _rate > 0 else "text_primary")

    # ═══════════════════════════════════════════════════════════════════════
    # I. IMMUTABLE LEDGER
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.markdown("### \U0001f510 Immutable Ledger")
    audits = get_audit_log()
    if not audits.empty:
        adf = audits.copy()
        adf["timestamp"] = pd.to_datetime(adf["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        disp = adf[["timestamp", "event_type", "customer_name", "action", "new_state", "reason"]].copy()
        disp.columns = ["Timestamp", "Event", "Customer", "Action", "State", "Reason"]
        st.dataframe(disp.sort_values("Timestamp", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.caption("No recovery events recorded yet. Advance a recovery state to begin logging.")



elif page == "📦 Inventory & Operations":
    from engine.analytics import detect_dead_stock as _dds2
    from engine.analytics import calculate_margins, category_month_heatmap

    if "sales_df" not in st.session_state or "inv_df" not in st.session_state:
        st.warning("Please load data first — go to ⚡ Command Center and click 'Load Demo Data'."); st.stop()

    render_page_header("INVENTORY & SALES", "📦 Inventory & Operations", "Optimize stock levels, prevent stockouts, and monitor operational performance.")
    
    sales_df = st.session_state["sales_df"]
    inv_df = st.session_state["inv_df"]
    
    # ── 1. Inventory Overview (KPI Strip) ────────────────────────────────────
    inv_val = (inv_df["current_stock"].fillna(0) * inv_df["purchase_price"].fillna(0)).sum()
    total_skus = len(inv_df)
    
    dead_stock_df = _dds2(inv_df)
    active = (dead_stock_df["stock_status"] == "ACTIVE").sum() if not dead_stock_df.empty else 0
    slow = (dead_stock_df["stock_status"] == "SLOW").sum() if not dead_stock_df.empty else 0
    dead = (dead_stock_df["stock_status"] == "DEAD").sum() if not dead_stock_df.empty else 0
    dead_blocked = dead_stock_df.loc[dead_stock_df["stock_status"] == "DEAD", "capital_blocked"].sum() if not dead_stock_df.empty else 0
    
    low_stock = inv_df[inv_df["current_stock"] <= inv_df["reorder_level"]].copy() if "reorder_level" in inv_df.columns else pd.DataFrame()
    stockout_cnt = len(low_stock)
    
    k1, k2, k3, k4, k5 = st.columns(5)
    def _k(col, lbl, val, sub="", tc="neutral"):
        _c = DESIGN_TOKENS.get(tc, DESIGN_TOKENS["text_primary"])
        _sub_html = f'<div style="font-size:11px;color:{DESIGN_TOKENS["text_muted"]};margin-top:4px;">{sub}</div>' if sub else ''
        col.markdown(f'''
        <div style="background:{DESIGN_TOKENS['card']};border:1px solid {DESIGN_TOKENS['border']};border-radius:{DESIGN_TOKENS['radius_card']};padding:14px;">
            <div style="font-size:10px;font-weight:600;text-transform:uppercase;color:{DESIGN_TOKENS['text_muted']};margin-bottom:6px;">{lbl}</div>
            <div style="font-size:18px;font-weight:700;color:{_c};font-variant-numeric:tabular-nums;letter-spacing:-0.01em;">{val}</div>
            {_sub_html}
        </div>
        ''', unsafe_allow_html=True)
        
    _k(k1, "Inventory Value", fmt_inr(inv_val), "Total capital", tc="text_primary")
    _k(k2, "Active SKUs", f"{active:,}", f"out of {total_skus:,} total", tc="success")
    _k(k3, "Stockout Risk", f"{stockout_cnt:,}", "At/below reorder level", tc="danger" if stockout_cnt > 0 else "success")
    _k(k4, "Dead Stock SKUs", f"{dead:,}", f"Blocked: {fmt_inr(dead_blocked)}", tc="warning" if dead > 0 else "success")
    _k(k5, "Slow Moving SKUs", f"{slow:,}", "Needs liquidation", tc="neutral")
    
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── 2. NOW: Inventory Health & Stockout Risk ─────────────────────────────
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("### 🩺 Inventory Health")
        if not dead_stock_df.empty:
            st.markdown(f"**{active}** Active SKUs &nbsp;&middot;&nbsp; **{slow}** Slow-Moving &nbsp;&middot;&nbsp; **{dead}** Dead SKUs")
            
            cat_blocked = dead_stock_df.groupby("category")["capital_blocked"].sum().reset_index()
            cat_blocked = cat_blocked[cat_blocked["capital_blocked"] > 0]
            if not cat_blocked.empty:
                import plotly.express as px
                fig2 = px.pie(
                    cat_blocked, values="capital_blocked", names="category",
                    hole=0.65, color_discrete_sequence=PRIMARY_COLORS, template=PLOTLY_TEMPLATE
                )
                fig2.update_traces(textposition="inside", textinfo="percent")
                fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=220, showlegend=True, legend=dict(orientation="v", yanchor="auto", y=0.5, xanchor="right", x=1))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">🩺</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Healthy Inventory</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">0 capital blocked in dead or slow-moving stock</div>
    </div>
</div>''', unsafe_allow_html=True)
        else:
            st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">ℹ️</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Data Unavailable</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">No inventory health data found</div>
    </div>
</div>''', unsafe_allow_html=True)
            
    with h2:
        st.markdown("### ⚠️ Stockout Risk")
        if stockout_cnt > 0:
            st.markdown(f"<div style='color:{DESIGN_TOKENS['danger']}; font-weight:600; margin-bottom:12px;'>{stockout_cnt} SKUs at or below reorder level</div>", unsafe_allow_html=True)
            low_disp = low_stock[["product_name", "category", "current_stock", "reorder_level"]].copy()
            low_disp["Reorder Gap"] = (low_disp["reorder_level"] - low_disp["current_stock"]).clip(lower=0)
            low_disp = low_disp.sort_values("Reorder Gap", ascending=False).head(5)
            st.dataframe(low_disp, use_container_width=True, hide_index=True)
        else:
            st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">✅</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">No Stockout Risk</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">All SKUs are currently above their reorder levels</div>
    </div>
</div>''', unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── 3. NOW: Dead Stock ───────────────────────────────────────────────────
    if dead > 0 or slow > 0:
        st.markdown("### 💀 Dead Stock Details")
        st.markdown(f"**{dead + slow} SKUs** are classified as Dead or Slow-moving, blocking **{fmt_inr(dead_stock_df.loc[dead_stock_df['stock_status'].isin(['DEAD', 'SLOW']), 'capital_blocked'].sum())}**.")
        dead_disp = dead_stock_df[dead_stock_df["stock_status"].isin(["DEAD", "SLOW"])].copy()
        dead_disp = dead_disp[["product_name", "category", "current_stock", "days_unsold", "stock_status", "capital_blocked"]].sort_values("days_unsold", ascending=False)
        st.dataframe(dead_disp, use_container_width=True, hide_index=True)
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    
    # ── 4. NEXT: Forecasting & Seasonal ──────────────────────────────────────
    n1, n2 = st.columns(2)
    with n1:
        st.markdown("### 📈 Demand Forecasting")
        spikes_df, error_msg = _get_forecast_spikes(
            st.session_state.get("sales_hash", 0), 
            st.session_state.get("inv_hash", 0), 
            sales_df, 
            inv_df
        )
        if error_msg:
            st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">⏸️</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Forecast Runtime Unavailable</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">Prophet/CmdStan compiler backend is not installed in this environment</div>
    </div>
</div>''', unsafe_allow_html=True)
        elif spikes_df.empty:
            st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">📉</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Stable Demand Forecast</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">No anomalous demand spikes forecasted for the next 30 days</div>
    </div>
</div>''', unsafe_allow_html=True)
        else:
            st.warning(f"Found {len(spikes_df)} products with forecasted demand spikes.")
            st.dataframe(spikes_df, use_container_width=True, hide_index=True)
            
    with n2:
        st.markdown("### 🌦️ Seasonal Buying Intelligence")
        st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">⏸️</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Seasonal Intelligence Unavailable</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">Backend modeling engine is currently inactive for historical extraction</div>
    </div>
</div>''', unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    
    # ── 5. BUY: Procurement & Price ──────────────────────────────────────────
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("### 🛒 Procurement Recommendations")
        if stockout_cnt > 0:
            proc_disp = low_stock[["product_name", "category", "current_stock", "reorder_level"]].copy()
            proc_disp["Suggested Reorder Qty"] = (proc_disp["reorder_level"] - proc_disp["current_stock"]).clip(lower=0)
            proc_disp["Reason"] = "Reorder Gap"
            st.dataframe(proc_disp.sort_values("Suggested Reorder Qty", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">📦</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Optimal Inventory Levels</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">No immediate procurement required based on reorder gaps</div>
    </div>
</div>''', unsafe_allow_html=True)
            
    with b2:
        st.markdown("### 💰 Price Intelligence")
        if "purchase_price" in sales_df.columns and "purchase_price" in inv_df.columns:
            hist_price = sales_df.groupby("product_name")["purchase_price"].mean().reset_index()
            hist_price.rename(columns={"purchase_price": "Historical Avg"}, inplace=True)
            price_comp = inv_df[["product_name", "category", "purchase_price"]].merge(hist_price, on="product_name", how="inner")
            price_comp.rename(columns={"purchase_price": "Latest Price", "product_name": "Product"}, inplace=True)
            price_comp["Historical Avg"] = price_comp["Historical Avg"].round(2)
            price_comp["Variance"] = (price_comp["Latest Price"] - price_comp["Historical Avg"]).round(2)
            price_comp["Var %"] = ((price_comp["Variance"] / price_comp["Historical Avg"]) * 100).round(1).astype(str) + "%"
            
            def get_status(v):
                if v > 0: return "📈 Above Avg"
                if v < 0: return "📉 Below Avg"
                return "➖ Stable"
                
            price_comp["Status"] = price_comp["Variance"].apply(get_status)
            price_comp["abs_var"] = price_comp["Variance"].abs()
            price_comp = price_comp.sort_values("abs_var", ascending=False).drop(columns=["abs_var", "category"])
            
            st.dataframe(
                price_comp.head(10), 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.markdown('''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px; margin-bottom:12px;">
    <div style="font-size:20px;">ℹ️</div>
    <div>
        <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Data Unavailable</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">Price history is not available</div>
    </div>
</div>''', unsafe_allow_html=True)
            
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    
    # ── 6. PERFORMANCE: Sales & Profitability ────────────────────────────────
    st.markdown("### 💹 Sales & Profitability")
    margins = calculate_margins(sales_df)
    heatmap_df = category_month_heatmap(sales_df)
    
    p1, p2 = st.columns(2)
    with p1:
        if not margins.empty and "total_profit" in margins.columns and "total_revenue" in margins.columns:
            by_cat = margins.groupby("category").agg({"total_profit": "sum", "total_revenue": "sum"}).reset_index()
            by_cat["real_margin_pct"] = (by_cat["total_profit"] / by_cat["total_revenue"] * 100).fillna(0).round(1)
            import plotly.express as px
            fig_mar = px.bar(
                by_cat.sort_values("real_margin_pct", ascending=False),
                x="category", y="real_margin_pct",
                title="Margin % by Category",
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=PRIMARY_COLORS,
            )
            fig_mar.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=320)
            st.plotly_chart(fig_mar, use_container_width=True)
        else:
            st.info("Profitability data unavailable.")
            
    with p2:
        if not heatmap_df.empty:
            import plotly.express as px
            fig_heat = px.imshow(
                heatmap_df,
                aspect="auto",
                title="Category vs Month Revenue",
                template=PLOTLY_TEMPLATE,
                color_continuous_scale="Blues",
            )
            fig_heat.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=320)
            st.plotly_chart(fig_heat, use_container_width=True)

elif page == "👥 Customer Intelligence":
    from engine.analytics import detect_churned_retailers as _churn, area_sales_ranking as _asr
    from engine.segmentation import compute_rfm, segment_customers, get_segment_recommendations

    if "sales_df" not in st.session_state or "cust_df" not in st.session_state:
        st.warning("Please load data first — go to ⚡ Command Center and click 'Load Demo Data'."); st.stop()

    render_page_header("", "👥 Customer Intelligence", "Understand customer segments, geography, behaviour, and retention.")

    sales_df = st.session_state["sales_df"]
    cust_df = st.session_state["cust_df"]
    
    # ── 0. Precompute Core Data ─────────────────────────────────────────────
    # RFM
    try:
        if "seg_df" not in st.session_state:
            _rfm = compute_rfm(sales_df, cust_df)
            _seg = segment_customers(_rfm)
            st.session_state["seg_df"] = _seg
        seg_df = st.session_state["seg_df"].copy()
    except Exception as e:
        seg_df = pd.DataFrame()
        st.session_state["seg_error"] = str(e)
        
    # Churn
    try:
        if "churn_df" not in st.session_state:
            _c = _churn(sales_df)
            st.session_state["churn_df"] = _c
        churn_df = st.session_state["churn_df"].copy()
    except Exception:
        churn_df = pd.DataFrame()

    # Active Customers: >0 outstanding
    active_count = len(cust_df.drop_duplicates("customer_id")[cust_df.drop_duplicates("customer_id")["outstanding_amount"] > 0])
    total_cust = cust_df["customer_id"].nunique()

    # Disambiguate AT RISK
    if not seg_df.empty:
        seg_df["segment"] = seg_df["segment"].replace({"At Risk": "Behavioral At Risk"})
    if not churn_df.empty:
        churn_df["churn_status"] = churn_df["churn_status"].replace({"AT RISK": "BEHAVIORAL AT RISK"})

    # ── 1. Customer Portfolio ────────────────────────────────────────────────
    champs = len(seg_df[seg_df["segment"] == "Champions"]) if not seg_df.empty else 0
    loyal = len(seg_df[seg_df["segment"] == "Loyal"]) if not seg_df.empty else 0
    beh_at_risk = len(seg_df[seg_df["segment"] == "Behavioral At Risk"]) if not seg_df.empty else 0
    lost = len(seg_df[seg_df["segment"] == "Lost"]) if not seg_df.empty else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    def _k(col, lbl, val, tc="text_primary"):
        _c = DESIGN_TOKENS.get(tc, DESIGN_TOKENS["text_primary"])
        col.markdown(f'''
        <div style="background:{DESIGN_TOKENS['card']};border:1px solid {DESIGN_TOKENS['border']};border-radius:{DESIGN_TOKENS['radius_card']};padding:14px;height:100%;">
            <div style="font-size:10px;font-weight:600;text-transform:uppercase;color:{DESIGN_TOKENS['text_muted']};margin-bottom:6px;">{lbl}</div>
            <div style="font-size:22px;font-weight:700;color:{_c};font-variant-numeric:tabular-nums;letter-spacing:-0.02em;">{val}</div>
        </div>
        ''', unsafe_allow_html=True)
        
    _k(c1, "Total Customers", f"{total_cust:,}")
    _k(c2, "Active Parties", f"{active_count:,}", "With open receivables")
    _k(c3, "Champions", f"{champs:,}", "primary")
    _k(c4, "Loyal", f"{loyal:,}", "success")
    _k(c5, "Behavioral At Risk", f"{beh_at_risk:,}", "warning")
    _k(c6, "Lost", f"{lost:,}", "danger")
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── 2. Customer Segmentation ─────────────────────────────────────────────
    st.markdown("### 🎯 Customer Segmentation")
    if not seg_df.empty:
        # Segment summary cards
        def seg_metrics(seg_name):
            d = seg_df[seg_df["segment"] == seg_name]
            if d.empty: return 0, 0, 0, 0, 0
            cnt = len(d)
            pct = (cnt / len(seg_df)) * 100
            rev = d["monetary"].mean()
            rec = d["recency_days"].mean()
            freq = d["frequency"].mean()
            return cnt, pct, rev, rec, freq
            
        sc1, sc2, sc3, sc4 = st.columns(4)
        def _sc(col, title, name, tc):
            cnt, pct, rev, rec, freq = seg_metrics(name)
            col.markdown(f'''
            <div style="background:{DESIGN_TOKENS['card']};border:1px solid {DESIGN_TOKENS['border']};border-top:3px solid {DESIGN_TOKENS[tc]};border-radius:{DESIGN_TOKENS['radius_card']};padding:14px;">
                <div style="font-weight:600;font-size:14px;color:{DESIGN_TOKENS['text_primary']};">{title}</div>
                <div style="font-size:24px;font-weight:700;color:{DESIGN_TOKENS['text_primary']};margin:4px 0;">{cnt:,} <span style="font-size:12px;font-weight:500;color:{DESIGN_TOKENS['text_muted']}">({pct:.1f}%)</span></div>
                <div style="display:flex;justify-content:space-between;font-size:12px;color:{DESIGN_TOKENS['text_muted']};margin-top:8px;">
                    <div>Avg Rev: <b>{fmt_inr(rev)}</b></div>
                    <div>Days: <b>{rec:.0f}</b></div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
        _sc(sc1, "CHAMPIONS", "Champions", "primary")
        _sc(sc2, "LOYAL", "Loyal", "success")
        _sc(sc3, "BEHAVIORAL AT RISK", "Behavioral At Risk", "warning")
        _sc(sc4, "LOST", "Lost", "danger")
        
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        
        s1, s2 = st.columns([1, 1.5])
        with s1:
            seg_counts = seg_df["segment"].value_counts().reset_index()
            seg_counts.columns = ["Segment", "Count"]
            import plotly.express as px
            fig_seg = px.pie(
                seg_counts, values="Count", names="Segment", hole=0.65,
                color_discrete_sequence=[DESIGN_TOKENS["primary"], DESIGN_TOKENS["success"], DESIGN_TOKENS["warning"], DESIGN_TOKENS["danger"]],
                template=PLOTLY_TEMPLATE,
            )
            fig_seg.update_traces(textposition="inside", textinfo="percent")
            fig_seg.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
            st.plotly_chart(fig_seg, use_container_width=True)
            
        with s2:
            st.markdown("##### Segment Profile & Recommendations")
            recs_df = get_segment_recommendations(seg_df)
            if not recs_df.empty and "recommendation" in recs_df.columns:
                recs_df["segment"] = recs_df["segment"].replace({"At Risk": "Behavioral At Risk"})
                summary = recs_df.groupby("segment").first().reset_index()
                for _, row in summary.iterrows():
                    cnt = seg_counts.loc[seg_counts["Segment"] == row["segment"], "Count"].values[0] if row["segment"] in seg_counts["Segment"].values else 0
                    st.markdown(f"**{row['segment']} ({cnt})**: {row['recommendation']}")
            else:
                st.info("No recommendations available.")
                
        with st.expander("🔍 View Segment Customer Details"):
            disp_seg = recs_df if not recs_df.empty else seg_df
            st.dataframe(
                disp_seg[["customer_name", "segment", "recency_days", "frequency", "monetary"] + (["recommendation"] if "recommendation" in disp_seg.columns else [])].rename(columns={
                    "customer_name": "Customer", "segment": "Segment", "recency_days": "Recency (Days)",
                    "frequency": "Orders", "monetary": "Revenue", "recommendation": "Recommendation"
                }),
                use_container_width=True, hide_index=True,
                column_config={"Revenue": st.column_config.NumberColumn(format="₹%.0f")}
            )
    else:
        err = st.session_state.get("seg_error", "Unknown error")
        st.markdown(f'''<div style="padding:12px 16px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; gap:12px;">
        <div style="font-size:20px;">⏸️</div>
        <div>
            <div style="font-size:14px; font-weight:600; color:rgba(255,255,255,0.9);">Segmentation Unavailable</div>
            <div style="font-size:12px; color:rgba(255,255,255,0.5);">{err}</div>
        </div>
        </div>''', unsafe_allow_html=True)
        
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── 3. Geographic Intelligence ───────────────────────────────────────────
    st.markdown("### 🗺️ Geographic Intelligence")
    area_rank = _asr(sales_df)
    
    if not area_rank.empty:
        # We need outstanding. Let's merge from cust_df using canonical field 'area'
        town_cust = cust_df.drop_duplicates("customer_id").groupby("area").agg(
            Outstanding=("outstanding_amount", "sum")
        ).reset_index().rename(columns={"area": "Town"})

        disp_area = area_rank.rename(columns={
            "customer_area": "Town", "unique_customers": "Customers", "total_revenue": "Sales"
        })[["Town", "Customers", "Sales"]]

        disp_area = disp_area.merge(town_cust, on="Town", how="left").fillna(0)

        g1, g2 = st.columns([1.5, 1])
        with g1:
            st.markdown("**Customer Distribution by Town (Sales vs Customers)**")
            fig_geo = px.scatter(
                disp_area, x="Customers", y="Sales", 
                size="Sales", color="Outstanding",
                hover_name="Town", template=PLOTLY_TEMPLATE,
                color_continuous_scale="Purples"
            )
            fig_geo.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), height=300,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_geo, use_container_width=True)
            st.caption("No GPS data — town-level aggregation only.")
            
        with g2:
            st.markdown("**Town-Level Summary**")
            st.dataframe(
                disp_area.sort_values("Sales", ascending=False),
                use_container_width=True, hide_index=True,
                column_config={
                    "Sales": st.column_config.NumberColumn(format="₹%.0f"),
                    "Outstanding": st.column_config.NumberColumn(format="₹%.0f")
                }
            )
    else:
        st.info("Geographic intelligence unavailable.")

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── 4. Territory Performance ─────────────────────────────────────────────
    st.markdown("### 📊 Territory Performance")
    if not area_rank.empty:
        t1, t2 = st.columns(2)
        disp_t = disp_area.sort_values("Sales", ascending=True)
        with t1:
            st.markdown("**SALES BY TOWN**")
            fig_st = px.bar(
                disp_t, x="Sales", y="Town", orientation="h",
                template=PLOTLY_TEMPLATE, color_discrete_sequence=[DESIGN_TOKENS["primary"]]
            )
            fig_st.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=250)
            st.plotly_chart(fig_st, use_container_width=True)
        with t2:
            st.markdown("**OUTSTANDING BY TOWN**")
            disp_o = disp_t.sort_values("Outstanding", ascending=True)
            fig_o = px.bar(
                disp_o, x="Outstanding", y="Town", orientation="h",
                template=PLOTLY_TEMPLATE, color_discrete_sequence=[DESIGN_TOKENS["warning"]]
            )
            fig_o.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=250)
            st.plotly_chart(fig_o, use_container_width=True)
            
        st.markdown("**Territory Performance Table**")
        perf_tab = disp_area.sort_values("Sales", ascending=False).copy()
        st.dataframe(perf_tab, use_container_width=True, hide_index=True, column_config={
            "Sales": st.column_config.NumberColumn(format="₹%.0f"),
            "Outstanding": st.column_config.NumberColumn(format="₹%.0f")
        })

    # ── 5. Beat Intelligence ─────────────────────────────────────────────────
    st.markdown("### 📍 Beat Intelligence")
    if "salesperson" in sales_df.columns and "customer_area" in sales_df.columns:
        beat_agg = sales_df.groupby(["customer_area", "salesperson"]).apply(
            lambda x: pd.Series({
                "Sales": (x["sale_price"] * x["quantity"]).sum(),
                "Customers": x["customer_name"].nunique(),
                "Transactions": x["date"].count()
            }), include_groups=False
        ).reset_index().rename(columns={"customer_area": "Town", "salesperson": "Sales Rep"})
        
        try:
            terr_df = pd.read_csv("data/config/territories.csv")
            beat_agg = beat_agg.merge(terr_df[["town", "sales_rep", "beat", "route_day"]].drop_duplicates(), left_on=["Town", "Sales Rep"], right_on=["town", "sales_rep"], how="left")
            beat_agg["Beat"] = beat_agg["beat"].fillna("Unassigned")
            beat_agg = beat_agg.drop(columns=["town", "sales_rep", "beat"])
        except Exception:
            beat_agg["Beat"] = "Aggregate (Town + Rep)"
            beat_agg["route_day"] = "Unknown"
            
        # UI Filters
        f1, f2, f3 = st.columns([2, 1, 1])
        with f1:
            towns = ["All"] + sorted(beat_agg["Town"].unique().tolist())
            sel_town = st.selectbox("Filter Town", towns, label_visibility="collapsed")
        with f3:
            show_reps = st.checkbox("Show Sales Rep & Route Day")
            
        filtered_beat = beat_agg if sel_town == "All" else beat_agg[beat_agg["Town"] == sel_town]
        
        # Outstanding at Town+Rep level is hard, we approximate by town average or omit.
        # The prompt says: Beat, Town, Customers, Sales, Outstanding
        # Let's merge outstanding from cust_df grouped by town
        # Actually customer outstanding is known per customer. We can't perfectly assign it to Town+Rep.
        # Omit Outstanding from Beat table to avoid misattribution, or show N/A.
        filtered_beat["Outstanding"] = "N/A"
        
        cols = ["Beat", "Town", "Customers", "Sales", "Outstanding"]
        if show_reps:
            cols.insert(2, "Sales Rep")
            cols.append("route_day")
            
        st.dataframe(
            filtered_beat[cols].rename(columns={"route_day": "Route Day"}).sort_values("Sales", ascending=False),
            use_container_width=True, hide_index=True,
            column_config={"Sales": st.column_config.NumberColumn(format="₹%.0f")}
        )
    else:
        st.info("Beat intelligence unavailable.")
        
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── 6. Customer Behaviour ────────────────────────────────────────────────
    st.markdown("### 👤 Customer Behaviour")
    if not seg_df.empty:
        cb1, cb2, cb3 = st.columns(3)
        
        with cb1:
            st.markdown("**RECENCY (Days since last order)**")
            bins_r = [0, 7, 14, 30, 60, 90, 9999]
            labels_r = ["0-7d", "8-14d", "15-30d", "31-60d", "61-90d", "90d+"]
            rec_dist = pd.cut(seg_df["recency_days"], bins=bins_r, labels=labels_r).value_counts().reindex(labels_r).reset_index()
            fig_r = px.bar(rec_dist, x="recency_days", y="count", template=PLOTLY_TEMPLATE, color_discrete_sequence=[DESIGN_TOKENS["primary"]])
            fig_r.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=200, xaxis_title="", yaxis_title="")
            st.plotly_chart(fig_r, use_container_width=True)
            
        with cb2:
            st.markdown("**FREQUENCY (Orders)**")
            bins_f = [0, 2, 4, 6, 8, 10, 9999]
            labels_f = ["1-2", "3-4", "5-6", "7-8", "9-10", "10+"]
            fre_dist = pd.cut(seg_df["frequency"], bins=bins_f, labels=labels_f).value_counts().reindex(labels_f).reset_index()
            fig_f = px.bar(fre_dist, x="frequency", y="count", template=PLOTLY_TEMPLATE, color_discrete_sequence=[DESIGN_TOKENS["primary"]])
            fig_f.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=200, xaxis_title="", yaxis_title="")
            st.plotly_chart(fig_f, use_container_width=True)
            
        with cb3:
            st.markdown("**MONETARY (Total Revenue)**")
            bins_m = [0, 5000, 10000, 20000, 40000, 80000, 99999999]
            labels_m = ["<₹5K", "₹5-10K", "₹10-20K", "₹20-40K", "₹40-80K", ">₹80K"]
            mon_dist = pd.cut(seg_df["monetary"], bins=bins_m, labels=labels_m).value_counts().reindex(labels_m).reset_index()
            fig_m = px.bar(mon_dist, x="monetary", y="count", template=PLOTLY_TEMPLATE, color_discrete_sequence=[DESIGN_TOKENS["primary"]])
            fig_m.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=200, xaxis_title="", yaxis_title="")
            st.plotly_chart(fig_m, use_container_width=True)
            
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── 7. Growing vs Declining ──────────────────────────────────────────────
    st.markdown("### 📈 Growing vs Declining")
    st.caption("Comparing last 30 days revenue against the prior 30 days.")
    # Deterministic calculation
    sales_df["date"] = pd.to_datetime(sales_df["date"])
    max_d = sales_df["date"].max()
    p1_start, p1_end = max_d - pd.Timedelta(days=30), max_d
    p2_start, p2_end = max_d - pd.Timedelta(days=60), max_d - pd.Timedelta(days=31)
    
    s_p1 = sales_df[(sales_df["date"] >= p1_start) & (sales_df["date"] <= p1_end)]
    s_p2 = sales_df[(sales_df["date"] >= p2_start) & (sales_df["date"] <= p2_end)]
    
    rev_p1 = s_p1.groupby("customer_name").apply(lambda x: (x["sale_price"]*x["quantity"]).sum()).reset_index(name="rev1")
    rev_p2 = s_p2.groupby("customer_name").apply(lambda x: (x["sale_price"]*x["quantity"]).sum()).reset_index(name="rev2")
    
    growth = pd.merge(rev_p1, rev_p2, on="customer_name", how="outer").fillna(0)
    growth["Δ Revenue"] = growth["rev1"] - growth["rev2"]
    
    # Merge town
    t_map = cust_df[["customer_name", "area"]].drop_duplicates("customer_name").rename(columns={"area": "town"})
    growth = growth.merge(t_map, on="customer_name", how="left")
    
    top_grow = growth[growth["Δ Revenue"] > 0].sort_values("Δ Revenue", ascending=False).head(5)
    top_dec = growth[growth["Δ Revenue"] < 0].sort_values("Δ Revenue", ascending=True).head(5)
    
    gd1, gd2 = st.columns(2)
    with gd1:
        st.markdown(f"**<span style='color:{DESIGN_TOKENS['success']}'>↑ Top 5 Growing</span>**", unsafe_allow_html=True)
        st.dataframe(
            top_grow[["customer_name", "town", "Δ Revenue"]].rename(columns={"customer_name": "Customer", "town": "Town"}),
            use_container_width=True, hide_index=True, column_config={"Δ Revenue": st.column_config.NumberColumn(format="₹%.0f")}
        )
    with gd2:
        st.markdown(f"**<span style='color:{DESIGN_TOKENS['danger']}'>↓ Top 5 Declining</span>**", unsafe_allow_html=True)
        st.dataframe(
            top_dec[["customer_name", "town", "Δ Revenue"]].rename(columns={"customer_name": "Customer", "town": "Town"}),
            use_container_width=True, hide_index=True, column_config={"Δ Revenue": st.column_config.NumberColumn(format="₹%.0f")}
        )

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── 8. Churned Customers ─────────────────────────────────────────────────
    st.markdown("### 🚨 Churned Customers")
    if not churn_df.empty:
        churn_df_disp = churn_df.copy()
        churn_df_disp["churn_status"] = churn_df_disp["churn_status"].replace({"AT RISK": "BEHAVIORAL AT RISK"})
        
        k1, k2, k3 = st.columns(3)
        _c_cnt = len(churn_df_disp[churn_df_disp["churn_status"] == "CHURNED"])
        _a_cnt = len(churn_df_disp[churn_df_disp["churn_status"] == "BEHAVIORAL AT RISK"])
        _l_rev = churn_df_disp[churn_df_disp["churn_status"] == "CHURNED"]["avg_monthly_revenue_before"].sum()
        
        k1.metric("Churned", _c_cnt)
        k2.metric("Behavioral At-Risk", _a_cnt)
        k3.metric("Est. Monthly Loss", fmt_inr(_l_rev))
        
        churned_list = churn_df_disp[churn_df_disp["churn_status"] == "CHURNED"]
        if not churned_list.empty:
            st.dataframe(
                churned_list[["customer_name", "customer_area", "last_order_date", "days_since_order", "avg_monthly_revenue_before", "recent_orders", "churn_status"]].rename(columns={
                    "customer_name": "Customer", "customer_area": "Town", "last_order_date": "Last Order", "days_since_order": "Days Since",
                    "avg_monthly_revenue_before": "Monthly Rev", "recent_orders": "Recent Orders", "churn_status": "Status"
                }),
                use_container_width=True, hide_index=True,
                column_config={"Monthly Rev": st.column_config.NumberColumn(format="₹%.0f")}
            )
        else:
            st.info("No churned customers detected.")
    else:
        st.success("✅ No churned or at-risk customers detected. All active customers are ordering regularly.")

# ═════════════════════════════════════════════════════════════════════════════
# WORKSPACE 5 — 🤖 AI BUSINESS ANALYST
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Business Analyst":
    from engine.ai_agent import WholesaleAgent, AgentContext, SUGGESTED_QUESTIONS
    from engine.payment_intelligence import (
        score_payment_risk,
        get_collection_summary,
        generate_collection_message,
    )
    import os

    render_page_header("AI ASSISTANT", "🤖 AI Business Analyst", "Ask questions about cash, customers, inventory and operations.")

    # ── Check data ──────────────────────────────────────────────────────────────
    data_ready = (
        "sales_df" in st.session_state
        and st.session_state["sales_df"] is not None
        and not st.session_state["sales_df"].empty
    )

    # ── Layout: chat (left) + config sidebar (right) ────────────────────────────
    chat_col, config_col = st.columns([3, 1])

    with config_col:
        st.markdown("**\u2699\ufe0f Agent Config**")
        gemini_key = st.text_input(
            "Gemini API Key", type="password",
            placeholder="AIza... (free at aistudio.google.com)",
            help="Get a free Gemini Flash key at aistudio.google.com — no credit card.",
            key="gemini_key_input",
        )
        groq_key = st.text_input(
            "Groq API Key", type="password",
            placeholder="gsk_... (free at console.groq.com)",
            help="Alternative free LLM via Groq.",
            key="groq_key_input",
        )
        # UI-entered keys take ABSOLUTE priority over env vars.
        ui_gemini = gemini_key.strip()
        ui_groq   = groq_key.strip()

        if ui_gemini:
            active_gemini = ui_gemini
            active_groq   = ""
        elif ui_groq:
            active_gemini = ""
            active_groq   = ui_groq
        else:
            active_gemini = os.getenv("GEMINI_API_KEY", "")
            active_groq   = os.getenv("GROQ_API_KEY", "")

        last_used = st.session_state.get("last_llm_used")
        if active_gemini:
            st.success("✅ Gemini key provided (auto-discovery)")
            backend_label = last_used if last_used else "Gemini (awaiting first run)"
        elif active_groq:
            st.success("✅ Groq key provided")
            backend_label = last_used if last_used else "Groq llama-3.1-8b-instant"
        else:
            st.info("ℹ️ Rule-based fallback — add a key for full LLM reasoning")
            backend_label = last_used if last_used else "Rule-based fallback"

        st.markdown(f"**Last Model:** `{backend_label}`")
        st.markdown("---")

        # ── Payment risk mini-summary ───────────────────────────────────────────
        st.markdown("**\U0001f4b3 Collection Risk**")
        if data_ready:
            _risk_df = score_payment_risk(
                st.session_state["sales_df"],
                st.session_state.get("cust_df"),
            )
            _summary = get_collection_summary(_risk_df)
            if _summary["total_at_risk"] > 0:
                st.markdown(
                    f"<div style='font-size:13px;line-height:1.6;'>"
                    f"<b>At Risk:</b> {fmt_inr(_summary['total_at_risk'])}<br>"
                    f"<b>High Risk:</b> <span style='color:#F0616D;'>{fmt_inr(_summary['high_risk_amount'])}</span><br>"
                    f"<b>Recovery Est:</b> {_summary['recovery_probability_pct']:.0f}%"
                    f"</div>",
                    unsafe_allow_html=True
                )
                if _summary["write_off_risk_count"] > 0:
                    st.error(f"\u26a0\ufe0f {_summary['write_off_risk_count']} write-off risk customers")
            else:
                st.success("\u2705 No overdue amounts")
        else:
            st.caption("Load data to see risk scores.")

    with chat_col:


        # ── Chat history ────────────────────────────────────────────────────────
        
# ── Mapping tools to merchant-facing labels ──────────────────────────────────
        _TOOL_LABELS = {
            "get_outstanding_payments": "Checked receivables",
            "get_payment_risk_scores": "Scored payment risk",
            "get_recovery_batch": "Ranked recovery candidates",
            "get_dead_stock": "Checked dead stock",
            "get_restock_alerts": "Checked stockout risk",
            "get_customer_segments": "Analyzed customer segments",
            "get_area_performance": "Reviewed territory performance",
            "get_morning_briefing": "Prepared business briefing",
            "execute_recovery_campaign": "Executed recovery campaign",
            "get_recovery_metrics": "Checked recovery metrics",
            "get_recovery_audit_log": "Checked recovery audit log",
            "get_customer_recovery_status": "Checked customer recovery status",
            "choose_recovery_action": "Chose recovery action",
            "check_payment_status": "Checked payment status",
            "get_recovery_priority": "Checked recovery priority",
            "get_anomalies": "Checked for anomalies"
        }

        def render_trace(steps):
            for s in steps:
                tool_name = s.get("action", s.get("action_name", ""))
                label = _TOOL_LABELS.get(tool_name, f"Executed {tool_name.replace('_', ' ')}")
                st.markdown(f"✓ {label}")

        if "agent_chat_history" not in st.session_state:
            st.session_state["agent_chat_history"] = []

        chat_container = st.container(height=500, border=False)
        with chat_container:
            if not st.session_state["agent_chat_history"]:
                st.markdown(
                    "<div style='text-align:center; padding:40px 20px; background:rgba(109,91,240,0.05); border-radius:12px; margin-top:20px;'>"
                    "<div style='font-size:24px; margin-bottom:12px;'>👋</div>"
                    "<div style='font-size:16px; font-weight:600; color:white; margin-bottom:8px;'>Welcome to your Business Analyst</div>"
                    "<div style='font-size:14px; color:#A1A1AA;'>Ask about:<br>Revenue &middot; Collections &middot; Inventory &middot; Customers &middot; Territories</div>"
                    "</div>",
                    unsafe_allow_html=True
                )

                st.markdown("<br>**💡 Suggested Questions**", unsafe_allow_html=True)
                _APPROVED_QUESTIONS = [
                    "Give me today's business briefing.",
                    "Which customers currently owe me the most?",
                    "Who should I contact first for collections?",
                    "Which products are approaching stockout?",
                    "What should I buy before the next seasonal peak?",
                    "Which customers are declining?",
                    "Which territory is underperforming?",
                    "What is my current inventory value?",
                    "Show me the immutable ledger."
                ]
                _chip_cols = st.columns(3)
                for _i, _q in enumerate(_APPROVED_QUESTIONS[:3]):
                    with _chip_cols[_i]:
                        if st.button(_q, key=f"chip1_{_i}", use_container_width=True):
                            st.session_state["agent_prefill"] = _q
                _chip_cols2 = st.columns(3)
                for _i, _q in enumerate(_APPROVED_QUESTIONS[3:6]):
                    with _chip_cols2[_i]:
                        if st.button(_q, key=f"chip2_{_i}", use_container_width=True):
                            st.session_state["agent_prefill"] = _q
                _chip_cols3 = st.columns(3)
                for _i, _q in enumerate(_APPROVED_QUESTIONS[6:9]):
                    with _chip_cols3[_i]:
                        if st.button(_q, key=f"chip3_{_i}", use_container_width=True):
                            st.session_state["agent_prefill"] = _q

            for _msg in st.session_state["agent_chat_history"]:
                with st.chat_message(_msg["role"]):
                    if _msg["role"] == "assistant" and _msg.get("content", "").startswith("AGENT_ERROR:"):
                        st.error(_msg["content"].replace("AGENT_ERROR: ", "⚠️ "))
                    else:
                        st.markdown(_msg["content"])
                        
                    if _msg["role"] == "assistant":
                            
                        if _msg.get("steps"):
                            _steps = _msg["steps"]
                            with st.expander(f"🔍 Operational trace ({len(_steps)} steps)"):
                                render_trace(_steps)
                                
                        if "confidence" in _msg:
                            _conf_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(_msg["confidence"], "⚪")
                            st.caption(f"{_conf_icon} Confidence: {_msg['confidence']} · Grounded in {_msg.get('tool_calls', 0)} data source(s)")

        # ── Threaded Chat input ────────────────────────────────────────────────────────
        _prefill = st.session_state.pop("agent_prefill", "")
        
        is_generating = st.session_state.get("agent_generating", False)
        
        _user_input = None
        if not is_generating:
            _user_input = st.chat_input(placeholder="Ask anything about your business...")
        else:
            scol1, scol2 = st.columns([8, 2])
            scol1.text_input("Generating", "Analyzing your business... ⏳", disabled=True, label_visibility="collapsed")
            if scol2.button("Stop 🛑", use_container_width=True):
                if "agent_cancel_event" in st.session_state:
                    st.session_state["agent_cancel_event"].set()
        
        _question = _user_input or _prefill
        
        if _question and not is_generating:
            if not data_ready:
                st.warning("⚠️ Please load data first — go to ⚡ Command Center and click 'Load Demo Data'.")
            else:
                st.session_state["agent_chat_history"].append({"role": "user", "content": _question})
                st.session_state["agent_generating"] = True
                
                import threading
                from streamlit.runtime.scriptrunner import add_script_run_ctx
                
                st.session_state["agent_cancel_event"] = threading.Event()
                st.session_state["agent_result"] = {}
                
                def _run_agent(q, res_dict, ev, ctx_data, keys):
                    try:
                        _ctx = AgentContext(
                            sales_df=ctx_data["s"], 
                            inventory_df=ctx_data["i"], 
                            customer_df=ctx_data["c"], 
                            recovery_state=ctx_data["r"]
                        )
                        _agent = WholesaleAgent(context=_ctx, gemini_key=keys["gem"], groq_key=keys["grq"])
                        res_dict["res"] = _agent.run(q, cancel_check=ev.is_set)
                        res_dict["r"] = _ctx.recovery_state
                    except Exception as e:
                        res_dict["err"] = str(e)

                shared_recovery = {}
                if "recovery_campaign" in st.session_state:
                    shared_recovery["campaign"] = st.session_state["recovery_campaign"]
                    shared_recovery["records"] = st.session_state.get("recovery_records")
                    shared_recovery["metrics"] = st.session_state.get("recovery_metrics")
                
                ctx_data = {
                    "s": st.session_state.get("sales_df"),
                    "i": st.session_state.get("inv_df"),
                    "c": st.session_state.get("cust_df"),
                    "r": shared_recovery
                }
                keys = {"gem": active_gemini, "grq": active_groq}
                
                t = threading.Thread(target=_run_agent, args=(_question, st.session_state["agent_result"], st.session_state["agent_cancel_event"], ctx_data, keys))
                add_script_run_ctx(t)
                t.start()
                st.session_state["agent_thread"] = t
                st.rerun()

        if is_generating:
            t = st.session_state.get("agent_thread")
            if t and not t.is_alive():
                st.session_state["agent_generating"] = False
                r_dict = st.session_state.get("agent_result", {})
                
                if "r" in r_dict:
                    shared_recovery = r_dict["r"]
                    if "campaign" in shared_recovery:
                        st.session_state["recovery_campaign"] = shared_recovery["campaign"]
                    if "records" in shared_recovery:
                        st.session_state["recovery_records"] = shared_recovery["records"]
                    if "metrics" in shared_recovery:
                        st.session_state["recovery_metrics"] = shared_recovery["metrics"]
                
                if "err" in r_dict:
                    st.session_state["agent_chat_history"].append({"role": "assistant", "content": f"AGENT_ERROR: {r_dict['err']}", "steps": [], "llm": "Error", "confidence": "LOW", "tool_calls": 0})
                elif "res" in r_dict:
                    _result = r_dict["res"]
                    st.session_state["last_llm_used"] = _result.llm_used
                    st.session_state["agent_chat_history"].append({
                        "role": "assistant",
                        "content": _result.answer,
                        "steps": [_s.to_display() for _s in _result.steps],
                        "llm": _result.llm_used,
                        "confidence": getattr(_result, "confidence", "MEDIUM"),
                        "tool_calls": len(getattr(_result, "tool_calls", []))
                    })
                st.rerun()
            else:
                import time
                time.sleep(0.5)
                st.rerun()

        # ── Clear chat ──────────────────────────────────────────────────────────
        if st.session_state.get("agent_chat_history"):
            if st.button("\U0001f5d1\ufe0f Clear chat", key="clear_chat"):
                st.session_state["agent_chat_history"] = []
                st.rerun()

