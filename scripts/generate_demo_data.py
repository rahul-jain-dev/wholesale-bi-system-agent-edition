"""
scripts/generate_demo_data.py
==============================
Generates three interview-ready demo CSV files for Raj Distributors, Jaipur.
All dates are computed relative to TODAY so every ML model fires correctly.

Run:
    python scripts/generate_demo_data.py
"""

import os
import random
from datetime import date, timedelta

import pandas as pd
import numpy as np

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# Anchor everything to TODAY so models always fire correctly
TODAY     = date.today()
END       = TODAY - timedelta(days=1)          # yesterday = last day of "data"
START     = TODAY - timedelta(days=180)        # 6 months of sales history

def days_ago(n):
    return (TODAY - timedelta(days=n)).strftime("%Y-%m-%d")

def days_from_now(n):
    return (TODAY + timedelta(days=n)).strftime("%Y-%m-%d")

print(f"Generating data: {START} to {END} (today = {TODAY})")

# -----------------------------------------------------------------------------
# 1. CUSTOMERS
# -----------------------------------------------------------------------------
# Designed so analytics produces: Champions, Loyal, At Risk, Lost segments
# Payment risk:  Patel=HIGH(>90d), Agarwal=MEDIUM(45-90d), Rao=LOW(<45d)
CUSTOMERS = [
    # (name, area, type, credit_limit, outstanding, last_order_dago, last_payment_dago, ytd)
    ("Gupta Supermarket",       "Vaishali Nagar", "Supermarket", 200000,  12000,  3,   10,   580000),   # Champion
    ("Sharma General Store",    "Mansarovar",     "Retailer",    80000,   8500,   6,   12,   320000),   # Champion
    ("Verma Kirana",            "Malviya Nagar",  "Retailer",    60000,   5200,   10,  18,   195000),   # Loyal
    ("Jain Provisions",         "C-Scheme",       "Retailer",    75000,   9800,   12,  20,   210000),   # Loyal
    ("Mehta Provision Store",   "Sanganer",       "Retailer",    50000,   18000,  62,  75,   95000),    # At Risk
    ("Singh Brothers",          "Sitapura",       "Wholesaler",  150000,  35000,  80,  95,   180000),   # At Risk
    ("Joshi Traders",           "Sodala",         "Retailer",    40000,   22000,  118, 130,  48000),    # Lost
    ("Patel Stores",            "Tonk Road",      "Retailer",    55000,   48000,  100, 115,  120000),   # HIGH payment risk
    ("Agarwal Mart",            "Raja Park",      "Supermarket", 90000,   31000,  55,  68,   210000),   # MEDIUM payment risk
    ("Rao Wholesale",           "Jhotwara",       "Wholesaler",  120000,  19500,  30,  40,   310000),   # LOW payment risk
]

customers_rows = []
for i, (name, area, ctype, credit, outstanding, lo_dago, lp_dago, ytd) in enumerate(CUSTOMERS):
    customers_rows.append({
        "customer_id":        f"CUST{i+1:03d}",
        "customer_name":      name,
        "area":               area,
        "pincode":            f"30200{i+1}",
        "customer_type":      ctype,
        "credit_limit":       credit,
        "outstanding_amount": outstanding,
        "last_order_date":    days_ago(lo_dago),
        "last_payment_date":  days_ago(lp_dago),
        "total_business_ytd": ytd,
    })

customers_df = pd.DataFrame(customers_rows)
customers_df.to_csv(os.path.join(OUT_DIR, "demo_customers.csv"), index=False)
print(f"[OK] demo_customers.csv - {len(customers_df)} customers")

# -----------------------------------------------------------------------------
# 2. INVENTORY  (last_sale_date relative to today)
# -----------------------------------------------------------------------------
# Purchase price multipliers by category (as % of MRP)
# Chosen so that at average 8.5% discount, real_margin is +8-14% after GST strip
# Snacks/Beverages GST=12%: buy at 70% MRP -> margin ~14%
# Personal Care/Home Care GST=18%: buy at 65% MRP -> margin ~13%
# FMCG/Dairy GST=5%: buy at 78% MRP -> margin ~9%
_PP_MULT = {
    "Snacks":        0.70,
    "Beverages":     0.70,
    "Personal Care": 0.65,
    "Home Care":     0.65,
    "FMCG":          0.78,
    "Dairy":         0.78,
}

def _pp(cat, mrp):
    """Return purchase price for a product given its category and MRP."""
    return round(mrp * _PP_MULT.get(cat, 0.72), 0)

INVENTORY = [
    # (name, category, company, size, stock, mrp, last_sale_dago)
    # purchase_price is calculated automatically by _pp(category, mrp)
    # ACTIVE stock (last sold 1-28 days ago)
    ("Parle-G Biscuit",        "Snacks",       "Parle",     "800g",   450,  55,  2),
    ("Maggi Noodles",          "Snacks",       "Nestle",    "70g",    800,  16,  1),
    ("Colgate MaxFresh",       "Personal Care","Colgate",   "200g",   300,  95,  4),
    ("Surf Excel",             "Home Care",    "HUL",       "1kg",    250,  140, 5),
    ("Vim Dishwash Bar",       "Home Care",    "HUL",       "300g",   600,  28,  3),
    ("Lays Classic",           "Snacks",       "PepsiCo",   "26g",   1200,  13,  1),
    ("Kurkure Masala",         "Snacks",       "PepsiCo",   "90g",    900,  27,  2),
    ("Dettol Soap",            "Personal Care","Reckitt",   "125g",   400,  48,  6),
    ("Clinic Plus Shampoo",    "Personal Care","HUL",       "175ml",  350,  78,  8),
    ("Lifebuoy Soap",          "Personal Care","HUL",       "100g",   500,  28,  10),
    ("Dabur Honey",            "FMCG",         "Dabur",     "500g",   180,  225, 7),
    ("Hajmola Candy",          "FMCG",         "Dabur",     "100pcs", 600,  45,  5),
    ("Real Fruit Juice",       "Beverages",    "Dabur",     "1L",     200,  95,  12),
    ("Frooti Mango Drink",     "Beverages",    "Parle",     "200ml",  800,  13,  3),
    ("7UP PET Bottle",         "Beverages",    "PepsiCo",   "750ml",  350,  40,  4),
    ("Aashirvaad Atta",        "FMCG",         "ITC",       "5kg",    120,  260, 9),
    ("Sunfeast Dark Fantasy",  "Snacks",       "ITC",       "150g",   420,  45,  6),
    ("Yippee Noodles",         "Snacks",       "ITC",       "70g",    650,  17,  2),
    ("Amul Butter",            "Dairy",        "Amul",      "500g",    90,  270, 1),
    ("Amul Cheese Slice",      "Dairy",        "Amul",      "200g",    75,  165, 5),
    ("Good Day Biscuit",       "Snacks",       "Britannia", "200g",   380,  38,  8),
    ("Marie Gold Biscuit",     "Snacks",       "Britannia", "250g",   290,  34,  14),
    # SLOW stock (31-58 days ago)
    ("Tropicana Orange Juice", "Beverages",    "PepsiCo",   "1L",     110,  110, 35),
    ("Cornetto Ice Cream",     "Dairy",        "HUL",       "65ml",   200,  40,  42),
    ("Knorr Soup",             "Snacks",       "HUL",       "44g",    150,  48,  50),
    ("Kissan Jam",             "FMCG",         "HUL",       "500g",    80,  120, 58),
    # DEAD stock (65-165 days ago)
    ("Boost Health Drink",     "Beverages",    "HUL",       "500g",    85,  355, 165),
    ("Horlicks Junior",        "Beverages",    "HUL",       "500g",    60,  465, 158),
    ("Ponds Face Wash",        "Personal Care","HUL",       "100ml",  120,  142, 140),
    ("Brylcreem Hair Cream",   "Personal Care","Reckitt",   "75ml",    95,  110, 130),
    ("Mortein Coil",           "Home Care",    "Reckitt",   "10pcs",  200,  58,  120),
    ("Harpic Toilet Cleaner",  "Home Care",    "Reckitt",   "500ml",   75,  125, 115),
    ("Eno Fruit Salt",         "FMCG",         "GSK",       "100g",   150,  78,  100),
    ("Vicks VapoRub",          "Personal Care","P&G",       "50ml",   110,  148, 65),
]

inv_rows = []
for prod, cat, comp, size, stock, mrp, ls_dago in INVENTORY:
    inv_rows.append({
        "product_name":      prod,
        "category":          cat,
        "company":           comp,
        "size_variant":      size,
        "current_stock":     stock,
        "last_purchase_date": days_ago(ls_dago + 5),
        "last_sale_date":    days_ago(ls_dago),
        "purchase_price":    _pp(cat, mrp),
        "mrp":               mrp,
        "reorder_level":     int(stock * 0.2),
    })

inv_df = pd.DataFrame(inv_rows)
inv_df.to_csv(os.path.join(OUT_DIR, "demo_inventory.csv"), index=False)

active_c = sum(1 for r in INVENTORY if r[6] <= 30)
slow_c   = sum(1 for r in INVENTORY if 31 <= r[6] <= 60)
dead_c   = sum(1 for r in INVENTORY if r[6] > 60)
dead_cap = sum(r[4] * _pp(r[1], r[5]) for r in INVENTORY if r[6] > 60)
print(f"[OK] demo_inventory.csv - {len(inv_df)} SKUs | "
      f"Active={active_c} Slow={slow_c} Dead={dead_c} | "
      f"Dead capital=Rs.{dead_cap:,}")

# -----------------------------------------------------------------------------
# 3. SALES  (6 months, relative to today)
# -----------------------------------------------------------------------------
ACTIVE_PRODUCTS = [p[0] for p in INVENTORY[:26]]  # active + slow only
CUST_AREA = {c[0]: c[1] for c in CUSTOMERS}
PROD_PP   = {p[0]: _pp(p[1], p[5]) for p in INVENTORY}
PROD_MRP  = {p[0]: p[5] for p in INVENTORY}
PROD_CAT  = {p[0]: p[1] for p in INVENTORY}
PROD_COMP = {p[0]: p[2] for p in INVENTORY}
PROD_SIZE = {p[0]: p[3] for p in INVENTORY}

# Orders per month per customer
CUST_FREQ = {
    "Gupta Supermarket":      10,   # Champion - very frequent
    "Sharma General Store":   8,    # Champion
    "Verma Kirana":           6,    # Loyal
    "Jain Provisions":        6,    # Loyal
    "Mehta Provision Store":  5,    # At Risk - was active but stopped 62 days ago
    "Singh Brothers":         4,    # At Risk - was active but stopped 80 days ago
    "Joshi Traders":          3,    # Lost - stopped ordering 118 days ago
    "Patel Stores":           4,    # HIGH payment risk
    "Agarwal Mart":           5,    # MEDIUM payment risk
    "Rao Wholesale":          7,    # LOW payment risk (active)
}

# When each customer STOPPED ordering (days ago). None = still active.
CUST_STOP = {
    "Mehta Provision Store":  62,
    "Singh Brothers":         80,
    "Joshi Traders":          118,
}

# Payment overdue logic -> sets due dates to trigger HIGH/MEDIUM/LOW risk
def get_payment(cust_name, order_date_obj):
    """Returns (payment_status, payment_due_date_str)."""
    due_offset = 30  # standard 30-day credit

    if cust_name == "Patel Stores":
        # HIGH risk: dues from 95+ days ago
        due_date = order_date_obj + timedelta(days=due_offset)
        overdue_days = (TODAY - due_date).days
        if overdue_days > 90:
            return "OVERDUE", due_date.strftime("%Y-%m-%d")
        return "PENDING", due_date.strftime("%Y-%m-%d")

    elif cust_name == "Agarwal Mart":
        # MEDIUM risk: dues 45-90 days overdue
        due_date = order_date_obj + timedelta(days=due_offset)
        overdue_days = (TODAY - due_date).days
        if 45 <= overdue_days <= 90:
            return "OVERDUE", due_date.strftime("%Y-%m-%d")
        return "PENDING", due_date.strftime("%Y-%m-%d")

    elif cust_name == "Rao Wholesale":
        # LOW risk: dues <45 days overdue
        due_date = order_date_obj + timedelta(days=due_offset)
        overdue_days = (TODAY - due_date).days
        if overdue_days > 0:
            return "PENDING", due_date.strftime("%Y-%m-%d")
        return "PENDING", due_date.strftime("%Y-%m-%d")

    elif cust_name in ["Joshi Traders", "Singh Brothers", "Mehta Provision Store"]:
        due_date = order_date_obj + timedelta(days=due_offset)
        return "OVERDUE", due_date.strftime("%Y-%m-%d")

    else:
        # Regular payers
        due_date = order_date_obj + timedelta(days=due_offset)
        overdue_days = (TODAY - due_date).days
        if overdue_days > 0:
            return random.choice(["PAID", "PAID", "PAID", "PENDING"]), due_date.strftime("%Y-%m-%d")
        return "PENDING", due_date.strftime("%Y-%m-%d")

SALESPERSONS = ["Ramesh Kumar", "Suresh Sharma", "Vijay Singh"]
ANOMALY_INVOICES = set()  # we'll mark 2 invoices for anomaly injection

sales_rows = []
invoice_counter = 1000

current = START
while current <= END:
    day_of_month = current.day
    month        = current.month
    days_ago_val = (TODAY - current).days

    # Festival boost: Holi effect (March window relative to START month)
    # We compute a "Holi-like" spike around 4 months before today
    holi_center = TODAY - timedelta(days=120)
    is_festival = abs((current - holi_center).days) <= 7

    # Weekend dip
    is_weekend = current.weekday() >= 5

    day_mult = 2.5 if is_festival else (0.6 if is_weekend else 1.0)

    for cust, freq in CUST_FREQ.items():
        # Check if this customer has stopped ordering
        stop_days = CUST_STOP.get(cust)
        if stop_days and days_ago_val <= stop_days:
            continue  # customer hasn't ordered since stop_days ago

        # Probability of ordering today
        prob = (freq / 22) * day_mult
        if random.random() > prob:
            continue

        invoice_no = f"INV-{invoice_counter:05d}"
        n_items = random.randint(2, 7)
        products = random.sample(ACTIVE_PRODUCTS, min(n_items, len(ACTIVE_PRODUCTS)))

        pay_status, due_date = get_payment(cust, current)

        for prod in products:
            pp  = PROD_PP[prod]
            mrp = PROD_MRP[prod]
            qty = random.randint(5, 60)

            # Normal discount 5-12%
            disc = round(random.uniform(5, 12), 1)

            # Inject anomalies: 2 specific invoices get 38% discount
            if invoice_counter in [1095, 1240]:
                disc = 38.0
                ANOMALY_INVOICES.add(invoice_no)

            sale_price = round(mrp * (1 - disc / 100), 2)

            sales_rows.append({
                "invoice_no":        invoice_no,
                "date":              current.strftime("%Y-%m-%d"),
                "customer_name":     cust,
                "customer_area":     CUST_AREA[cust],
                "product_name":      prod,
                "category":          PROD_CAT[prod],
                "company":           PROD_COMP[prod],
                "size_variant":      PROD_SIZE[prod],
                "quantity":          qty,
                "purchase_price":    pp,
                "sale_price":        sale_price,
                "discount_pct":      disc,
                "salesperson":       random.choice(SALESPERSONS),
                "payment_status":    pay_status,
                "payment_due_date":  due_date,
            })

        invoice_counter += 1

    current += timedelta(days=1)

sales_df = pd.DataFrame(sales_rows)
sales_df.to_csv(os.path.join(OUT_DIR, "demo_sales.csv"), index=False)

total_rev = (sales_df["sale_price"] * sales_df["quantity"]).sum()
n_invoices = sales_df["invoice_no"].nunique()
n_overdue  = sales_df[sales_df["payment_status"] == "OVERDUE"]["invoice_no"].nunique()
print(f"[OK] demo_sales.csv - {len(sales_df):,} rows | {n_invoices} invoices | "
      f"Rs.{total_rev:,.0f} revenue | {n_overdue} overdue invoices")

print()
print("=" * 60)
print("DEMO DATA SUMMARY")
print("=" * 60)
print(f"Date range   : {START} to {END}")
print(f"Customers    : {len(customers_df)} (Champions/Loyal/At Risk/Lost)")
print(f"Inventory    : {len(inv_df)} SKUs (Active={active_c}, Slow={slow_c}, Dead={dead_c})")
print(f"Dead capital : Rs.{dead_cap:,}")
print(f"Sales rows   : {len(sales_df):,}")
print(f"Invoices     : {n_invoices}")
print(f"Overdue inv  : {n_overdue}")
print(f"Anomaly inv  : {list(ANOMALY_INVOICES)}")
print()
print("Upload demo_sales.csv + demo_inventory.csv + demo_customers.csv")
print("to the Streamlit app to see all insights fire correctly.")
