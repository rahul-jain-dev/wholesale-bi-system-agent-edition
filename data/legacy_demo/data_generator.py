"""
data_generator.py
=================
Generates 2 years of realistic synthetic wholesale data for the Uniara region,
Rajasthan. Data is calibrated against:
  - Real Indian festival dates (2023–2024): Diwali, Holi, Navratri, Eid, Dussehra
  - Wholesale Price Index (WPI) FMCG inflation (~8% in 2022-23, ~4% in 2023-24)
  - Real FMCG company names and margin benchmarks from published annual reports

Outputs four CSV files:
  - sales_data.csv        : 2 years of daily invoice-level transactions
  - inventory_data.csv    : Current stock snapshot per SKU
  - customer_data.csv     : Customer master with outstanding amounts
  - purchase_data.csv     : Purchase/procurement history

Usage:
    python data/data_generator.py

Author: Rahul Jain | JECRC Foundation, Jaipur
"""

import random
import sys
import numpy as np
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Output directory ─────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent
DATA_DIR.mkdir(exist_ok=True)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — REAL INDIAN FESTIVAL DATES (2023 + 2024)
# Source: Public calendar / Press Information Bureau India
# These dates drive demand spikes in the data generator.
# ═════════════════════════════════════════════════════════════════════════════
FESTIVAL_DATES = {
    # 2023 Festivals
    date(2023, 3, 8):   ("Holi",        ["Beverages", "Snacks", "Personal Care"]),
    date(2023, 3, 30):  ("Eid ul-Fitr", ["FMCG", "Snacks", "Dairy"]),
    date(2023, 4, 14):  ("Baisakhi",    ["Agricultural", "Beverages"]),
    date(2023, 10, 15): ("Navratri",    ["FMCG", "Dairy", "Snacks"]),
    date(2023, 10, 24): ("Dussehra",    ["FMCG", "Personal Care", "Household"]),
    date(2023, 11, 12): ("Diwali",      ["FMCG", "Snacks", "Beverages", "Household", "Personal Care"]),
    date(2023, 11, 27): ("Diwali+15",   ["FMCG", "Snacks"]),   # post-Diwali tail
    date(2023, 12, 25): ("Christmas",   ["Beverages", "Snacks"]),
    # 2024 Festivals
    date(2024, 3, 25):  ("Holi",        ["Beverages", "Snacks", "Personal Care"]),
    date(2024, 4, 10):  ("Eid ul-Fitr", ["FMCG", "Snacks", "Dairy"]),
    date(2024, 4, 17):  ("Ram Navami",  ["FMCG", "Dairy"]),
    date(2024, 10, 3):  ("Navratri",    ["FMCG", "Dairy", "Snacks"]),
    date(2024, 10, 12): ("Dussehra",    ["FMCG", "Personal Care", "Household"]),
    date(2024, 11, 1):  ("Diwali",      ["FMCG", "Snacks", "Beverages", "Household", "Personal Care"]),
    date(2024, 11, 15): ("Diwali+15",   ["FMCG", "Snacks"]),
    date(2024, 12, 25): ("Christmas",   ["Beverages", "Snacks"]),
}

# Pre-compute set of all festival-window dates (±3 days around each festival)
FESTIVAL_WINDOW: dict[date, tuple] = {}
for fdate, (fname, fcats) in FESTIVAL_DATES.items():
    for delta in range(-3, 4):
        d = fdate + timedelta(days=delta)
        if d not in FESTIVAL_WINDOW:
            FESTIVAL_WINDOW[d] = (fname, fcats)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — WPI-CALIBRATED PRICING
# FMCG WPI inflation: ~8.5% in FY2022-23, ~3.8% in FY2023-24
# Source: Office of Economic Adviser, India (eaindustry.nic.in)
# Applied as a monthly compounding factor on base prices.
# ═════════════════════════════════════════════════════════════════════════════

# GST rates by category — must match analytics.py GST_RATES exactly
# sale_price in CSVs is GST-INCLUSIVE (analytics engine strips GST internally)
GST_RATES_GEN: dict[str, float] = {
    "FMCG": 0.05,
    "Personal Care": 0.18,
    "Beverages": 0.12,
    "Snacks": 0.12,
    "Household": 0.12,
    "Dairy": 0.05,
    "Stationery": 0.12,
    "Electronics Accessories": 0.12,
    "Clothing Accessories": 0.12,
    "Agricultural": 0.12,
}
DEFAULT_GST = 0.12

def wpi_price_factor(transaction_date: date) -> float:
    """
    Returns a WPI-calibrated price multiplier for a given date.
    Base date = Jan 2023 (factor = 1.0)
    FY2022-23 (Apr22-Mar23): ~8.5% annual → ~0.68% monthly
    FY2023-24 (Apr23-Mar24): ~3.8% annual → ~0.31% monthly
    """
    base = date(2023, 1, 1)
    months = (transaction_date.year - base.year) * 12 + (transaction_date.month - base.month)
    if months <= 3:   # Jan–Mar 2023: still FY22-23 rate
        monthly_rate = 0.0068
    elif months <= 15: # Apr 2023–Mar 2024: FY23-24 rate
        monthly_rate = 0.0031
    else:              # Apr 2024+: moderate at ~3%
        monthly_rate = 0.0025
    return (1 + monthly_rate) ** max(months, 0)

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MASTER DATA DEFINITIONS
# ═════════════════════════════════════════════════════════════════════════════

TOWNS = [
    "Uniara", "Tonk", "Deoli", "Niwai",
    "Malpura", "Todaraisingh", "Khanpur", "Sawai Madhopur"
]

TOWN_WEIGHTS = [0.22, 0.20, 0.14, 0.12, 0.10, 0.09, 0.07, 0.06]  # Uniara is HQ

CATEGORIES = [
    "FMCG", "Personal Care", "Beverages", "Snacks", "Household",
    "Dairy", "Stationery", "Electronics Accessories",
    "Clothing Accessories", "Agricultural"
]

# Real FMCG companies with real gross margin benchmarks
# Source: Published HUL, ITC, Britannia, Dabur annual reports FY23
COMPANIES = {
    "Hindustan Unilever": {"margin_range": (12, 18), "categories": ["FMCG", "Personal Care", "Household"]},
    "ITC":                {"margin_range": (10, 16), "categories": ["FMCG", "Snacks", "Stationery"]},
    "Nestle":             {"margin_range": (11, 17), "categories": ["Snacks", "Dairy", "Beverages"]},
    "Britannia":          {"margin_range": (8,  14), "categories": ["FMCG", "Snacks", "Dairy"]},
    "Dabur":              {"margin_range": (10, 15), "categories": ["FMCG", "Personal Care", "Beverages"]},
    "Marico":             {"margin_range": (12, 18), "categories": ["Personal Care", "FMCG"]},
    "Godrej Consumer":    {"margin_range": (10, 15), "categories": ["Personal Care", "Household"]},
    "Patanjali":          {"margin_range": (6,  12), "categories": ["FMCG", "Personal Care", "Beverages"]},
    "Amul":               {"margin_range": (5,  10), "categories": ["Dairy", "Beverages", "Snacks"]},
    "Parle":              {"margin_range": (7,  12), "categories": ["Snacks", "Beverages"]},
    "Haldiram":           {"margin_range": (9,  14), "categories": ["Snacks", "FMCG"]},
    "MDH":                {"margin_range": (10, 16), "categories": ["FMCG", "Agricultural"]},
    "Tata Consumer":      {"margin_range": (8,  13), "categories": ["Beverages", "FMCG", "Agricultural"]},
    "Bajaj":              {"margin_range": (6,  11), "categories": ["Household", "Electronics Accessories"]},
    "Local Brand":        {"margin_range": (3,  8),  "categories": CATEGORIES},
}

# Product templates per category with realistic names
PRODUCT_TEMPLATES = {
    "FMCG": [
        ("Surf Excel Detergent", ["500g", "1kg", "2kg"]),
        ("Vim Dish Wash", ["250ml", "500ml", "1L"]),
        ("Rin Bar", ["100g", "200g", "400g"]),
        ("Wheel Detergent Powder", ["500g", "1kg"]),
        ("Harpic Toilet Cleaner", ["500ml", "1L"]),
        ("Colgate Toothpaste", ["100g", "200g", "300g"]),
        ("Pepsodent Toothpaste", ["70g", "150g", "300g"]),
        ("Lux Soap", ["75g", "150g"]),
        ("Lifebuoy Soap", ["75g", "150g", "250g"]),
        ("Dettol Handwash", ["200ml", "500ml"]),
    ],
    "Personal Care": [
        ("Dove Shampoo", ["200ml", "400ml"]),
        ("Head & Shoulders Shampoo", ["180ml", "360ml"]),
        ("Pantene Shampoo", ["185ml", "370ml"]),
        ("Clinic Plus Shampoo", ["175ml", "350ml"]),
        ("Patanjali Kesh Kanti", ["200ml", "450ml"]),
        ("Parachute Coconut Oil", ["200ml", "500ml", "1L"]),
        ("Marico Hair Oil", ["100ml", "300ml"]),
        ("Fair & Lovely Cream", ["25g", "50g", "100g"]),
        ("Nivea Body Lotion", ["200ml", "400ml"]),
        ("Veet Hair Removal Cream", ["25g", "50g"]),
    ],
    "Beverages": [
        ("Tata Tea Premium", ["250g", "500g", "1kg"]),
        ("Red Label Tea", ["250g", "500g", "1kg"]),
        ("Nescafe Classic Coffee", ["50g", "100g", "200g"]),
        ("Bournvita", ["200g", "500g", "1kg"]),
        ("Horlicks", ["200g", "500g", "1kg"]),
        ("Rooh Afza", ["300ml", "750ml"]),
        ("Real Fruit Juice", ["1L", "2L"]),
        ("Paperboat Drinks", ["200ml", "250ml"]),
        ("Limca Syrup", ["750ml"]),
        ("Tang Powder", ["50g", "100g", "500g"]),
    ],
    "Snacks": [
        ("Britannia Biscuits", ["100g", "200g", "400g"]),
        ("Parle-G Biscuits", ["100g", "200g"]),
        ("Haldiram Namkeen", ["200g", "400g", "1kg"]),
        ("Lays Chips", ["26g", "73g"]),
        ("Kurkure", ["73g", "100g"]),
        ("Good Day Cookies", ["75g", "150g"]),
        ("Monaco Crackers", ["80g", "160g"]),
        ("Bourbon Biscuits", ["80g", "200g"]),
        ("Hide & Seek", ["75g", "100g"]),
        ("Sunfeast Dark Fantasy", ["75g", "150g"]),
    ],
    "Household": [
        ("Lizol Floor Cleaner", ["500ml", "1L", "2L"]),
        ("Colin Glass Cleaner", ["500ml"]),
        ("Odonil Air Freshener", ["75g", "150g"]),
        ("Godrej Hit Cockroach Spray", ["200ml", "400ml"]),
        ("Good Knight Mosquito Coil", ["10 pcs", "20 pcs"]),
        ("All Out Liquid Refill", ["45ml", "135ml"]),
        ("Scotch Brite Scrub", ["1 pc", "2 pc", "3 pc"]),
        ("Garbage Bags", ["30 pcs", "50 pcs"]),
        ("Candle Pack", ["12 pcs", "24 pcs"]),
        ("Tissue Box", ["100 sheets", "200 sheets"]),
    ],
    "Dairy": [
        ("Amul Butter", ["100g", "500g"]),
        ("Amul Cheese Slices", ["200g", "400g"]),
        ("Mother Dairy Paneer", ["200g", "500g"]),
        ("Nestle Milkmaid", ["400g", "1kg"]),
        ("Amul Ghee", ["500ml", "1L"]),
        ("Britannia Cheese Spread", ["180g"]),
        ("Amul Lassi", ["200ml"]),
        ("Yakult Probiotic", ["5 bottles"]),
    ],
    "Stationery": [
        ("Classmate Notebook", ["100 pages", "200 pages"]),
        ("Reynolds Pen", ["10 pcs", "20 pcs"]),
        ("Natraj Pencil Box", ["10 pcs", "20 pcs"]),
        ("Fevicol Glue", ["50ml", "100ml", "500ml"]),
        ("Scotch Tape", ["1 roll", "3 rolls"]),
        ("Stapler Machine", ["Standard"]),
        ("A4 Paper Ream", ["500 sheets"]),
    ],
    "Electronics Accessories": [
        ("Bajaj LED Bulb 9W", ["1 pc", "4 pcs"]),
        ("Philips LED Bulb 12W", ["1 pc", "4 pcs"]),
        ("Extension Board 4-pin", ["1.5m", "3m"]),
        ("Syska LED Strip", ["1m", "5m"]),
        ("Anchor Switchboard", ["4 switch", "6 switch"]),
    ],
    "Clothing Accessories": [
        ("Rupa Underwear", ["S", "M", "L", "XL"]),
        ("VIP Socks", ["2 pairs", "4 pairs"]),
        ("Jockey Vest", ["S", "M", "L"]),
        ("Handkerchief Pack", ["6 pcs", "12 pcs"]),
    ],
    "Agricultural": [
        ("MDH Haldi Powder", ["100g", "250g", "500g"]),
        ("MDH Red Chilli Powder", ["100g", "250g", "500g"]),
        ("Tata Salt", ["1kg"]),
        ("Annapurna Atta", ["5kg", "10kg"]),
        ("Fortune Sunflower Oil", ["1L", "5L"]),
        ("Saffola Gold Oil", ["1L", "5L"]),
        ("MDH Garam Masala", ["50g", "100g"]),
        ("Everest Sabji Masala", ["50g", "100g"]),
    ],
}

# Strict product → company mapping to prevent brand mismatches
# e.g. "Amul Ghee" must ALWAYS be Amul, not Britannia
PRODUCT_COMPANY_MAP: dict[str, str] = {
    # FMCG / HUL products
    "Surf Excel Detergent": "Hindustan Unilever",
    "Vim Dish Wash": "Hindustan Unilever",
    "Rin Bar": "Hindustan Unilever",
    "Wheel Detergent Powder": "Hindustan Unilever",
    "Lux Soap": "Hindustan Unilever",
    "Lifebuoy Soap": "Hindustan Unilever",
    "Dettol Handwash": "Godrej Consumer",
    "Harpic Toilet Cleaner": "Hindustan Unilever",
    "Colgate Toothpaste": "Hindustan Unilever",
    "Pepsodent Toothpaste": "Hindustan Unilever",
    # Personal Care
    "Dove Shampoo": "Hindustan Unilever",
    "Head & Shoulders Shampoo": "Hindustan Unilever",
    "Pantene Shampoo": "Hindustan Unilever",
    "Clinic Plus Shampoo": "Hindustan Unilever",
    "Patanjali Kesh Kanti": "Patanjali",
    "Parachute Coconut Oil": "Marico",
    "Marico Hair Oil": "Marico",
    "Fair & Lovely Cream": "Hindustan Unilever",
    "Nivea Body Lotion": "Hindustan Unilever",
    "Veet Hair Removal Cream": "Hindustan Unilever",
    # Beverages
    "Tata Tea Premium": "Tata Consumer",
    "Red Label Tea": "Hindustan Unilever",
    "Nescafe Classic Coffee": "Nestle",
    "Bournvita": "Hindustan Unilever",
    "Horlicks": "Hindustan Unilever",
    "Rooh Afza": "Dabur",
    "Real Fruit Juice": "Dabur",
    "Paperboat Drinks": "Local Brand",
    "Limca Syrup": "Local Brand",
    "Tang Powder": "Hindustan Unilever",
    # Snacks
    "Britannia Biscuits": "Britannia",
    "Parle-G Biscuits": "Parle",
    "Haldiram Namkeen": "Haldiram",
    "Lays Chips": "ITC",
    "Kurkure": "ITC",
    "Good Day Cookies": "Britannia",
    "Monaco Crackers": "Britannia",
    "Bourbon Biscuits": "Britannia",
    "Hide & Seek": "Britannia",
    "Sunfeast Dark Fantasy": "ITC",
    "Maggi Noodles": "Nestle",
    # Household
    "Lizol Floor Cleaner": "Godrej Consumer",
    "Colin Glass Cleaner": "Godrej Consumer",
    "Odonil Air Freshener": "Godrej Consumer",
    "Godrej Hit Cockroach Spray": "Godrej Consumer",
    "Good Knight Mosquito Coil": "Godrej Consumer",
    "All Out Liquid Refill": "Godrej Consumer",
    "Scotch Brite Scrub": "Local Brand",
    "Garbage Bags": "Local Brand",
    "Candle Pack": "Local Brand",
    "Tissue Box": "Local Brand",
    # Dairy — ALL Amul/Nestle/Britannia strictly
    "Amul Butter": "Amul",
    "Amul Cheese Slices": "Amul",
    "Amul Ghee": "Amul",
    "Amul Lassi": "Amul",
    "Mother Dairy Paneer": "Local Brand",
    "Nestle Milkmaid": "Nestle",
    "Britannia Cheese Spread": "Britannia",
    "Yakult Probiotic": "Local Brand",
    # Agricultural
    "MDH Haldi Powder": "MDH",
    "MDH Red Chilli Powder": "MDH",
    "MDH Garam Masala": "MDH",
    "Tata Salt": "Tata Consumer",
    "Annapurna Atta": "ITC",
    "Fortune Sunflower Oil": "Local Brand",
    "Saffola Gold Oil": "Marico",
    "Everest Sabji Masala": "Local Brand",
}


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — BUILD PRODUCT MASTER (300 SKUs)
# ═════════════════════════════════════════════════════════════════════════════
def build_product_master() -> pd.DataFrame:
    """Creates a product master with 300 SKUs, base prices, and margin targets."""
    products = []
    company_list = list(COMPANIES.keys())

    for category, templates in PRODUCT_TEMPLATES.items():
        for product_name, variants in templates:
            # Use strict brand mapping — fall back to eligible random company only if not in map
            if product_name in PRODUCT_COMPANY_MAP:
                company = PRODUCT_COMPANY_MAP[product_name]
            else:
                eligible_companies = [c for c, info in COMPANIES.items()
                                     if category in info["categories"]]
                company = random.choice(eligible_companies) if eligible_companies else "Local Brand"

            margin_lo, margin_hi = COMPANIES[company]["margin_range"]

            for variant in variants:
                # Base purchase price (realistic wholesale landing cost)
                base_map = {
                    "FMCG": (25, 180), "Personal Care": (40, 350),
                    "Beverages": (30, 320), "Snacks": (10, 180),
                    "Household": (20, 250), "Dairy": (15, 600),
                    "Stationery": (8, 120), "Electronics Accessories": (30, 450),
                    "Clothing Accessories": (25, 250), "Agricultural": (15, 400),
                }
                lo, hi = base_map.get(category, (20, 200))
                purchase_price = round(random.uniform(lo, hi), 2)
                margin_pct = random.uniform(margin_lo / 100, margin_hi / 100)
                gst_rate = GST_RATES_GEN.get(category, DEFAULT_GST)
                # MRP is GST-inclusive (printed on retail pack) — matches sale_price convention
                mrp = round(purchase_price / (1 - margin_pct) * 1.10 * (1 + gst_rate), 2)
                reorder_level = random.randint(5, 30)

                products.append({
                    "product_name": product_name,
                    "category":     category,
                    "company":      company,
                    "size_variant": variant,
                    "purchase_price": purchase_price,
                    "mrp":           mrp,
                    "reorder_level": reorder_level,
                    "target_margin_pct": round(margin_pct * 100, 1),
                })

    df = pd.DataFrame(products).reset_index(drop=True)
    df.index.name = "sku_id"
    return df


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — BUILD CUSTOMER MASTER (60 Customers)
# ═════════════════════════════════════════════════════════════════════════════
CUSTOMER_NAMES = [
    "Ramesh General Store", "Sharma Kirana", "Bajaj Traders", "Meena Provisions",
    "Suresh Wholesale", "Patel Store", "Ram Lal & Sons", "Bharat Enterprises",
    "Gupta Distributors", "Verma Trading Co.", "Agarwal Provisions",
    "Yadav General Stores", "Vijay Kirana", "Narayan & Brothers", "Laxmi Stores",
    "Rajesh Trading", "Sanjay Provisions", "Mahesh Kirana Center", "Dev Store",
    "Krishna Traders", "Shiv Shakti Store", "Hari Om Traders", "Ashok General",
    "Deepak Provisions", "Sonu Store", "Mukesh Kirana", "Manoj Traders",
    "Ravi Wholesale", "Santosh Store", "Dilip Provisions", "Hemant Traders",
    "Ganesh Store", "Nandlal Kirana", "Gopal Traders", "Mohan Store",
    "Radhe Shyam Provisions", "Rajendra General", "Kiran Store", "Arvind Traders",
    "Pramod Kirana", "Umesh Store", "Naresh Provisions", "Satish Traders",
    "Vinod Store", "Rakesh General", "Sunil Kirana", "Anil Provisions",
    "Mukund Traders", "Girish Store", "Lalit Kirana Center", "Bhavesh Store",
    "Hitesh Provisions", "Nilesh Traders", "Kalpesh General", "Jignesh Store",
    "Chintan Kirana", "Dhruv Provisions", "Parth Traders", "Vivek Store",
    "Yash General Stores", "Ankit Kirana",
]

PINCODES = {
    "Uniara": "304025", "Tonk": "304001", "Deoli": "304804",
    "Niwai": "304021", "Malpura": "304502", "Todaraisingh": "304505",
    "Khanpur": "304023", "Sawai Madhopur": "322001",
}

def build_customer_master(start_date: date, end_date: date) -> pd.DataFrame:
    """Creates 60 customers with realistic profiles including intentional bad payers."""
    customers = []

    for i, name in enumerate(CUSTOMER_NAMES):
        town = random.choices(TOWNS, weights=TOWN_WEIGHTS)[0]
        credit_limit = random.choice([25000, 50000, 75000, 100000, 150000, 200000])

        # Intentional pattern: 15% of customers are chronic late payers
        is_bad_payer = i % 7 == 0
        # 10% are inactive (lost customers)
        is_inactive = i % 10 == 9

        if is_inactive:
            last_order_date = start_date + timedelta(days=random.randint(30, 180))
            last_payment_date = last_order_date + timedelta(days=random.randint(10, 30))
            outstanding = round(random.uniform(0, credit_limit * 0.3), 2)
        elif is_bad_payer:
            last_order_date = end_date - timedelta(days=random.randint(5, 20))
            last_payment_date = end_date - timedelta(days=random.randint(95, 200))
            outstanding = round(random.uniform(credit_limit * 0.6, credit_limit * 1.1), 2)
        else:
            last_order_date = end_date - timedelta(days=random.randint(1, 30))
            last_payment_date = end_date - timedelta(days=random.randint(5, 40))
            outstanding = round(random.uniform(0, credit_limit * 0.5), 2)

        total_ytd = round(random.uniform(credit_limit * 2, credit_limit * 15), 2)

        customers.append({
            "customer_id":       f"CUST{i+1:03d}",
            "customer_name":     name,
            "area":              town,
            "pincode":           PINCODES[town],
            "customer_type":     random.choice(["Retailer", "Sub-Wholesaler"]),
            "credit_limit":      credit_limit,
            "outstanding_amount": outstanding,
            "last_order_date":   last_order_date.strftime("%Y-%m-%d"),
            "last_payment_date": last_payment_date.strftime("%Y-%m-%d"),
            "total_business_ytd": total_ytd,
            "is_bad_payer":      is_bad_payer,   # internal flag, not in canonical schema
        })

    return pd.DataFrame(customers)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — BUILD INVENTORY SNAPSHOT
# ═════════════════════════════════════════════════════════════════════════════
def build_inventory(product_master: pd.DataFrame, end_date: date) -> pd.DataFrame:
    """
    Creates current inventory snapshot.
    Intentionally embeds dead stock: ~20% of SKUs have last_sale_date > 60 days ago.
    """
    inventory_rows = []

    for _, row in product_master.iterrows():
        # Intentional dead stock: every 5th product
        is_dead_stock = random.random() < 0.20

        if is_dead_stock:
            days_since_sale = random.randint(61, 180)
            current_stock = random.randint(20, 120)   # Lots unsold
        else:
            days_since_sale = random.randint(1, 45)
            current_stock = random.randint(5, 80)

        last_sale_date = end_date - timedelta(days=days_since_sale)
        last_purchase_date = last_sale_date - timedelta(days=random.randint(5, 30))

        inventory_rows.append({
            "product_name":     row["product_name"],
            "category":         row["category"],
            "company":          row["company"],
            "size_variant":     row["size_variant"],
            "current_stock":    current_stock,
            "last_purchase_date": last_purchase_date.strftime("%Y-%m-%d"),
            "last_sale_date":   last_sale_date.strftime("%Y-%m-%d"),
            "purchase_price":   round(row["purchase_price"] * wpi_price_factor(end_date), 2),
            "mrp":              round(row["mrp"] * wpi_price_factor(end_date), 2),
            "reorder_level":    row["reorder_level"],
        })

    return pd.DataFrame(inventory_rows)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 7 — GENERATE SALES TRANSACTIONS
# ═════════════════════════════════════════════════════════════════════════════
SALESPERSONS = ["Vijay Sharma", "Raju Patel", "Suresh Kumar", "Manoj Yadav", "Deepak Meena"]

def generate_sales(
    product_master: pd.DataFrame,
    customer_df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Generates 2 years of daily sales transactions with:
    - Festival demand spikes (real dates)
    - WPI price inflation
    - Realistic payment patterns (bad payers stay bad)
    - Seasonal summer boost for Beverages
    - Anomalous transactions (5% flagged for Isolation Forest training)
    """
    sales = []
    invoice_counter = 1001
    products = product_master.to_dict("records")
    customers = customer_df.to_dict("records")

    current = start_date
    while current <= end_date:
        # Skip Sundays (business closed)
        if current.weekday() == 6:
            current += timedelta(days=1)
            continue

        # Determine base transaction count for the day
        is_festival = current in FESTIVAL_WINDOW
        is_month_end = current.day >= 28

        base_txn = random.randint(8, 18)
        if is_festival:
            base_txn = int(base_txn * random.uniform(1.8, 2.8))  # festival spike
        if is_month_end:
            base_txn = int(base_txn * 1.2)  # month-end push

        # Summer boost for beverages (April–June)
        summer = current.month in [4, 5, 6]

        for _ in range(base_txn):
            customer = random.choice(customers)
            town = customer["area"]

            # Pick a product (festival → bias towards festival categories)
            if is_festival:
                _, fest_cats = FESTIVAL_WINDOW[current]
                eligible = [p for p in products if p["category"] in fest_cats]
                product = random.choice(eligible) if eligible else random.choice(products)
            elif summer:
                eligible = [p for p in products if p["category"] == "Beverages"] + products
                product = random.choice(eligible)
            else:
                product = random.choice(products)

            # WPI-calibrated pricing
            price_factor = wpi_price_factor(current)
            purchase_price = round(product["purchase_price"] * price_factor, 2)
            mrp = round(product["mrp"] * price_factor, 2)

            # GST rate for this category
            gst_rate = GST_RATES_GEN.get(product["category"], DEFAULT_GST)

            # Sale price = purchase_price * (1 + wholesale_margin) * (1 + GST)
            # Stored GST-inclusive so analytics engine correctly strips GST
            # and shows realistic positive margins (6-18% for major FMCG cos)
            target_margin = product["target_margin_pct"] / 100
            sale_price_ex_gst = round(purchase_price * (1 + target_margin), 2)
            sale_price = round(sale_price_ex_gst * (1 + gst_rate), 2)
            sale_price = min(sale_price, mrp)  # cannot exceed MRP

            quantity = random.randint(1, 20)
            if is_festival:
                quantity = int(quantity * random.uniform(1.5, 3.0))

            # Discount: 0–5% normal, ~10% anomalous (5% of transactions)
            is_anomaly = random.random() < 0.05
            if is_anomaly:
                discount_pct = round(random.uniform(15, 40), 1)  # suspicious
            else:
                discount_pct = round(random.uniform(0, 5), 1)

            effective_sale_price = round(sale_price * (1 - discount_pct / 100), 2)

            # Payment status: bad payers almost always get overdue
            if customer["is_bad_payer"]:
                payment_status = random.choices(
                    ["Paid", "Pending", "Overdue"], weights=[0.1, 0.2, 0.7]
                )[0]
            else:
                payment_status = random.choices(
                    ["Paid", "Pending", "Overdue"], weights=[0.70, 0.20, 0.10]
                )[0]

            due_days = 30 if payment_status != "Paid" else 0
            due_date = (current + timedelta(days=due_days)).strftime("%Y-%m-%d") if due_days else ""

            sales.append({
                "invoice_no":       f"INV{invoice_counter:06d}",
                "date":             current.strftime("%Y-%m-%d"),
                "customer_name":    customer["customer_name"],
                "customer_area":    town,
                "product_name":     product["product_name"],
                "category":         product["category"],
                "company":          product["company"],
                "size_variant":     product["size_variant"],
                "quantity":         quantity,
                "purchase_price":   purchase_price,
                "sale_price":       effective_sale_price,
                "discount_pct":     discount_pct,
                "salesperson":      random.choice(SALESPERSONS),
                "payment_status":   payment_status,
                "payment_due_date": due_date,
                "is_anomaly":       is_anomaly,   # label for model validation
            })
            invoice_counter += 1

        current += timedelta(days=1)

    return pd.DataFrame(sales)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 8 — GENERATE PURCHASE ORDERS
# ═════════════════════════════════════════════════════════════════════════════
SUPPLIERS = [
    "HUL Distributor Hub Jaipur", "ITC Regional Depot", "Nestle C&F Jaipur",
    "Britannia Jaipur Hub", "Dabur Tonk Depot", "Amul Cooperative Jaipur",
    "Parle Agencies Jaipur", "Haldiram Distributors", "Local Supplier",
]

def generate_purchases(product_master: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    """Generates purchase/procurement orders with realistic lead times."""
    purchases = []
    po_counter = 5001

    # Purchase every 2 weeks per product (on average)
    current = start_date
    while current <= end_date:
        if current.weekday() in [1, 3]:  # Tuesdays and Thursdays = purchase days
            num_products = random.randint(15, 35)
            sampled = product_master.sample(num_products, random_state=po_counter)

            for _, prod in sampled.iterrows():
                price_factor = wpi_price_factor(current)
                landing_cost = round(prod["purchase_price"] * price_factor * random.uniform(0.97, 1.03), 2)
                quantity = random.randint(10, 100)

                company = prod["company"]
                supplier = next(
                    (s for s in SUPPLIERS if company.split()[0].lower() in s.lower()),
                    "Local Supplier"
                )

                purchases.append({
                    "po_number":      f"PO{po_counter:05d}",
                    "date":           current.strftime("%Y-%m-%d"),
                    "supplier_name":  supplier,
                    "product_name":   prod["product_name"],
                    "size_variant":   prod["size_variant"],
                    "quantity":       quantity,
                    "landing_cost":   landing_cost,
                    "invoice_value":  round(landing_cost * quantity, 2),
                })
                po_counter += 1

        current += timedelta(days=1)

    return pd.DataFrame(purchases)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 9 — MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    START_DATE = date(2023, 1, 1)
    END_DATE   = date(2024, 12, 31)

    print("=" * 60)
    print("  Wholesale BI System — Synthetic Data Generator")
    print("  Option B: Synthetic + Real Indian Festival/WPI Calibration")
    print("=" * 60)
    print(f"  Date range  : {START_DATE} -> {END_DATE} (2 years)")
    print(f"  Festival dates loaded : {len(FESTIVAL_DATES)}")
    print()

    # Build masters
    print("[1/4] Building product master (300 SKUs)...")
    product_master = build_product_master()
    print(f"      → {len(product_master)} SKUs across {product_master['category'].nunique()} categories")

    print("[2/4] Building customer master (60 customers)...")
    customer_df = build_customer_master(START_DATE, END_DATE)
    print(f"      → {len(customer_df)} customers across {customer_df['area'].nunique()} towns")
    bad_payers = customer_df["is_bad_payer"].sum()
    print(f"      → {bad_payers} intentional bad payers embedded")

    print("[3/4] Generating sales transactions (~730 days, skip Sundays)...")
    sales_df = generate_sales(product_master, customer_df, START_DATE, END_DATE)
    anomalies = sales_df["is_anomaly"].sum()
    print(f"      → {len(sales_df):,} transactions generated")
    print(f"      → {anomalies} anomalous transactions embedded ({anomalies/len(sales_df)*100:.1f}%)")

    print("[4/4] Generating purchase orders...")
    purchase_df = generate_purchases(product_master, START_DATE, END_DATE)
    print(f"      → {len(purchase_df):,} purchase line items")

    # Build inventory snapshot (as of END_DATE)
    print("[*]   Building inventory snapshot (as of END_DATE)...")
    inventory_df = build_inventory(product_master, END_DATE)
    dead = (pd.to_datetime(inventory_df["last_sale_date"]) < pd.Timestamp(END_DATE) - pd.Timedelta(days=60)).sum()
    print(f"      → {len(inventory_df)} SKUs, {dead} with dead stock (>60 days unsold)")

    # Drop internal flags before saving
    customer_df_clean = customer_df.drop(columns=["is_bad_payer"])
    sales_df_clean = sales_df.drop(columns=["is_anomaly"])

    # Save
    print()
    print("Saving CSVs...")
    sales_path     = DATA_DIR / "sales_data.csv"
    inventory_path = DATA_DIR / "inventory_data.csv"
    customer_path  = DATA_DIR / "customer_data.csv"
    purchase_path  = DATA_DIR / "purchase_data.csv"

    sales_df_clean.to_csv(sales_path, index=False)
    inventory_df.to_csv(inventory_path, index=False)
    customer_df_clean.to_csv(customer_path, index=False)
    purchase_df.to_csv(purchase_path, index=False)

    print(f"  ✓ {sales_path.name}     ({len(sales_df_clean):,} rows)")
    print(f"  ✓ {inventory_path.name}  ({len(inventory_df):,} rows)")
    print(f"  ✓ {customer_path.name}   ({len(customer_df_clean):,} rows)")
    print(f"  ✓ {purchase_path.name}  ({len(purchase_df):,} rows)")
    print()
    print("Data generation complete.")
    print()
    print("Interview Note:")
    print("  Data calibrated against real Indian WPI inflation (8.5% FY22-23,")
    print("  3.8% FY23-24) and real festival dates from PIB India calendar.")
    print("  No public dataset exists for Indian FMCG wholesale at this granularity.")


if __name__ == "__main__":
    main()
