# Wholesale BI System — Agent Edition
### An AI Agent for Indian Wholesale Distributors

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red?logo=streamlit)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/LLM-Gemini%20Flash-orange?logo=google)](https://aistudio.google.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![MLflow](https://img.shields.io/badge/MLflow-2.13-blue?logo=mlflow)](https://mlflow.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## What This Is

A **business intelligence system built as an AI agent** — not a dashboard.

It takes raw ERP exports (Kuber / Tally / Marg CSV) → cleans → runs ML → and then lets you **ask questions in plain English** and get grounded, data-backed answers.

```
User: "Which customers are most likely to not pay me this month?"

Agent Thought: I need outstanding payments + customer risk scores.
Agent Action:  get_payment_risk_scores()
Observation:   Ramesh Traders — ₹47,000 overdue, 94 days, declining trend.
Agent Action:  get_customer_segments()
Observation:   Ramesh Traders = "At Risk" segment for 3 months.
Agent Answer:  "Ramesh Traders is your highest default risk — ₹47,000 overdue
               for 94 days with a 3-month sales decline. Call today.
               Here's a suggested WhatsApp script: ..."
```

**This is not RAG. Not a chatbot wrapper. A ReAct agent that selects tools, calls them, observes results, and reasons to a grounded answer.**

---

## Architecture

```
Natural Language Question
         ↓
   WholesaleAgent (ReAct Loop)
    ├── Thought: What tool do I need?
    ├── Action: call tool from registry
    ├── Observation: real data from ML engine
    └── Repeat → Final Answer (grounded in real numbers)
         ↓
   LLM Layer (Gemini Flash → Groq → Rule-based fallback)
         ↓
   Tool Registry (8 tools wrapping existing ML modules)
    ├── get_dead_stock()           → analytics.detect_dead_stock()
    ├── get_outstanding_payments() → analytics.get_outstanding_payments()
    ├── get_payment_risk_scores()  → payment_intelligence.score_payment_risk()
    ├── get_customer_segments()    → segmentation.segment_customers()
    ├── get_anomalies()            → anomaly_detector.detect_anomalies()
    ├── get_restock_alerts()       → forecasting.detect_demand_spikes()
    ├── get_morning_briefing()     → recommender.ceo_morning_briefing()
    └── get_area_performance()     → analytics.area_sales_ranking()
         ↓
   ML Engine (existing, unchanged)
    ├── Prophet demand forecasting (Indian festival seasonality)
    ├── RFM + K-Means customer segmentation
    ├── Isolation Forest anomaly detection
    ├── Gradient Boosting payment default predictor  ← NEW
    └── Rule-based analytics (dead stock, margins, payments)
         ↓
   Streamlit Dashboard (7 pages) + FastAPI (6 endpoints)
```

---

## ML & AI Features

### New in Agent Edition

| Feature | What It Does | Razorpay Parallel |
|---|---|---|
| **ReAct Agent** | Reason → Act → Observe loop over business data | Slash, Agent Studio |
| **Payment Default Predictor** | GBM classifier: 7 features → collection probability 0–100% | Razorpay Capital risk scoring |
| **Collection Message Generator** | Personalized WhatsApp/call script per customer, tone by risk tier | Call-E |
| **Conversational BI** | Natural language Q&A grounded in real data | Slash |

### From v1 (unchanged, still running)

| Feature | Method | What Makes It Real |
|---|---|---|
| Demand Forecasting | **Facebook Prophet** + Indian festival regressors | Diwali, Holi, Eid, Navratri, Dussehra dates from PIB India |
| Customer Segmentation | **RFM + K-Means** (k=4, silhouette validated) | Champions → Loyal → At Risk → Lost |
| Anomaly Detection | **Isolation Forest** (contamination=0.05) | Per-transaction discount/price/qty flags |
| Dead Stock | Rule-based (30/60/90-day thresholds) | Capital blocked ₹ calculation |
| Outstanding Payments | Sigmoid urgency score formula | Risk HIGH/MEDIUM/LOW |
| GST-Aware Margins | Category-specific GST rates | Benchmarked vs HUL/ITC annual reports |
| QPS Claim Calculator | Invoice-level scheme cross-reference | Tracks free-goods claims owed by FMCG companies |

---

## Payment Default Predictor — Technical Detail

The `engine/payment_intelligence.py` module scores every customer on:

```python
features = [
    "max_days_overdue",        # How long outstanding
    "total_overdue_amount",    # ₹ at risk
    "sales_trend_3m",          # Revenue declining = higher risk
    "avg_days_to_pay",         # Historical payment speed
    "payment_count",           # Loyalty proxy
    "days_since_last_sale",    # Recency
    "overdue_invoice_count",   # Breadth of problem
]
```

**Model:** `GradientBoostingClassifier` (n_estimators=50, max_depth=3).  
Falls back to rule-based scoring when data is insufficient for ML.

**Output:**
```
customer_name        | collection_probability | risk_tier    | recommended_action
Ramesh Traders       | 23%                    | HIGH RISK    | Personal Visit
Sunita General Store | 67%                    | MEDIUM RISK  | Call Today
Patel & Co.          | 91%                    | LOW RISK     | Routine Follow-up
```

This is architecturally identical to how Razorpay Capital scores lending risk — same principle, different domain.

---

## Agent Implementation — Why ReAct from Scratch

This project does **not** use LangChain or LangGraph. The ReAct loop is ~150 lines of Python (`engine/ai_agent.py`).

**Why:** Writing it from scratch forces clarity on what an agent actually is:
1. A prompt that tells the LLM what tools exist
2. A parser that extracts the tool call from the LLM response
3. A runner that calls the tool and appends the observation
4. A loop that continues until the LLM writes "Final Answer:"

That's it. No framework magic. Just a loop, a parser, and tools.

```python
# The core of engine/ai_agent.py
for step_num in range(MAX_REACT_STEPS):
    llm_response = llm.generate(build_react_prompt(question, history))
    thought, action, args, is_final = parse_llm_response(llm_response)

    if is_final:
        return extract_final_answer(llm_response)

    observation = tools[action].call(**args)
    history.append(AgentStep(thought, action, args, observation))
```

---

## LLM Strategy — No Paid Key Required

The agent tries providers in priority order:

```
1. Google Gemini Flash  → set GEMINI_API_KEY (free at aistudio.google.com)
2. Groq Llama 3         → set GROQ_API_KEY   (free at console.groq.com)
3. Rule-based fallback  → always works, no key needed
```

Even in fallback mode, the full agent architecture is visible:
- Tool selection heuristics run
- Observations are collected from real data
- Reasoning trace is shown in the UI

---

## Project Structure

```
wholesale-bi-system-agent-edition/
│
├── engine/
│   ├── ai_agent.py             ← ReAct agent + tool registry + LLM client [NEW]
│   ├── payment_intelligence.py ← GBM payment default predictor              [NEW]
│   ├── data_cleaner.py         ← Canonical schema standardizer
│   ├── analytics.py            ← Dead stock, payments, margins, areas
│   ├── scoring.py              ← Urgency + risk scoring formulas
│   ├── forecasting.py          ← Prophet demand forecasting + MLflow
│   ├── segmentation.py         ← RFM + K-Means + silhouette validation
│   ├── anomaly_detector.py     ← Isolation Forest + MLflow
│   ├── qps_engine.py           ← QPS claim calculator (FMCG scheme tracker)
│   └── recommender.py          ← Recommendation engine + CEO Morning Briefing
│
├── app/
│   └── streamlit_app.py        ← 7-page dashboard (Page 7: AI Business Analyst) [UPDATED]
│
├── api/
│   └── main.py                 ← FastAPI (6 endpoints + Pydantic validation)
│
├── data/
│   ├── demo_sales.csv          ← 2 years synthetic transactions (WPI-calibrated)
│   ├── demo_inventory.csv      ← Stock snapshot
│   └── demo_customers.csv      ← Customer master
│
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Running Locally

```bash
# 1. Install
pip install -r requirements.txt

# 2. Run dashboard (7 pages including AI Analyst)
streamlit run app/streamlit_app.py

# 3. (Optional) Set LLM key for full agent reasoning
export GEMINI_API_KEY=your_key_here   # free at aistudio.google.com

# 4. (Optional) Run FastAPI
uvicorn api.main:app --reload --port 8000
```

---

## Streamlit Dashboard — 7 Pages

| Page | What It Shows |
|---|---|
| **1. Upload & Overview** | File uploader, 4 KPI cards, town distribution |
| **2. Inventory Intelligence** | Dead stock table, capital blocked donut |
| **3. Payment Collection** | Risk-sorted outstanding, WhatsApp message generator |
| **4. Customer Intelligence** | RFM segments, cohort retention |
| **5. Sales & Profitability** | Monthly trend, GST margins, category heatmap |
| **6. Recommendations** | CEO Morning Briefing, priority cards, What-If scenario |
| **7. 🤖 AI Business Analyst** | ReAct chat UI, reasoning trace, payment risk ML table |

---

## Business Context

- **Target:** Small/medium wholesale distributors (₹5Cr–₹50Cr turnover)
- **Inspired by:** Real wholesale business, Uniara, Tonk District, Rajasthan
- **ERP Compatible:** Kuber ERP, Tally, Marg (canonical schema standardizer)
- **Data:** Synthetic, calibrated against WPI inflation data (Office of Economic Adviser, India) and HUL/ITC/Britannia FMCG margin benchmarks

---

## What I Would Build at Razorpay

If I joined the AI team, the three things I'd build immediately:

1. **Merchant Morning Briefing Agent** — Every Razorpay merchant gets a daily WhatsApp/email from an agent that analyzes their payment patterns, flags unusual drops, and suggests actions. Runs overnight, grounded in real transaction data. Exact same architecture as what's in this project.

2. **Payment Failure Root Cause Agent** — When a merchant's success rate drops, an agent investigates automatically: checks gateway health, card type breakdown, time-of-day patterns, and returns a plain-English diagnosis. Today this requires a human analyst.

3. **Collection Intelligence for Razorpay Capital** — Score SME borrowers on payment behavior signals beyond CIBIL: invoice aging, buyer diversification, seasonal patterns. The payment_intelligence.py module in this project is a direct prototype of this.

---

## Developer

**Rahul Jain**
BTech AI & Data Science | JECRC Foundation, Jaipur, Rajasthan
GitHub: [@rahul-jain-dev](https://github.com/rahul-jain-dev)

---

## License

MIT License — free for personal, academic, and commercial use.
