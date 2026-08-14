# AI-Powered Wholesale BI System
### Decision Support for Indian Wholesale Distributors

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red?logo=streamlit)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![MLflow](https://img.shields.io/badge/MLflow-2.13-blue?logo=mlflow)](https://mlflow.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 🎯 What This System Does

Takes raw ERP exports (Kuber / Tally / Marg CSV) → cleans → runs analytics + ML → outputs **plain English prioritized business recommendations**.

**Not a dashboard. A decision support system.**

> *"Call Ramesh today — ₹47,000 overdue 94 days"*  
> *"Order Britannia biscuits this week — stock runs out in 8 days"*  
> *"Clear Patanjali shampoo 400ml — dead 78 days, ₹12,000 blocked"*

---

## 🏢 Business Context

- **Target User:** Small/medium wholesale distributors in India (₹5Cr–₹50Cr turnover)
- **Inspired by:** Real wholesale business in Uniara, Tonk District, Rajasthan using Kuber ERP
- **Service Area:** Uniara, Tonk, Deoli, Niwai, Malpura, Todaraisingh, Khanpur, Sawai Madhopur
- **ERP Compatible:** Kuber ERP, Tally, Marg ERP (via canonical schema standardizer)

---

## 🧠 ML & Analytics Features

| Feature | Method | Validation |
|---------|--------|------------|
| Dead Stock Detection | Rule-based (30/60/90-day thresholds) | Capital blocked ₹ calculation |
| Outstanding Payment Tracker | Urgency scoring formula | Risk level HIGH/MEDIUM/LOW |
| Demand Forecasting | **Facebook Prophet** with Indian festival holidays | MAE/RMSE on 30-day holdout |
| Customer Segmentation | **RFM + K-Means** (k=4) | Silhouette Score + Elbow Method |
| Anomaly Detection | **Isolation Forest** (contamination=0.05) | Precision on labeled anomaly set |
| GST-Aware Margins | Rule-based (category-specific GST rates) | Benchmarked vs HUL/ITC annual reports |
| Recommendations | Weighted urgency score + rule engine | Business impact in ₹ |

### Prophet Seasonality — Real Indian Festivals
Custom holiday regressors built from real dates (PIB India calendar):
- **Diwali** (2023-11-12, 2024-11-01)
- **Holi** (2023-03-08, 2024-03-25)
- **Navratri** (2023-10-15, 2024-10-03)
- **Dussehra** (2023-10-24, 2024-10-12)
- **Eid ul-Fitr** (2023-03-30, 2024-04-10)

### Data Calibration
Synthetic data calibrated against:
- **WPI (Wholesale Price Index):** 8.5% FMCG inflation FY2022-23, 3.8% FY2023-24 — *Office of Economic Adviser, India*
- **FMCG margin benchmarks:** HUL 12-18%, Britannia 8-14%, Patanjali 6-12% — *published annual reports*

---

## 🏗️ Architecture

```
CSV Upload (Kuber / Tally / Marg)
           ↓
  data_cleaner.py  ← Canonical Schema Standardizer
           ↓
  analytics.py     ← Dead stock + Payments + Margins + Areas
     ↓        ↓              ↓
forecasting  segmentation  anomaly_detector
(Prophet)    (RFM+KMeans)  (IsoForest)
     ↓        ↓              ↓
          recommender.py
     (Plain English + ₹ impact + CEO Briefing)
               ↓
    streamlit_app.py (5-page dashboard)
               ↓
        FastAPI (api/main.py)
               ↓
     Docker → Streamlit Cloud
```

### Canonical Schema Design
The `standardizer` in `data_cleaner.py` maps any ERP export format to one internal standard.
Only this function changes when connecting to real Kuber data — **zero changes** to ML engine.

```
Kuber Excel Export  →  standardizer()  →  Canonical DataFrame  →  ML Engine
Tally CSV Export    →  standardizer()  →  Canonical DataFrame  →  ML Engine
Synthetic CSV       →  standardizer()  →  Canonical DataFrame  →  ML Engine
```

---

## 📁 Project Structure

```
wholesale-bi-system/
│
├── data/
│   ├── data_generator.py      ← Synthetic data with WPI + festival calibration
│   ├── sales_data.csv         ← 2 years of transactions (generated)
│   ├── inventory_data.csv     ← Stock snapshot (generated)
│   ├── customer_data.csv      ← Customer master (generated)
│   └── purchase_data.csv      ← Purchase history (generated)
│
├── engine/
│   ├── data_cleaner.py        ← Canonical schema standardizer
│   ├── analytics.py           ← Business analytics (dead stock, payments, margins)
│   ├── scoring.py             ← Urgency + risk scoring formulas
│   ├── forecasting.py         ← Prophet demand forecasting + MLflow
│   ├── segmentation.py        ← RFM + K-Means + Silhouette validation + MLflow
│   ├── anomaly_detector.py    ← Isolation Forest + MLflow
│   └── recommender.py         ← Recommendation engine + CEO Morning Briefing
│
├── api/
│   └── main.py                ← FastAPI (5 endpoints + Pydantic validation)
│
├── app/
│   └── streamlit_app.py       ← 5-page premium Streamlit dashboard
│
├── notebooks/
│   └── exploration.ipynb      ← EDA and ML validation
│
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate synthetic data
```bash
python data/data_generator.py
```

### 3. Run the dashboard
```bash
streamlit run app/streamlit_app.py
```

### 4. Run the API (optional)
```bash
uvicorn api.main:app --reload --port 8000
# API docs at: http://localhost:8000/docs
```

### 5. View MLflow experiments
```bash
mlflow ui
# Dashboard at: http://localhost:5000
```

---

## 🐳 Docker

```bash
docker build -t wholesale-bi .
docker run -p 8501:8501 wholesale-bi
```

---

## 📊 Streamlit Dashboard — 5 Pages

| Page | What it shows |
|------|--------------|
| **1. Upload & Overview** | File uploader, 4 KPI cards, town distribution, data preview |
| **2. Inventory Intelligence** | Dead stock table (RED/ORANGE/GREEN), top 15 by days unsold, capital blocked donut |
| **3. Payment Collection** | Risk-sorted outstanding table, urgency bars, WhatsApp message generator |
| **4. Sales & Profitability** | Monthly trend, town ranking, GST-adjusted margins, category heatmap |
| **5. Recommendations** | CEO Morning Briefing, priority cards (HIGH/MEDIUM/LOW), What-If scenario |

---

## 🔌 FastAPI Endpoints

```
POST /upload          → Upload CSVs, returns summary stats
GET  /analytics       → Dead stock + payments + margins + area ranking
GET  /forecast        → Prophet demand forecasts + spike alerts
GET  /recommendations → Prioritized recommendation list + CEO briefing
GET  /segments        → RFM K-Means customer segments
GET  /health          → API health check
```

Interactive docs: `http://localhost:8000/docs`

---

## 🤖 ML Model Details

### Facebook Prophet (Demand Forecasting)
- **Why Prophet over LSTM?** Handles missing days + irregular intervals common in small wholesalers. LSTM needs far more data per SKU. Prophet natively supports festival seasonality via custom holiday regressors.
- **Validation:** 30-day holdout MAE/RMSE tracked in MLflow
- **Granularity:** Category-level (not SKU-level) — more reliable with sparse data

### K-Means Customer Segmentation
- **Why K-Means over DBSCAN?** Interpretable, stable segments. RFM clusters are generally globular.
- **k=4 justification:** Validated with Elbow Method + Silhouette Score (plots in `data/`)
- **Segments:** Champions → Loyal → At Risk → Lost

### Isolation Forest (Anomaly Detection)
- **contamination=0.05** — based on expected 5% anomaly rate in small wholesale businesses
- **Features:** discount_pct, quantity, sale_price, margin deviation from product average
- **Output:** anomaly_score + is_anomaly flag per transaction

---

## 📈 Urgency Score Formula

```python
urgency_score = (days_factor * 0.4) + (amount_factor * 0.4) + (trend_factor * 0.2)
```

- `days_factor`: Sigmoid-normalized (90 days = 1.0)
- `amount_factor`: Log-normalized outstanding amount
- `trend_factor`: 3-month sales slope (declining = higher urgency)

---

## 👨‍💻 Developer

**Rahul Jain**  
BTech AI & Data Science | JECRC Foundation, Jaipur, Rajasthan  
GitHub: [@Rahuljain3851](https://github.com/Rahuljain3851)

---

## 📄 License

MIT License — free for personal, academic, and commercial use.
