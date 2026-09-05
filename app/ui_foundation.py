"""
app/ui_foundation.py
====================
Figma-inspired global design system for the Wholesale BI System — Agent Edition.
Sourced from design-reference/figma/src/index.css and App.tsx (READ-ONLY reference).

Contains:
  - Design tokens (TOKENS / T dict)
  - Global CSS injection (inject_global_css)
  - Badge tone system (BADGE_TONES / render_status_badge)
  - Financial formatters (fmt_inr / fmt_number / fmt_percent)
  - Reusable render helpers:
      render_page_header, render_section_header,
      render_kpi_card, render_empty_state, render_error_state,
      render_unavailable_state, render_success_state,
      render_sidebar, render_data_status_sidebar, color_status

DO NOT modify backend logic here. Pure UI primitives only.
"""

from __future__ import annotations
import streamlit as st

# =============================================================================
# DESIGN TOKENS
# =============================================================================

T: dict[str, str] = {
    # Backgrounds
    "app_bg":         "#0B0E14",
    "sidebar_bg":     "#10141B",
    "card":           "#151A23",
    "card_elevated":  "#1A202B",
    # Borders
    "border":         "#232A36",
    "border_strong":  "#2E3644",
    # Text
    "text_primary":   "#E8ECF3",
    "text_secondary": "#9AA4B2",
    "text_muted":     "#6B7482",
    # Accent
    "accent":         "#6D5BF0",
"primary":        "#6D5BF0", # Alias for semantic use
    "accent_hover":   "#7E6FF5",
    "link":           "#8B7CF7",
    # Semantic
    "success":        "#34D399",
    "warning":        "#F5B84C",
    "danger":         "#F0616D",
    "critical":       "#E5484D",
    "info":           "#4C9AFF",
    "gold":           "#E7B93C",
    "orange":         "#F58A4C",
    # Radius
    "radius_card":    "12px",
    "radius_control": "8px",
    "radius_badge":   "999px",
}

# =============================================================================
# BADGE TONE MAP  (status label -> (bg, text_color))
# =============================================================================

BADGE_TONES: dict[str, tuple[str, str]] = {
    "HIGH":           (f"{T['danger']}20",   T["danger"]),
    "MEDIUM":         (f"{T['warning']}20",  T["warning"]),
    "LOW":            (f"{T['success']}20",  T["success"]),
    "PAID":           (f"{T['success']}20",  T["success"]),
    "UNPAID":         (f"{T['danger']}20",   T["danger"]),
    "PARTIAL":        (f"{T['warning']}20",  T["warning"]),
    "OVERDUE":        (f"{T['danger']}20",   T["danger"]),
    "PENDING":        (f"{T['warning']}20",  T["warning"]),
    "RECOVERED":      (f"{T['success']}20",  T["success"]),
    "ESCALATED":      (f"{T['danger']}20",   T["danger"]),
    "WAITING":        (f"{T['info']}20",     T["info"]),
    "WAITING_FOR_PAYMENT": (f"{T['info']}20", T["info"]),
    "FIRST_REMINDER": (f"{T['warning']}20",  T["warning"]),
    "SECOND_REMINDER":(f"{T['orange']}20",   T["orange"]),
    "IDENTIFIED":     (f"{T['info']}20",     T["info"]),
    "STOPPED":        (f"{T['text_muted']}20", T["text_muted"]),
    "NO_PAYMENT":     (f"{T['warning']}20",  T["warning"]),
    "ACTIVE":         (f"{T['success']}20",  T["success"]),
    "SLOW":           (f"{T['warning']}20",  T["warning"]),
    "DEAD":           (f"{T['danger']}20",   T["danger"]),
    "WRITE-OFF":      (f"{T['critical']}20", T["critical"]),
    "LOW RISK":       (f"{T['success']}20",  T["success"]),
    "HIGH RISK":      (f"{T['danger']}20",   T["danger"]),
    "MED RISK":       (f"{T['warning']}20",  T["warning"]),
    "CHURNED":        (f"{T['danger']}20",   T["danger"]),
    "AT RISK":        (f"{T['warning']}20",  T["warning"]),
    "CHAMPIONS":      (f"{T['gold']}20",     T["gold"]),
    "LOYAL":          (f"{T['success']}20",  T["success"]),
    "NEUTRAL":        (T["card_elevated"],   T["text_secondary"]),
    "INFO":           (f"{T['info']}20",     T["info"]),
    "SUCCESS":        (f"{T['success']}20",  T["success"]),
    "WARNING":        (f"{T['warning']}20",  T["warning"]),
    "DANGER":         (f"{T['danger']}20",   T["danger"]),
}


def _badge_colors(label: str) -> tuple[str, str]:
    key = str(label).upper().strip()
    return BADGE_TONES.get(key, (T["card_elevated"], T["text_secondary"]))


# =============================================================================
# GLOBAL CSS INJECTION
# =============================================================================

def inject_global_css() -> None:
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', system-ui, sans-serif; -webkit-font-smoothing: antialiased; }}
.stApp {{ background: {T['app_bg']}; }}
.block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; max-width: 100%; }}
[data-testid="stSidebar"] {{ background: {T['sidebar_bg']} !important; border-right: 1px solid {T['border']}; min-width: 260px !important; max-width: 300px !important; }}
[data-testid="stSidebar"] > div:first-child {{ padding: 0 !important; }}
[data-testid="stSidebarContent"] {{ padding: 0 !important; }}
[data-testid="metric-container"] {{ background: {T['card']}; border: 1px solid {T['border']}; border-radius: {T['radius_card']}; padding: 18px 20px; transition: border-color 0.15s; box-shadow: none; }}
[data-testid="metric-container"]:hover {{ border-color: {T['border_strong']}; transform: none; box-shadow: none; }}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{ font-size: 11px !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.08em; color: {T['text_muted']} !important; }}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{ font-size: 22px !important; font-weight: 600 !important; color: {T['text_primary']} !important; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }}
[data-testid="stDataFrame"] {{ border: 1px solid {T['border']}; border-radius: {T['radius_card']}; overflow: hidden; }}
[data-testid="stExpander"] {{ background: {T['card']}; border: 1px solid {T['border']}; border-radius: {T['radius_card']}; }}
[data-testid="stExpander"] summary {{ font-size: 13px; font-weight: 500; color: {T['text_secondary']}; }}
.stButton > button {{ background: {T['accent']}; color: white; border: none; border-radius: {T['radius_control']}; font-size: 13px; font-weight: 500; padding: 8px 18px; transition: background 0.15s; }}
.stButton > button:hover {{ background: {T['accent_hover']}; color: white; border: none; }}
.stButton > button[kind="secondary"] {{ background: transparent; border: 1px solid {T['border']}; color: {T['text_secondary']}; }}
.stButton > button[kind="secondary"]:hover {{ border-color: {T['border_strong']}; color: {T['text_primary']}; background: {T['card_elevated']}; }}
[data-testid="stFileUploader"] {{ border: 2px dashed rgba(109,91,240,0.35); border-radius: {T['radius_card']}; padding: 12px; background: rgba(109,91,240,0.05); }}
[data-testid="stAlert"] {{ border-radius: {T['radius_control']}; border-left-width: 3px; font-size: 13px; }}
/* Chat UI Enhancements */
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {{
    flex-direction: row-reverse;
}}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) div[data-testid="stMarkdownContainer"] {{
    background-color: {T['primary']};
    color: white;
    padding: 10px 16px;
    border-radius: 18px 18px 4px 18px;
    display: inline-block;
}}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) div[data-testid="chatAvatarIcon-user"] {{
    display: none;
}}

[data-testid="stChatInput"] {{ background: {T['card']} !important; border: 1px solid {T['border']} !important; border-radius: {T['radius_control']} !important; }}
::-webkit-scrollbar {{ width: 4px; height: 4px; }} ::-webkit-scrollbar-track {{ background: transparent; }} ::-webkit-scrollbar-thumb {{ background: {T['border']}; border-radius: 2px; }} ::-webkit-scrollbar-thumb:hover {{ background: {T['border_strong']}; }}
.section-divider {{ border: none; border-top: 1px solid {T['border']}; margin: 22px 0; }}
.rec-card {{ border-radius: 10px; padding: 15px 18px; margin-bottom: 10px; border: 1px solid {T['border']}; border-left: 3px solid; transition: border-color 0.12s; }}
.rec-card:hover {{ border-color: {T['border_strong']}; }}
.rec-card.HIGH {{ background: {T['card']}; border-left-color: {T['danger']}; }}
.rec-card.MEDIUM {{ background: {T['card']}; border-left-color: {T['warning']}; }}
.rec-card.LOW {{ background: {T['card']}; border-left-color: {T['success']}; }}
.rec-priority {{ font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; display: inline-block; margin-bottom: 7px; }}
.HIGH .rec-priority {{ background: rgba(240,97,109,0.18); color: {T['danger']}; }}
.MEDIUM .rec-priority {{ background: rgba(245,184,76,0.18); color: {T['warning']}; }}
.LOW .rec-priority {{ background: rgba(52,211,153,0.18); color: {T['success']}; }}
.rec-title {{ font-size: 13px; font-weight: 600; color: {T['text_primary']}; margin: 4px 0; }}
.rec-message {{ font-size: 12px; color: {T['text_secondary']}; line-height: 1.6; }}
.rec-impact {{ font-size: 12px; font-weight: 600; color: {T['success']}; margin-top: 8px; }}
.ceo-box {{ background: {T['card']}; border: 1px solid rgba(109,91,240,0.35); border-radius: {T['radius_card']}; padding: 20px 24px; margin-bottom: 20px; }}
.ceo-box h3 {{ color: {T['link']}; font-size: 10px; letter-spacing: 0.12em; font-weight: 600; text-transform: uppercase; margin: 0 0 10px 0; }}
.ceo-box p {{ color: {T['text_primary']}; font-size: 14px; line-height: 1.75; margin: 0; }}
.top-bar {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid {T['border']}; }}
.top-bar-meta {{ font-size: 11px; color: {T['text_muted']}; line-height: 1.6; text-align: right; }}
.top-bar-meta b {{ color: {T['text_secondary']}; }}
.badge {{ display: inline-block; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; padding: 3px 8px; border-radius: 999px; white-space: nowrap; }}
.fin {{ font-variant-numeric: tabular-nums; }}

/* ── Sidebar Nav Rail ────────────────────────────────────────────────────── */
/* Hide the round radio circle input */
[data-testid="stSidebar"] .stRadio input[type="radio"] {{
    display: none !important;
}}
/* Container for radio options — vertical list with controlled gap */
[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] {{
    gap: 1px !important;
    display: flex !important;
    flex-direction: column !important;
    padding: 0 8px !important;
}}
/* Each radio option wrapper */
[data-testid="stSidebar"] .stRadio div[data-baseweb="radio"] {{
    position: relative !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}}
/* The label text row */
[data-testid="stSidebar"] .stRadio label {{
    display: flex !important;
    align-items: center !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    color: {T['text_secondary']} !important;
    padding: 8px 10px 8px 12px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    transition: background 0.12s, color 0.12s !important;
    margin: 0 !important;
    border-left: 2px solid transparent !important;
    background: transparent !important;
    width: 100% !important;
    box-sizing: border-box !important;
    line-height: 1.35 !important;
    white-space: normal !important;
    overflow: visible !important;
}}
/* Hover state */
[data-testid="stSidebar"] .stRadio label:hover {{
    background: rgba(109,91,240,0.08) !important;
    color: {T['text_primary']} !important;
    border-left-color: rgba(109,91,240,0.4) !important;
}}
/* Active state — :has() supported in all modern Chromium-based browsers */
[data-testid="stSidebar"] .stRadio div[data-baseweb="radio"]:has(input:checked) > label {{
    background: rgba(109,91,240,0.14) !important;
    color: {T['text_primary']} !important;
    font-weight: 600 !important;
    border-left: 2px solid {T['accent']} !important;
}}
/* Hide the auto-generated "Navigate" text label above the radio group */
[data-testid="stSidebar"] .stRadio > label {{
    display: none !important;
}}
/* Remove stray margins from the widget wrapper */
[data-testid="stSidebar"] .stRadio {{
    margin: 0 !important;
    padding: 0 !important;
}}
/* Remove stray padding Streamlit injects around sidebar markdown blocks */
[data-testid="stSidebar"] .stMarkdown {{
    padding: 0 !important;
}}
</style>""", unsafe_allow_html=True)


# =============================================================================
# FINANCIAL FORMATTERS
# =============================================================================

def fmt_inr(amount: float) -> str:
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "Rs.-"
    if amount >= 1_00_00_000:
        return f"Rs.{amount / 1_00_00_000:.2f}Cr"
    elif amount >= 1_00_000:
        return f"Rs.{amount / 1_00_000:.1f}L"
    elif amount >= 1_000:
        return f"Rs.{amount / 1_000:.1f}K"
    return f"Rs.{amount:,.0f}"


def fmt_number(v: float, decimals: int = 0) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    if abs(v) >= 1_00_00_000:
        return f"{v / 1_00_00_000:.1f}Cr"
    elif abs(v) >= 1_00_000:
        return f"{v / 1_00_000:.1f}L"
    elif abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:,.{decimals}f}"


def fmt_percent(v: float, decimals: int = 1) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-%"
    if 0.0 <= v <= 1.0:
        v = v * 100
    return f"{v:.{decimals}f}%"


# =============================================================================
# REUSABLE RENDER HELPERS
# =============================================================================

def render_page_header(icon: str, title: str, subtitle: str = "", meta_right: str = "") -> None:
    meta_html = f'<div class="top-bar-meta">{meta_right}</div>' if meta_right else ""
    st.markdown(f"""
<div class="top-bar">
  <div>
    <h1 style="font-size:22px;font-weight:600;color:{T['text_primary']};margin:0 0 4px;letter-spacing:-0.015em;">{icon} {title}</h1>
    <p style="font-size:13px;color:{T['text_secondary']};margin:0;line-height:1.5;">{subtitle}</p>
  </div>
  {meta_html}
</div>""", unsafe_allow_html=True)


def render_section_header(title: str, eyebrow: str = "", description: str = "", divider: bool = True) -> None:
    if divider:
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    eyebrow_html = f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;color:{T["text_muted"]};margin-bottom:5px;">{eyebrow}</div>' if eyebrow else ""
    desc_html = f'<p style="font-size:12px;color:{T["text_secondary"]};margin:4px 0 0;">{description}</p>' if description else ""
    st.markdown(f"""<div style="margin-bottom:14px;">{eyebrow_html}<h2 style="font-size:16px;font-weight:600;color:{T['text_primary']};margin:0;letter-spacing:-0.01em;">{title}</h2>{desc_html}</div>""", unsafe_allow_html=True)


def render_status_badge(label: str) -> str:
    bg, color = _badge_colors(label)
    return f'<span class="badge" style="background:{bg};color:{color};">{label}</span>'


def render_kpi_card(label: str, value: str, subtitle: str = "", tone: str = "neutral") -> None:
    tone_colors = {"neutral": T["text_secondary"], "success": T["success"], "warning": T["warning"], "danger": T["danger"], "info": T["info"]}
    sub_color = tone_colors.get(tone, T["text_secondary"])
    sub_html = f'<div style="font-size:12px;color:{sub_color};font-weight:500;margin-top:5px;">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""<div style="background:{T['card']};border:1px solid {T['border']};border-radius:{T['radius_card']};padding:18px 20px;">
  <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:{T['text_muted']};margin-bottom:8px;">{label}</div>
  <div style="font-size:24px;line-height:30px;font-weight:600;color:{T['text_primary']};font-variant-numeric:tabular-nums;letter-spacing:-0.01em;">{value}</div>
  {sub_html}
</div>""", unsafe_allow_html=True)


def render_empty_state(icon: str = "📭", title: str = "No Data", message: str = "Nothing to display here yet.") -> None:
    st.markdown(f"""<div style="text-align:center;padding:48px 24px;background:{T['card']};border:1px solid {T['border']};border-radius:{T['radius_card']};margin:16px 0;">
  <div style="font-size:32px;margin-bottom:12px;">{icon}</div>
  <div style="font-size:15px;font-weight:600;color:{T['text_primary']};margin-bottom:6px;">{title}</div>
  <div style="font-size:13px;color:{T['text_secondary']};line-height:1.6;">{message}</div>
</div>""", unsafe_allow_html=True)


def render_error_state(title: str = "Something went wrong", message: str = "", details: str = "") -> None:
    details_html = f'<details style="margin-top:12px;text-align:left;"><summary style="font-size:11px;color:{T["text_muted"]};cursor:pointer;">View details</summary><pre style="font-size:11px;color:{T["text_muted"]};margin-top:6px;white-space:pre-wrap;word-break:break-all;">{details}</pre></details>' if details else ""
    st.markdown(f"""<div style="padding:18px 22px;background:rgba(240,97,109,0.08);border:1px solid rgba(240,97,109,0.25);border-radius:{T['radius_card']};margin:10px 0;">
  <div style="font-size:13px;font-weight:600;color:{T['danger']};margin-bottom:4px;">! {title}</div>
  <div style="font-size:12px;color:{T['text_secondary']};line-height:1.6;">{message}</div>{details_html}
</div>""", unsafe_allow_html=True)


def render_unavailable_state(feature: str = "This feature", reason: str = "is unavailable in the current environment.", details: str = "") -> None:
    details_html = f'<details style="margin-top:10px;"><summary style="font-size:11px;color:{T["text_muted"]};cursor:pointer;">Diagnostic details</summary><pre style="font-size:11px;color:{T["text_muted"]};margin-top:6px;white-space:pre-wrap;word-break:break-all;">{details}</pre></details>' if details else ""
    st.markdown(f"""<div style="padding:16px 20px;background:{T['card']};border:1px solid {T['border']};border-radius:{T['radius_card']};margin:10px 0;">
  <div style="font-size:13px;font-weight:600;color:{T['text_muted']};margin-bottom:4px;">&#x1F6AB; {feature}</div>
  <div style="font-size:12px;color:{T['text_secondary']};line-height:1.6;">{reason}</div>{details_html}
</div>""", unsafe_allow_html=True)


def render_success_state(message: str) -> None:
    st.markdown(f"""<div style="padding:12px 16px;background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.25);border-radius:{T['radius_card']};margin:8px 0;">
  <span style="font-size:13px;color:{T['success']};font-weight:500;">&#x2713; {message}</span>
</div>""", unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    st.sidebar.markdown(f"""<div style="padding:16px 16px 12px;border-bottom:1px solid {T['border']};margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:30px;height:30px;border-radius:7px;background:{T['accent']};display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">&#x26A1;</div>
    <div>
      <div style="font-size:13px;font-weight:700;color:{T['text_primary']};line-height:17px;letter-spacing:-0.01em;">Raj Distributors</div>
      <div style="font-size:10px;color:{T['text_muted']};line-height:14px;margin-top:1px;letter-spacing:0.01em;">AI Business Intelligence</div>
    </div>
  </div>
</div>
<div style="padding:0 16px 6px;">
  <div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.09em;color:{T['text_muted']};margin-bottom:4px;">Navigate</div>
</div>""", unsafe_allow_html=True)


def render_data_status_sidebar(loaded_data: dict | None = None) -> None:
    if loaded_data:
        sales_count = loaded_data.get("sales_count", 0)
        cust_count  = loaded_data.get("cust_count", 0)
        sku_count   = loaded_data.get("sku_count", 0)
        months      = loaded_data.get("months", "")
        st.sidebar.markdown(f"""<div style="margin:12px 12px 0;border-top:1px solid {T['border']};padding-top:12px;">
  <div style="background:{T['card']};border:1px solid {T['border']};border-radius:8px;padding:10px 12px;">
    <div style="display:flex;align-items:flex-start;gap:6px;font-size:11px;color:{T['text_secondary']};line-height:17px;">
      <span style="color:{T['success']};font-size:8px;margin-top:3px;flex-shrink:0;">&#9679;</span>
      <span><span style="color:{T['success']};font-weight:600;">ERP Data Connected</span><br>
      {sales_count:,} Sales &nbsp;&middot;&nbsp; {cust_count:,} Customers<br>
      {sku_count:,} SKUs &nbsp;&middot;&nbsp; {months} History</span>
    </div>
  </div>
  <div style="padding:8px 4px 2px;">
    <p style="font-size:10px;color:{T['text_muted']};margin:0;line-height:1.5;opacity:0.5;">Built by Rahul Jain &middot; JECRC Foundation</p>
  </div>
</div>""", unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"""<div style="margin:12px 12px 0;border-top:1px solid {T['border']};padding-top:12px;">
  <div style="background:{T['card']};border:1px solid {T['border']};border-radius:8px;padding:10px 12px;">
    <div style="font-size:11px;color:{T['text_muted']};line-height:17px;">
      <span style="font-size:8px;opacity:0.5;">&#9679;</span>&nbsp; No data loaded<br>
      <span style="font-size:10px;">Load data in &#x26A1; Command Center.</span>
    </div>
  </div>
  <div style="padding:8px 4px 2px;">
    <p style="font-size:10px;color:{T['text_muted']};margin:0;line-height:1.5;opacity:0.5;">Built by Rahul Jain &middot; JECRC Foundation</p>
  </div>
</div>""", unsafe_allow_html=True)


def color_status(val: str) -> str:
    """Legacy pandas Styler helper — backward compat."""
    colors = {
        "DEAD":   "color: #F0616D; font-weight: 700",
        "SLOW":   "color: #F5B84C; font-weight: 700",
        "ACTIVE": "color: #34D399; font-weight: 700",
        "HIGH":   "color: #F0616D; font-weight: 700",
        "MEDIUM": "color: #F5B84C; font-weight: 700",
        "LOW":    "color: #34D399; font-weight: 700",
    }
    return colors.get(str(val).upper(), "")
