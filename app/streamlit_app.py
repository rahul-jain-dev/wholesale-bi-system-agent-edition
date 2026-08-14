"""
app/streamlit_app.py
====================
5-page Streamlit dashboard for the Wholesale BI System.
Premium dark-mode UI with plotly charts and recommendation cards.

Pages:
  1. Upload & Overview
  2. Inventory Intelligence
  3. Payment Collection
  4. Sales & Profitability
  5. Recommendations (Showpiece)

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
    page_title="Wholesale BI System | Uniara, Rajasthan",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ─── Base Theme ─── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ─── Metric Cards ─── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}

/* ─── Page Header ─── */
.page-header {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 28px;
    box-shadow: 0 8px 32px rgba(99,102,241,0.3);
}
.page-header h1 {
    color: white;
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
}
.page-header p {
    color: rgba(255,255,255,0.8);
    margin: 8px 0 0 0;
    font-size: 0.95rem;
}

/* ─── Recommendation Cards ─── */
.rec-card {
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 14px;
    border-left: 5px solid;
    box-shadow: 0 2px 16px rgba(0,0,0,0.2);
    transition: transform 0.15s ease;
}
.rec-card:hover { transform: translateX(4px); }
.rec-card.HIGH {
    background: linear-gradient(135deg, #2d1b1b 0%, #3d1f1f 100%);
    border-color: #ef4444;
}
.rec-card.MEDIUM {
    background: linear-gradient(135deg, #2d2210 0%, #3d2d10 100%);
    border-color: #f59e0b;
}
.rec-card.LOW {
    background: linear-gradient(135deg, #0f2d1b 0%, #102d20 100%);
    border-color: #10b981;
}
.rec-priority {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 3px 10px;
    border-radius: 99px;
    display: inline-block;
    margin-bottom: 8px;
}
.HIGH .rec-priority  { background: #ef4444; color: white; }
.MEDIUM .rec-priority { background: #f59e0b; color: white; }
.LOW .rec-priority   { background: #10b981; color: white; }
.rec-title { font-size: 1rem; font-weight: 600; color: white; margin: 4px 0; }
.rec-message { font-size: 0.88rem; color: rgba(255,255,255,0.9); line-height: 1.6; }
.rec-impact {
    font-size: 0.85rem;
    font-weight: 600;
    color: #34d399;
    margin-top: 10px;
}

/* ─── CEO Briefing Box ─── */
.ceo-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border: 1px solid rgba(99,102,241,0.4);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 28px;
    box-shadow: 0 8px 32px rgba(99,102,241,0.2);
}
.ceo-box h3 {
    color: #a78bfa;
    font-size: 0.8rem;
    letter-spacing: 0.15em;
    font-weight: 600;
    text-transform: uppercase;
    margin: 0 0 14px 0;
}
.ceo-box p {
    color: rgba(255,255,255,0.9);
    font-size: 1rem;
    line-height: 1.8;
    margin: 0;
}

/* ─── Status Badges ─── */
.badge-dead   { color: #ef4444; font-weight: 700; }
.badge-slow   { color: #f59e0b; font-weight: 700; }
.badge-active { color: #10b981; font-weight: 700; }
.badge-high   { color: #ef4444; font-weight: 700; }
.badge-medium { color: #f59e0b; font-weight: 700; }
.badge-low    { color: #10b981; font-weight: 700; }

/* ─── Top Navbar ─── */
.top-navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(90deg, #16162a 0%, #1e1e36 100%);
    padding: 12px 24px;
    border-radius: 12px;
    margin-bottom: 24px;
    border: 1px solid rgba(255,255,255,0.1);
}
.top-navbar-brand {
    font-size: 1.1rem;
    font-weight: 700;
    color: white;
}
.top-navbar-meta {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.85);
}
.top-navbar-meta b { color: white; }

/* ─── Action Button in Tables ─── */
.action-btn {
    background-color: #10b981;
    color: white !important;
    padding: 4px 10px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.8rem;
}
.action-btn:hover {
    background-color: #059669;
}

/* ─── Sidebar ─── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}

/* ─── Upload zone ─── */
[data-testid="stFileUploader"] {
    border: 2px dashed rgba(99,102,241,0.4);
    border-radius: 12px;
    padding: 12px;
}

/* ─── Section divider ─── */
.section-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 28px 0;
}
</style>
""", unsafe_allow_html=True)

# ─── Plotly dark template ─────────────────────────────────────────────────────
PLOTLY_TEMPLATE = "plotly_dark"
PRIMARY_COLORS = px.colors.qualitative.Vivid

# ═════════════════════════════════════════════════════════════════════════════
# SESSION STATE & DATA LOADING
# ═════════════════════════════════════════════════════════════════════════════
DATA_DIR = Path(__file__).parent.parent / "data"

def _default_data_exists() -> bool:
    return (DATA_DIR / "demo_sales.csv").exists()

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
    sales_df = standardize_sales(pd.read_csv(DATA_DIR / "demo_sales.csv"))
    inv_df   = standardize_inventory(pd.read_csv(DATA_DIR / "demo_inventory.csv"))
    cust_df  = standardize_customers(pd.read_csv(DATA_DIR / "demo_customers.csv"))
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
def _get_forecast_spikes(s_hash: int, inv_hash: int, _sales: pd.DataFrame, _inv: pd.DataFrame) -> pd.DataFrame:
    try:
        top_cat = _sales["category"].mode().iloc[0] if "category" in _sales.columns and not _sales.empty else "FMCG"
        fc = forecast_demand(_sales, top_cat, 30)
        return detect_demand_spikes({top_cat: fc}, _inv)
    except Exception:
        return pd.DataFrame()

# ── Format helpers ────────────────────────────────────────────────────────────
def fmt_inr(amount: float) -> str:
    """Format amount in Indian Rupee notation (e.g., ₹1,23,456)."""
    if amount >= 1_00_00_000:
        return f"₹{amount/1_00_00_000:.1f}Cr"
    elif amount >= 1_00_000:
        return f"₹{amount/1_00_000:.1f}L"
    elif amount >= 1_000:
        return f"₹{amount/1_000:.1f}K"
    return f"₹{amount:,.0f}"

def color_status(val: str) -> str:
    colors = {"DEAD": "color: #ef4444; font-weight: bold",
              "SLOW": "color: #f59e0b; font-weight: bold",
              "ACTIVE": "color: #10b981; font-weight: bold",
              "HIGH": "color: #ef4444; font-weight: bold",
              "MEDIUM": "color: #f59e0b; font-weight: bold",
              "LOW": "color: #10b981; font-weight: bold"}
    return colors.get(str(val).upper(), "")

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 📦 Wholesale BI System")
    st.markdown("*AI Decision Support for Indian Distributors*")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        options=[
            "🏠 Upload & Overview",
            "📦 Inventory Intelligence",
            "💰 Payment Collection",
            "👤 Customer Intelligence",
            "📈 Sales & Profitability",
            "🎯 Recommendations",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("Built by Rahul Jain · JECRC Foundation")
    st.caption("BTech AI & Data Science · 2025")

# ── Top Navbar ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="top-navbar">
    <div class="top-navbar-brand">📦 Wholesale BI System</div>
    <div class="top-navbar-meta">
        <span><b>Business:</b> Uniara, Tonk, Rajasthan</span> &nbsp;|&nbsp; 
        <span><b>ERP:</b> Kuber / Tally / Marg</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — UPLOAD & OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════
if page == "🏠 Upload & Overview":
    st.markdown("""
    <div class="page-header">
        <h1>📦 Wholesale BI System</h1>
        <p>AI-Powered Decision Support for Indian Wholesale Distributors · Uniara, Rajasthan</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Demo Data Download Section ────────────────────────────────────────────
    demo_dir = Path(__file__).parent.parent / "data"
    demo_sales_path     = demo_dir / "demo_sales.csv"
    demo_inv_path       = demo_dir / "demo_inventory.csv"
    demo_cust_path      = demo_dir / "demo_customers.csv"

    if demo_sales_path.exists():
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #1a2744 0%, #0f1f3d 100%);
            border: 1px solid #6C63FF;
            border-radius: 16px;
            padding: 28px 32px;
            margin-bottom: 24px;
        ">
            <h3 style="margin: 0 0 6px 0; color: #a78bfa;">🎯 Try the Dashboard — 3 Easy Steps</h3>
            <p style="color: #94a3b8; margin: 0 0 20px 0; font-size: 14px;">
                Download our pre-built sample dataset for <strong style="color:#e2e8f0;">Raj Distributors, Jaipur</strong> —
                a fictional FMCG wholesale company — then upload the files to see AI insights in action.
            </p>
        </div>
        """, unsafe_allow_html=True)

        step1, step2, step3 = st.columns(3)

        with step1:
            st.markdown("""
            <div style="text-align:center; padding: 8px 0 4px 0;">
                <span style="font-size:32px;">⬇️</span><br>
                <strong style="color:#a78bfa;">STEP 1</strong><br>
                <span style="font-size:12px; color:#94a3b8;">Download the 3 sample files below</span>
            </div>
            """, unsafe_allow_html=True)
            st.download_button(
                "📊 Sales Data (CSV)",
                data=open(demo_sales_path, "rb").read(),
                file_name="demo_sales.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                "📦 Inventory Data (CSV)",
                data=open(demo_inv_path, "rb").read(),
                file_name="demo_inventory.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                "👥 Customer Data (CSV)",
                data=open(demo_cust_path, "rb").read(),
                file_name="demo_customers.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with step2:
            st.markdown("""
            <div style="text-align:center; padding: 8px 0 4px 0;">
                <span style="font-size:32px;">⬆️</span><br>
                <strong style="color:#a78bfa;">STEP 2</strong><br>
                <span style="font-size:12px; color:#94a3b8;">Upload them using the section below</span>
            </div>
            """, unsafe_allow_html=True)
            st.info("Open **📁 Upload ERP Data** below and upload all 3 files you just downloaded.")

        with step3:
            st.markdown("""
            <div style="text-align:center; padding: 8px 0 4px 0;">
                <span style="font-size:32px;">📊</span><br>
                <strong style="color:#a78bfa;">STEP 3</strong><br>
                <span style="font-size:12px; color:#94a3b8;">Explore AI insights across all pages</span>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            **What you'll discover:**
            - 📦 ₹1.1L of capital blocked in dead stock
            - 💰 3 customers with unpaid dues
            - 👤 Customer segments (Champions → Lost)
            - 📈 Holi festival demand spike in sales
            - 🔍 2 anomalous discount transactions
            """)

        st.markdown("---")

    # Upload section
    with st.expander("📁 Upload ERP Data (Kuber / Tally / Marg — CSV or Excel)", expanded=not _default_data_exists()):
        col1, col2, col3 = st.columns(3)
        with col1:
            sales_file = st.file_uploader("Sales Data (CSV / Excel)", type=["csv", "xlsx", "xls"], key="sales_upload")
        with col2:
            inv_file = st.file_uploader("Inventory Data (CSV / Excel)", type=["csv", "xlsx", "xls"], key="inv_upload")
        with col3:
            cust_file = st.file_uploader("Customer Data (CSV / Excel)", type=["csv", "xlsx", "xls"], key="cust_upload")

        if sales_file or inv_file or cust_file:
            # Ensure base data exists first so other pages still work
            if "sales_df" not in st.session_state and _default_data_exists():
                s, i, c = load_defaults()
                st.session_state["sales_df"] = s
                st.session_state["inv_df"] = i
                st.session_state["cust_df"] = c

            def _load_uploaded(uploaded_file, standardize_fn, alias_map, label):
                """Read, preprocess and standardize a single uploaded file."""
                raw_bytes = uploaded_file.read()
                raw_df = read_file(raw_bytes)
                clean_df = preprocess_erp_dataframe(raw_df)
                # Warn about unrecognised columns
                unknown = get_unmapped_columns(clean_df, alias_map)
                if unknown:
                    st.warning(
                        f"⚠️ **{label}:** {len(unknown)} column(s) not recognized and will be ignored: "
                        f"`{'`, `'.join(unknown[:8])}`"
                    )
                return standardize_fn(clean_df)

            try:
                if sales_file:
                    st.session_state["sales_df"] = _load_uploaded(
                        sales_file, standardize_sales, SALES_ALIASES, "Sales"
                    )
                if inv_file:
                    st.session_state["inv_df"] = _load_uploaded(
                        inv_file, standardize_inventory, INVENTORY_ALIASES, "Inventory"
                    )
                if cust_file:
                    st.session_state["cust_df"] = _load_uploaded(
                        cust_file, standardize_customers, CUSTOMER_ALIASES, "Customer"
                    )
                st.session_state["data_source"] = "uploaded"
                st.session_state["sales_hash"] = int(pd.util.hash_pandas_object(st.session_state["sales_df"]).sum())
                st.session_state["inv_hash"] = int(pd.util.hash_pandas_object(st.session_state["inv_df"]).sum())
                st.session_state["cust_hash"] = int(pd.util.hash_pandas_object(st.session_state["cust_df"]).sum())
                st.success(
                    "✅ Uploaded data cleaned and standardized to canonical schema. "

                    "Junk rows removed · ₹ formatting stripped · Column aliases applied."
                )
            except Exception as e:
                st.error(f"❌ Error processing upload: {str(e)}")
                st.info("💡 Tip: Share the first few rows of your file and we can fix the mapping instantly.")

    # Load default data if not uploaded
    if "sales_df" not in st.session_state:
        if _default_data_exists():
            st.info("💡 **Interview / Demo Mode**: You can load pre-configured, interview-ready data instantly instead of uploading files manually.")
            if st.button("🚀 Load Pre-configured Demo Data", use_container_width=True):
                with st.spinner("Loading interview-ready demo data..."):
                    sales_df, inv_df, cust_df = load_defaults()
                    st.session_state["sales_df"]    = sales_df
                    st.session_state["inv_df"]      = inv_df
                    st.session_state["cust_df"]     = cust_df
                    st.session_state["data_source"] = "synthetic"
                    st.session_state["sales_hash"] = int(pd.util.hash_pandas_object(sales_df).sum())
                    st.session_state["inv_hash"] = int(pd.util.hash_pandas_object(inv_df).sum())
                    st.session_state["cust_hash"] = int(pd.util.hash_pandas_object(cust_df).sum())
                st.rerun()
            st.stop()
        else:
            st.warning("⚠️ No data found. Run `python scripts/generate_demo_data.py` to generate demo data, or upload your CSV files above.")
            st.stop()

    sales_df = st.session_state["sales_df"]
    inv_df   = st.session_state["inv_df"]
    cust_df  = st.session_state["cust_df"]

    # ── KPI Cards ────────────────────────────────────────────────────────────
    dead_stock_df  = _get_dead_stock(st.session_state["inv_hash"], inv_df)
    outstanding_df = _get_outstanding(st.session_state["sales_hash"], st.session_state["cust_hash"], sales_df, cust_df)

    total_products   = len(inv_df)
    dead_stock_val   = dead_stock_df.loc[dead_stock_df["stock_status"] == "DEAD", "capital_blocked"].sum()
    total_outstanding = cust_df["outstanding_amount"].sum()
    at_risk_count    = outstanding_df.loc[outstanding_df["risk_level"] == "HIGH", "customer_name"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total SKUs", f"{total_products:,}", delta="Tracked products")
    with col2:
        st.metric("💀 Dead Stock Value", fmt_inr(dead_stock_val), delta="Capital blocked", delta_color="inverse")
    with col3:
        st.metric("⏰ Outstanding Payments", fmt_inr(total_outstanding), delta="Total recoverable", delta_color="inverse")
    with col4:
        st.metric("🚨 High-Risk Customers", str(at_risk_count), delta="90+ days overdue", delta_color="inverse")

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Quick stats ───────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📅 Date Range")
        dates = pd.to_datetime(sales_df["date"])
        if sales_df.empty or pd.isna(dates.min()):
            st.write("**No date range available** — upload sales data with a date column.")
            days = 0
        else:
            st.write(f"**{dates.min().strftime('%d %b %Y')}** → **{dates.max().strftime('%d %b %Y')}**")
            days = (dates.max() - dates.min()).days
        st.caption(f"{days} days of transaction history")

        total_rev = (sales_df["sale_price"] * sales_df["quantity"]).sum()
        st.markdown(f"#### 💹 Total Revenue")
        st.markdown(f"## {fmt_inr(total_rev)}")

    with col2:
        # Town distribution donut
        town_sales = sales_df.groupby("customer_area", group_keys=False).apply(
            lambda x: (x["sale_price"] * x["quantity"]).sum(), include_groups=False
        ).reset_index(name="revenue")
        fig = px.pie(
            town_sales, values="revenue", names="customer_area",
            title="Revenue by Town", hole=0.5,
            color_discrete_sequence=PRIMARY_COLORS,
            template=PLOTLY_TEMPLATE,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(margin=dict(t=40, b=10, l=0, r=0), height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Data Preview ──────────────────────────────────────────────────────────
    st.markdown("#### 📋 Sales Data Preview (last 20 transactions)")
    preview_cols = ["invoice_no", "date", "customer_name", "customer_area",
                    "product_name", "category", "quantity", "sale_price", "payment_status"]
    st.dataframe(
        sales_df[preview_cols].tail(20),
        use_container_width=True,
        hide_index=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — INVENTORY INTELLIGENCE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📦 Inventory Intelligence":
    if "sales_df" not in st.session_state:
        st.warning("Please upload data or go to Upload & Overview page first."); st.stop()

    st.markdown("""
    <div class="page-header">
        <h1>📦 Inventory Intelligence</h1>
        <p>Dead stock detection · Capital blocked analysis · Restock alerts</p>
    </div>
    """, unsafe_allow_html=True)

    inv_df = st.session_state["inv_df"]
    dead_stock_df = _get_dead_stock(st.session_state["inv_hash"], inv_df)

    # Summary metrics
    active = (dead_stock_df["stock_status"] == "ACTIVE").sum()
    slow   = (dead_stock_df["stock_status"] == "SLOW").sum()
    dead   = (dead_stock_df["stock_status"] == "DEAD").sum()
    total_blocked = dead_stock_df["capital_blocked"].sum()
    dead_blocked  = dead_stock_df.loc[dead_stock_df["stock_status"] == "DEAD", "capital_blocked"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("✅ Active SKUs", active, delta="≤30 days unsold")
    with col2: st.metric("🟡 Slow SKUs", slow, delta="31-60 days unsold", delta_color="off")
    with col3: st.metric("🔴 Dead SKUs", dead, delta=">60 days unsold", delta_color="inverse")
    with col4: st.metric("💀 Dead Capital", fmt_inr(dead_blocked), delta_color="inverse")

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Filter
    status_filter = st.multiselect(
        "Filter by Status", ["DEAD", "SLOW", "ACTIVE"],
        default=["DEAD", "SLOW"], key="inv_filter"
    )
    filtered = dead_stock_df[dead_stock_df["stock_status"].isin(status_filter)] if status_filter else dead_stock_df

    # ── Table ─────────────────────────────────────────────────────────────────
    display_cols = [
        "product_name", "category", "company", "size_variant",
        "current_stock", "days_unsold", "stock_status",
        "capital_blocked", "suggested_discount_pct", "recommended_action"
    ]
    st.markdown("#### 📊 Dead Stock Analysis")

    def style_status(val):
        return color_status(val)

    styled = filtered[display_cols].sort_values("days_unsold", ascending=False)
    styled["capital_blocked"] = styled["capital_blocked"].apply(lambda x: fmt_inr(x))
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config={
            "stock_status": st.column_config.TextColumn("Status"),
            "days_unsold": st.column_config.NumberColumn("Days Unsold", format="%d days"),
            "suggested_discount_pct": st.column_config.NumberColumn("Suggested Discount", format="%.0f%%"),
        }
    )

    col1, col2 = st.columns(2)

    with col1:
        # Top 15 products by days unsold
        top15 = (
            dead_stock_df.nlargest(15, "days_unsold")
            [["product_name", "size_variant", "days_unsold", "stock_status"]]
            .copy()
        )
        top15["label"] = top15["product_name"] + " " + top15["size_variant"]
        color_map = {"DEAD": "#ef4444", "SLOW": "#f59e0b", "ACTIVE": "#10b981"}
        top15["color"] = top15["stock_status"].map(color_map)

        fig = px.bar(
            top15, x="days_unsold", y="label", orientation="h",
            color="stock_status",
            color_discrete_map=color_map,
            title="Top 15 Products by Days Unsold",
            labels={"days_unsold": "Days Unsold", "label": "Product"},
            template=PLOTLY_TEMPLATE,
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            margin=dict(l=0, r=0, t=40, b=0),
            height=420,
            legend_title="Status",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Capital blocked by category (donut)
        cat_blocked = (
            dead_stock_df.groupby("category")["capital_blocked"].sum()
            .reset_index().rename(columns={"capital_blocked": "Capital Blocked"})
        )
        fig2 = px.pie(
            cat_blocked, values="Capital Blocked", names="category",
            title="Capital Blocked by Category", hole=0.55,
            color_discrete_sequence=PRIMARY_COLORS,
            template=PLOTLY_TEMPLATE,
        )
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        fig2.update_layout(margin=dict(t=40, b=10, l=0, r=0), height=420, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    # ── Near reorder alert ────────────────────────────────────────────────────
    low_stock = inv_df[inv_df["current_stock"] <= inv_df["reorder_level"]].copy()
    if not low_stock.empty:
        st.warning(f"⚠️ **{len(low_stock)} SKUs** are at or below reorder level — consider restocking soon.")
        st.dataframe(
            low_stock[["product_name", "size_variant", "current_stock", "reorder_level"]].head(10),
            use_container_width=True, hide_index=True
        )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3 — PAYMENT COLLECTION
# ═════════════════════════════════════════════════════════════════════════════
elif page == "💰 Payment Collection":
    if "sales_df" not in st.session_state:
        st.warning("Please upload data or go to Upload & Overview page first."); st.stop()

    st.markdown("""
    <div class="page-header">
        <h1>💰 Payment Collection</h1>
        <p>Outstanding recovery tracker · Risk scoring · WhatsApp reminders</p>
    </div>
    """, unsafe_allow_html=True)

    sales_df = st.session_state["sales_df"]
    cust_df  = st.session_state["cust_df"]
    outstanding_df = _get_outstanding(
        st.session_state["sales_hash"], st.session_state["cust_hash"], sales_df, cust_df
    )

    # NPA Filter
    show_npa = st.toggle("Show Historical NPA (Bad Debts > 120 days)", value=False)
    if not show_npa:
        outstanding_df = outstanding_df[outstanding_df["npa_status"] != "NPA"]

    # KPIs
    total_out   = cust_df["outstanding_amount"].sum()
    high_risk   = outstanding_df[outstanding_df["risk_level"] == "HIGH"]
    medium_risk = outstanding_df[outstanding_df["risk_level"] == "MEDIUM"]
    high_val    = high_risk["outstanding_amount"].sum()
    med_val     = medium_risk["outstanding_amount"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("💰 Total Outstanding", fmt_inr(total_out))
    with col2: st.metric("🔴 HIGH Risk", f"{len(high_risk)} customers", delta=fmt_inr(high_val), delta_color="inverse")
    with col3: st.metric("🟡 MEDIUM Risk", f"{len(medium_risk)} customers", delta=fmt_inr(med_val), delta_color="inverse")
    with col4:
        avg_overdue = outstanding_df["days_overdue"].mean()
        if outstanding_df.empty or pd.isna(avg_overdue):
            avg_overdue = 0
        st.metric("📅 Avg Days Overdue", f"{avg_overdue:.0f} days")

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Filter by risk
    risk_filter = st.multiselect(
        "Filter by Risk Level", ["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM"], key="pay_filter"
    )
    filtered_pay = outstanding_df[outstanding_df["risk_level"].isin(risk_filter)] if risk_filter else outstanding_df
    filtered_pay = filtered_pay.sort_values("urgency_score", ascending=False)

    st.markdown("#### 📋 Outstanding Payments — Sorted by Urgency Score")
    display_pay = [
        "customer_name", "area", "outstanding_amount", "days_overdue",
        "risk_level", "urgency_score", "credit_limit"
    ]
    filtered_pay_display = filtered_pay[display_pay].copy()
    filtered_pay_display["outstanding_amount"] = filtered_pay_display["outstanding_amount"].apply(fmt_inr)
    filtered_pay_display["credit_limit"]       = filtered_pay_display["credit_limit"].apply(fmt_inr)
    filtered_pay_display["urgency_score"]      = filtered_pay_display["urgency_score"].round(2)
    # Add dummy WhatsApp link column
    filtered_pay_display["action_url"] = "https://wa.me/"

    st.dataframe(
        filtered_pay_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "days_overdue": st.column_config.NumberColumn("Days Overdue", format="%d days"),
            "urgency_score": st.column_config.ProgressColumn("Urgency", min_value=0, max_value=100, format="%.1f"),
            "action_url": st.column_config.LinkColumn("Action", display_text="💬 WhatsApp"),
        }
    )

    col1, col2 = st.columns(2)

    with col1:
        # Outstanding per customer bar chart (top 15)
        top_out = (
            outstanding_df.nlargest(15, "outstanding_amount")
            [["customer_name", "outstanding_amount", "risk_level"]]
        )
        color_map = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}
        fig = px.bar(
            top_out, x="outstanding_amount", y="customer_name", orientation="h",
            color="risk_level", color_discrete_map=color_map,
            title="Top 15 Outstanding Amounts",
            labels={"outstanding_amount": "Amount (₹)", "customer_name": "Customer"},
            template=PLOTLY_TEMPLATE,
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"},
                          margin=dict(l=0,r=0,t=40,b=0), height=420)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Days overdue distribution
        fig2 = px.histogram(
            outstanding_df, x="days_overdue", nbins=20,
            color_discrete_sequence=["#6366f1"],
            title="Days Overdue Distribution",
            labels={"days_overdue": "Days Overdue", "count": "Customers"},
            template=PLOTLY_TEMPLATE,
        )
        fig2.add_vline(x=45, line_dash="dash", line_color="#f59e0b",
                       annotation_text="MEDIUM threshold (45d)")
        fig2.add_vline(x=90, line_dash="dash", line_color="#ef4444",
                       annotation_text="HIGH threshold (90d)")
        fig2.update_layout(margin=dict(l=0,r=0,t=40,b=0), height=420)
        st.plotly_chart(fig2, use_container_width=True)

    # WhatsApp message generator
    st.markdown("#### 💬 WhatsApp Collection Message Generator")
    selected_cust = st.selectbox(
        "Select customer to generate collection message",
        options=outstanding_df["customer_name"].tolist(),
        key="cust_select"
    )
    if selected_cust:
        row = outstanding_df[outstanding_df["customer_name"] == selected_cust].iloc[0]
        if "whatsapp_message" in row and row["whatsapp_message"]:
            st.code(row["whatsapp_message"], language=None)
        else:
            msg = (f"Namaste {row['customer_name']},\n\n"
                   f"Aapka ₹{row['outstanding_amount']:,.0f} ka payment "
                   f"{int(row['days_overdue'])} din se pending hai.\n"
                   f"Kripya aaj hi settle karein.\n\nDhanyavaad,\nUniara Wholesale")
            st.code(msg, language=None)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — CUSTOMER INTELLIGENCE (CHURN)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "👤 Customer Intelligence":
    if "sales_df" not in st.session_state:
        st.warning("Please upload data or go to Upload & Overview page first."); st.stop()

    st.markdown("""
    <div class="page-header">
        <h1>👤 Customer Intelligence</h1>
        <p>Dead retailer alerts · Churn detection · Customer retention</p>
    </div>
    """, unsafe_allow_html=True)

    sales_df = st.session_state["sales_df"]
    churn_df = _get_churned_retailers(st.session_state["sales_hash"], sales_df)

    if churn_df.empty:
        st.success("✅ No churned or at-risk customers detected. All active customers are ordering regularly.")
    else:
        churned = churn_df[churn_df["churn_status"] == "CHURNED"]
        at_risk = churn_df[churn_df["churn_status"] == "AT RISK"]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔴 Churned Retailers", len(churned), delta="0 orders in 45 days", delta_color="inverse")
        with col2:
            st.metric("⚠️ At Risk Retailers", len(at_risk), delta=">50% drop in frequency", delta_color="inverse")
        with col3:
            lost_rev = churned["avg_monthly_revenue_before"].sum()
            st.metric("💸 Estimated Monthly Loss", fmt_inr(lost_rev), delta="From churned customers", delta_color="inverse")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        st.markdown("#### 🚨 Retailer Churn Alerts")
        st.caption("Customers who have stopped buying or significantly reduced order frequency.")

        for _, row in churn_df.iterrows():
            status = row["churn_status"]
            alert = row["churn_alert"]
            color_cls = "HIGH" if status == "CHURNED" else "MEDIUM"
            icon = "🔴" if status == "CHURNED" else "⚠️"

            st.markdown(f"""
            <div class="rec-card {color_cls}">
                <span class="rec-priority">{status}</span>
                <div class="rec-title">{icon} {row['customer_name']} ({row.get('customer_area', '')})</div>
                <div class="rec-message">{alert}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### 📋 Data View")
        display_churn = churn_df.copy()
        display_churn["avg_monthly_revenue_before"] = display_churn["avg_monthly_revenue_before"].apply(fmt_inr)
        
        st.dataframe(
            display_churn,
            use_container_width=True,
            hide_index=True,
        )

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5 — SALES & PROFITABILITY
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📈 Sales & Profitability":
    if "sales_df" not in st.session_state:
        st.warning("Please upload data or go to Upload & Overview page first."); st.stop()

    st.markdown("""
    <div class="page-header">
        <h1>📈 Sales & Profitability</h1>
        <p>Monthly trends · GST-aware margins · Town ranking · Category heatmap</p>
    </div>
    """, unsafe_allow_html=True)

    sales_df = st.session_state["sales_df"]

    monthly_df = _get_monthly_trend(st.session_state["sales_hash"], sales_df)
    margins    = _get_margins(st.session_state["sales_hash"], sales_df)
    area_df    = _get_area_rank(st.session_state["sales_hash"], sales_df)
    heatmap_df = _get_heatmap(st.session_state["sales_hash"], sales_df)

    # ── Monthly Revenue Trend ─────────────────────────────────────────────────
    st.markdown("#### 📅 Monthly Revenue Trend")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly_df["year_month"], y=monthly_df["total_revenue"],
        mode="lines+markers",
        name="Revenue",
        line=dict(color="#6366f1", width=3),
        marker=dict(size=7),
        fill="tozeroy",
        fillcolor="rgba(99,102,241,0.1)",
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        xaxis_title="Month", yaxis_title="Revenue (₹)",
        margin=dict(l=0,r=0,t=10,b=0), height=320,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Town-wise sales ranking
        st.markdown("#### 🗺️ Town-wise Sales Ranking")
        fig2 = px.bar(
            area_df.sort_values("total_revenue", ascending=True),
            x="total_revenue", y="customer_area", orientation="h",
            color="total_revenue",
            color_continuous_scale="Viridis",
            title=None,
            labels={"total_revenue": "Revenue (₹)", "customer_area": "Town"},
            template=PLOTLY_TEMPLATE,
        )
        fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=340, coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        # Company-wise margin table
        st.markdown("#### 🏢 Company-wise Actual Margin (GST-adjusted)")
        comp_margin = margins["by_company"].copy()
        comp_margin = comp_margin.sort_values("real_margin_pct", ascending=False)
        comp_margin["real_margin_pct"] = comp_margin["real_margin_pct"].round(1)
        st.dataframe(
            comp_margin[["company", "real_margin_pct", "total_revenue", "num_products"]].head(15),
            use_container_width=True,
            hide_index=True,
            column_config={
                "real_margin_pct": st.column_config.ProgressColumn(
                    "Margin %", min_value=0, max_value=25, format="%.1f%%"
                ),
                "total_revenue": st.column_config.NumberColumn("Revenue (₹)", format="₹%.0f"),
            }
        )

    # ── Category × Month Heatmap ──────────────────────────────────────────────
    st.markdown("#### 🔥 Category × Month Revenue Heatmap")
    if not heatmap_df.empty:
        fig3 = px.imshow(
            heatmap_df,
            color_continuous_scale="Viridis",
            aspect="auto",
            title=None,
            template=PLOTLY_TEMPLATE,
        )
        fig3.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=360)
        st.plotly_chart(fig3, use_container_width=True)

    # ── Top & Bottom products ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    prod_margin = margins["by_product"].copy()
    with col1:
        st.markdown("#### 🏆 Top 10 Products by Margin")
        st.dataframe(
            prod_margin.nlargest(10, "real_margin_pct")[
                ["product_name", "category", "company", "real_margin_pct"]
            ].round(2),
            use_container_width=True, hide_index=True,
            column_config={
                "real_margin_pct": st.column_config.ProgressColumn(
                    "Margin %", min_value=0, max_value=30, format="%.1f%%"
                ),
            }
        )
    with col2:
        st.markdown("#### 📉 Bottom 10 Products by Margin")
        st.dataframe(
            prod_margin.nsmallest(10, "real_margin_pct")[
                ["product_name", "category", "company", "real_margin_pct"]
            ].round(2),
            use_container_width=True, hide_index=True,
            column_config={
                "real_margin_pct": st.column_config.ProgressColumn(
                    "Margin %", min_value=0, max_value=30, format="%.1f%%"
                ),
            }
        )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6 — RECOMMENDATIONS (SHOWPIECE)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🎯 Recommendations":
    if "sales_df" not in st.session_state:
        st.warning("Please upload data or go to Upload & Overview page first."); st.stop()

    st.markdown("""
    <div class="page-header">
        <h1>🎯 AI Recommendations</h1>
        <p>Prioritized plain-English business actions · CEO Morning Briefing · ₹ Impact Scoring</p>
    </div>
    """, unsafe_allow_html=True)

    sales_df = st.session_state["sales_df"]
    inv_df   = st.session_state["inv_df"]
    cust_df  = st.session_state["cust_df"]

    with st.spinner("Running all ML models and analytics..."):
        dead_stock_df  = _get_dead_stock(st.session_state["inv_hash"], inv_df)
        outstanding_df = _get_outstanding(st.session_state["sales_hash"], st.session_state["cust_hash"], sales_df, cust_df)
        segment_df     = _get_segments(st.session_state["sales_hash"], st.session_state["cust_hash"], sales_df, cust_df)
        anomaly_df     = _get_anomalies(st.session_state["sales_hash"], sales_df)
        spike_df       = _get_forecast_spikes(st.session_state["sales_hash"], st.session_state["inv_hash"], sales_df, inv_df)

        all_recs = generate_recommendations(
            dead_stock_df=dead_stock_df,
            outstanding_df=outstanding_df,
            forecast_alerts=spike_df,
            segment_df=segment_df,
            anomaly_df=anomaly_df,
        )

    # ── CEO Morning Briefing ──────────────────────────────────────────────────
    briefing = ceo_morning_briefing(all_recs)
    total_opportunity = sum(getattr(r, "impact_rupees", 0) for r in all_recs)

    st.markdown(f"""
    <div class="ceo-box">
        <h3>☀️ CEO Morning Briefing</h3>
        <p>{briefing}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Summary metrics ────────────────────────────────────────────────────────
    high_count   = sum(1 for r in all_recs if getattr(r, "priority", "") == "HIGH")
    medium_count = sum(1 for r in all_recs if getattr(r, "priority", "") == "MEDIUM")
    low_count    = sum(1 for r in all_recs if getattr(r, "priority", "") == "LOW")

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("💰 Total Opportunity", fmt_inr(total_opportunity))
    with col2: st.metric("🔴 HIGH Priority", high_count)
    with col3: st.metric("🟡 MEDIUM Priority", medium_count)
    with col4: st.metric("🟢 LOW Priority", low_count)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Filter buttons ─────────────────────────────────────────────────────────
    col_filters = st.columns(6)
    categories = ["All", "Inventory", "Payment", "Customer", "Sales", "Anomaly"]
    selected_cat = st.session_state.get("rec_filter", "All")

    for i, cat in enumerate(categories):
        with col_filters[i]:
            if st.button(cat, key=f"rec_btn_{cat}",
                         type="primary" if selected_cat == cat else "secondary",
                         use_container_width=True):
                st.session_state["rec_filter"] = cat
                st.rerun()

    selected_cat = st.session_state.get("rec_filter", "All")
    if selected_cat != "All":
        display_recs = filter_by_category(all_recs, selected_cat)
    else:
        display_recs = all_recs

    # ── Recommendation Cards ──────────────────────────────────────────────────
    st.markdown(f"#### Showing {len(display_recs)} recommendations")

    for rec in display_recs:
        priority    = getattr(rec, "priority", "LOW")
        title       = getattr(rec, "title", "")
        message     = getattr(rec, "message", "")
        impact      = getattr(rec, "impact_rupees", 0)
        category    = getattr(rec, "category", "")
        icon_map    = {"Inventory": "📦", "Payment": "💰", "Customer": "👤",
                       "Sales": "📈", "Anomaly": "⚠️"}
        icon = icon_map.get(category, "🔔")

        st.markdown(f"""
        <div class="rec-card {priority}">
            <span class="rec-priority">{priority}</span>
            &nbsp;&nbsp;<span style="color:rgba(255,255,255,0.5);font-size:0.8rem">{icon} {category}</span>
            <div class="rec-title">{title}</div>
            <div class="rec-message">{message}</div>
            <div class="rec-impact">💰 Estimated Impact: {fmt_inr(impact)}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── What-If Scenario ──────────────────────────────────────────────────────
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.markdown("#### 🔧 What-If Scenario Analyzer")
    st.caption("Estimate recovery if you apply a clearance discount to dead stock")

    col1, col2 = st.columns([1, 2])
    with col1:
        discount_pct = st.slider("Clearance Discount %", 5, 40, 15, key="whatif_discount")
        dead_stock_df_local = _get_dead_stock(st.session_state["inv_hash"], inv_df)
        dead_only = dead_stock_df_local[dead_stock_df_local["stock_status"] == "DEAD"].copy()

        if not dead_only.empty:
            recoverable = (
                dead_only["current_stock"] *
                dead_only["purchase_price"] *
                (1 + (dead_only["mrp"] / dead_only["purchase_price"] - 1) * (1 - discount_pct / 100))
            ).sum()
            blocked     = dead_only["capital_blocked"].sum()
            recovery_pct = (recoverable / blocked * 100) if blocked > 0 else 0

            st.metric("Estimated Recovery", fmt_inr(recoverable),
                      delta=f"{recovery_pct:.0f}% of blocked capital")

    with col2:
        if not dead_only.empty:
            dead_only["recovery_estimate"] = (
                dead_only["current_stock"] *
                dead_only["purchase_price"] *
                (1 + (dead_only["mrp"] / dead_only["purchase_price"] - 1) * (1 - discount_pct / 100))
            )
            fig = px.bar(
                dead_only.nlargest(10, "recovery_estimate"),
                x="recovery_estimate", y="product_name", orientation="h",
                color="recovery_estimate",
                color_continuous_scale="Teal",
                title=f"Top 10 Recovery Opportunity at {discount_pct}% Clearance",
                template=PLOTLY_TEMPLATE,
                labels={"recovery_estimate": "Recovery (₹)", "product_name": "Product"},
            )
            fig.update_layout(height=340, margin=dict(l=0,r=0,t=40,b=0),
                              coloraxis_showscale=False,
                              yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
