"""
Bootstrap writer: writes generate_demo_data.py to the project.
Run: python write_generator.py
"""
from pathlib import Path

TARGET = Path(r"E:\PROJECT 1\WHOLESALE BI SYSTEM - AGENT EDITION\data\generate_demo_data.py")

CONTENT = r'''"""
data/generate_demo_data.py
==========================
ERP-shaped synthetic data generator for the Wholesale BI System.

Run:
    .\venv\Scripts\python.exe data\generate_demo_data.py

SEED=42 | DATA_START=2024-09-01 | DATA_END=2026-08-31
N_CUSTOMERS=380 | N_PRODUCTS=135 | TARGET_SALES_LINES=25000 | N_TERRITORIES=25
"""
from __future__ import annotations

import json, random, shutil, sys, warnings, calendar
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
RAW_DIR    = DATA_DIR / "raw"
CONFIG_DIR = DATA_DIR / "config"
PROC_DIR   = DATA_DIR / "processed"
LEGACY_DIR = DATA_DIR / "legacy_demo"

for _d in [RAW_DIR, CONFIG_DIR, PROC_DIR, LEGACY_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# PARAMETERS
# ---------------------------------------------------------------------------
SEED               = 42
DATA_START         = date(2024, 9, 1)
DATA_END           = date(2026, 8, 31)
N_CUSTOMERS        = 380
TARGET_SALES_LINES = 25000

rng = np.random.default_rng(SEED)
random.seed(SEED)

# ---------------------------------------------------------------------------
# LEGACY MOVE
# ---------------------------------------------------------------------------
def move_legacy_files():
    legacy_map = {
        DATA_DIR / "demo_sales.csv"     : LEGACY_DIR / "demo_sales.csv",
        DATA_DIR / "demo_customers.csv" : LEGACY_DIR / "demo_customers.csv",
        DATA_DIR / "demo_inventory.csv" : LEGACY_DIR / "demo_inventory.csv",
        DATA_DIR / "data_generator.py"  : LEGACY_DIR / "data_generator.py",
    }
    for src, dst in legacy_map.items():
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {src.name} -> legacy_demo/")

# ---------------------------------------------------------------------------
# PRODUCT CATALOG  (name, category, brand, size, purchase_rate, selling_rate, gst%)
# ---------------------------------------------------------------------------
PRODUCT_CATALOG = [
    # Beverages (15)
    ("Brooke Bond Red Label Tea",   "Beverages",      "HUL",        "250g",   95,  130, 12),
    ("Tata Tea Gold",               "Beverages",      "Tata",       "500g",   190, 260, 12),
    ("Nescafe Classic",             "Beverages",      "Nestle",     "50g",    195, 280, 12),
    ("Bru Gold Coffee",             "Beverages",      "HUL",        "100g",   175, 250, 12),
    ("Amul Kool Milk",              "Beverages",      "Amul",       "200ml",  18,  25,  12),
    ("Frooti Mango Drink",          "Beverages",      "PepsiCo",    "200ml",  9,   13,  12),
    ("Maaza Mango",                 "Beverages",      "Coca-Cola",  "600ml",  32,  45,  12),
    ("Slice Mango Drink",           "Beverages",      "PepsiCo",    "600ml",  28,  40,  12),
    ("Thumbs Up Cola",              "Beverages",      "Coca-Cola",  "750ml",  30,  42,  12),
    ("Limca Lemon",                 "Beverages",      "Coca-Cola",  "750ml",  28,  40,  12),
    ("Sprite",                      "Beverages",      "Coca-Cola",  "750ml",  28,  40,  12),
    ("Coca Cola",                   "Beverages",      "Coca-Cola",  "750ml",  30,  42,  12),
    ("Pepsi",                       "Beverages",      "PepsiCo",    "750ml",  28,  40,  12),
    ("Real Fruit Juice",            "Beverages",      "Dabur",      "1L",     66,  95,  12),
    ("Tropicana Orange Juice",      "Beverages",      "PepsiCo",    "1L",     77,  110, 12),
    # Personal Care (20)
    ("Colgate MaxFresh Toothpaste", "Personal Care",  "Colgate",    "200g",   62,  95,  18),
    ("Colgate Dental Cream",        "Personal Care",  "Colgate",    "100g",   38,  58,  18),
    ("Pepsodent Toothpaste",        "Personal Care",  "HUL",        "200g",   55,  82,  18),
    ("Dettol Soap",                 "Personal Care",  "Reckitt",    "125g",   31,  48,  18),
    ("Lux Beauty Soap",             "Personal Care",  "HUL",        "100g",   22,  35,  18),
    ("Lifebuoy Soap",               "Personal Care",  "HUL",        "100g",   18,  28,  18),
    ("Dove Soap",                   "Personal Care",  "HUL",        "75g",    42,  65,  18),
    ("Head & Shoulders Shampoo",    "Personal Care",  "P&G",        "180ml",  118, 175, 18),
    ("Clinic Plus Shampoo",         "Personal Care",  "HUL",        "175ml",  51,  78,  18),
    ("Pantene Shampoo",             "Personal Care",  "P&G",        "180ml",  125, 185, 18),
    ("Parachute Coconut Oil",       "Personal Care",  "Marico",     "500ml",  75,  110, 18),
    ("Dabur Amla Hair Oil",         "Personal Care",  "Dabur",      "500ml",  68,  100, 18),
    ("Vivel Soap",                  "Personal Care",  "ITC",        "100g",   20,  30,  18),
    ("Gillette Mach3 Razor",        "Personal Care",  "Gillette",   "2pcs",   95,  145, 18),
    ("Gillette Fusion Razor",       "Personal Care",  "Gillette",   "2pcs",   195, 295, 18),
    ("Nivea Cream",                 "Personal Care",  "Nivea",      "200ml",  148, 220, 18),
    ("Fair & Lovely Cream",         "Personal Care",  "HUL",        "100g",   58,  88,  18),
    ("Ponds Talcum Powder",         "Personal Care",  "HUL",        "300g",   95,  145, 18),
    ("Vim Dishwash Bar",            "Personal Care",  "HUL",        "300g",   18,  28,  18),
    ("Pears Soap",                  "Personal Care",  "HUL",        "75g",    38,  58,  18),
    # Home Care (15)
    ("Surf Excel Detergent",        "Home Care",      "HUL",        "1kg",    91,  140, 12),
    ("Ariel Detergent",             "Home Care",      "P&G",        "1kg",    95,  145, 12),
    ("Rin Detergent",               "Home Care",      "HUL",        "500g",   38,  58,  12),
    ("Wheel Detergent",             "Home Care",      "HUL",        "1kg",    55,  82,  12),
    ("Harpic Toilet Cleaner",       "Home Care",      "Reckitt",    "500ml",  81,  125, 12),
    ("Lizol Floor Cleaner",         "Home Care",      "Reckitt",    "500ml",  72,  110, 12),
    ("Colin Glass Cleaner",         "Home Care",      "Reckitt",    "500ml",  65,  98,  12),
    ("Scotch Brite Scrub",          "Home Care",      "3M",         "1pc",    22,  35,  12),
    ("Vim Dishwash Liquid",         "Home Care",      "HUL",        "500ml",  85,  128, 12),
    ("Good Knight Mosquito Coil",   "Home Care",      "Godrej",     "10pcs",  38,  58,  12),
    ("All Out Mosquito Repellent",  "Home Care",      "HUL",        "45ml",   55,  82,  12),
    ("Odonil Air Freshener",        "Home Care",      "Dabur",      "50g",    42,  65,  12),
    ("Phenyl Floor Cleaner",        "Home Care",      "Reckitt",    "500ml",  28,  42,  12),
    ("Exo Dishwash Bar",            "Home Care",      "HUL",        "200g",   15,  22,  12),
    ("Domex Toilet Cleaner",        "Home Care",      "HUL",        "500ml",  68,  102, 12),
    # Snacks (20)
    ("Parle-G Biscuit",             "Snacks",         "Parle",      "800g",   38,  55,  12),
    ("Britannia Good Day",          "Snacks",         "Britannia",  "200g",   27,  38,  12),
    ("Oreo Biscuit",                "Snacks",         "Mondelez",   "120g",   38,  55,  12),
    ("Marie Gold Biscuit",          "Snacks",         "Britannia",  "250g",   24,  34,  12),
    ("Lays Classic Chips",          "Snacks",         "PepsiCo",    "26g",    9,   13,  12),
    ("Kurkure Masala",              "Snacks",         "PepsiCo",    "90g",    19,  27,  12),
    ("Uncle Chips",                 "Snacks",         "PepsiCo",    "60g",    15,  22,  12),
    ("Haldiram Bhujia",             "Snacks",         "Haldiram",   "200g",   65,  95,  12),
    ("Haldiram Aloo Bhujia",        "Snacks",         "Haldiram",   "150g",   48,  70,  12),
    ("Maggi Noodles",               "Snacks",         "Nestle",     "70g",    11,  16,  12),
    ("Yippee Noodles",              "Snacks",         "ITC",        "70g",    12,  17,  12),
    ("Britannia 50-50 Biscuit",     "Snacks",         "Britannia",  "100g",   18,  26,  12),
    ("Monaco Biscuit",              "Snacks",         "Parle",      "250g",   28,  40,  12),
    ("Sunfeast Dark Fantasy",       "Snacks",         "ITC",        "150g",   31,  45,  12),
    ("Bingo Mad Angles",            "Snacks",         "ITC",        "90g",    22,  32,  12),
    ("Hippo Rings",                 "Snacks",         "PepsiCo",    "40g",    10,  14,  12),
    ("Crax Corn Rings",             "Snacks",         "DFM",        "30g",    8,   12,  12),
    ("Perk Chocolate",              "Snacks",         "Cadbury",    "36g",    18,  25,  12),
    ("Dairy Milk Chocolate",        "Snacks",         "Cadbury",    "40g",    35,  50,  12),
    ("Sunfeast Yumfills",           "Snacks",         "ITC",        "50g",    12,  18,  12),
    # Packaged Foods (15)
    ("Aashirvaad Atta",             "Packaged Foods", "ITC",        "5kg",    203, 260, 5),
    ("Fortune Chakki Atta",         "Packaged Foods", "Marico",     "5kg",    195, 250, 5),
    ("Saffola Gold Oil",            "Packaged Foods", "Marico",     "1L",     145, 195, 5),
    ("Fortune Sunflower Oil",       "Packaged Foods", "Marico",     "1L",     125, 170, 5),
    ("Tata Salt",                   "Packaged Foods", "Tata",       "1kg",    18,  24,  5),
    ("Captain Cook Salt",           "Packaged Foods", "Tata",       "1kg",    16,  22,  5),
    ("Catch Black Pepper",          "Packaged Foods", "Catch",      "50g",    38,  52,  5),
    ("Everest Garam Masala",        "Packaged Foods", "Everest",    "100g",   55,  75,  5),
    ("MDH Kitchen King",            "Packaged Foods", "MDH",        "100g",   58,  80,  5),
    ("Rajdhani Besan",              "Packaged Foods", "Rajdhani",   "1kg",    62,  85,  5),
    ("Patanjali Ghee",              "Packaged Foods", "Patanjali",  "1L",     380, 495, 5),
    ("Amul Butter",                 "Packaged Foods", "Amul",       "500g",   211, 270, 5),
    ("Amul Cheese",                 "Packaged Foods", "Amul",       "200g",   129, 165, 5),
    ("Knorr Soup",                  "Packaged Foods", "HUL",        "44g",    34,  48,  5),
    ("Maggi Masala",                "Packaged Foods", "Nestle",     "100g",   22,  30,  5),
    # Dairy (10)
    ("Amul Milk 1L Pouch",          "Dairy",          "Amul",       "1L",     55,  68,  5),
    ("Amul Dahi",                   "Dairy",          "Amul",       "400g",   38,  50,  5),
    ("Mother Dairy Curd",           "Dairy",          "Mother Dairy","400g",  35,  48,  5),
    ("Amul Paneer",                 "Dairy",          "Amul",       "200g",   85,  110, 5),
    ("Amul Gold Milk",              "Dairy",          "Amul",       "1L",     62,  80,  5),
    ("Nestle Milkmaid",             "Dairy",          "Nestle",     "400g",   88,  118, 5),
    ("Amul Mozzarella Cheese",      "Dairy",          "Amul",       "200g",   145, 190, 5),
    ("Kwality Walls Cornetto",      "Dairy",          "HUL",        "65ml",   28,  40,  5),
    ("Amul Cone Ice Cream",         "Dairy",          "Amul",       "65ml",   22,  32,  5),
    ("Havmor Ice Cream",            "Dairy",          "Havmor",     "500ml",  95,  130, 5),
    # FMCG (15)
    ("Dettol Handwash",             "FMCG",           "Reckitt",    "200ml",  65,  95,  12),
    ("Savlon Antiseptic",           "FMCG",           "ICI",        "200ml",  55,  80,  12),
    ("Burnol Cream",                "FMCG",           "Reckitt",    "20g",    35,  52,  12),
    ("Band-Aid Strips",             "FMCG",           "J&J",        "10pcs",  22,  32,  12),
    ("ORS Oral Rehydration",        "FMCG",           "Dabur",      "21g",    12,  18,   5),
    ("Vicks VapoRub",               "FMCG",           "P&G",        "50ml",   96,  148, 12),
    ("Eno Fruit Salt",              "FMCG",           "Reckitt",    "100g",   61,  78,   5),
    ("Hajmola Tablets",             "FMCG",           "Dabur",      "120pcs", 35,  50,   5),
    ("Pudin Hara",                  "FMCG",           "Dabur",      "20ml",   28,  40,   5),
    ("Reynolds Pen",                "FMCG",           "Reynolds",   "10pcs",  45,  65,  12),
    ("Classmate Notebook",          "FMCG",           "ITC",        "172pg",  38,  55,  12),
    ("Natraj Pencil",               "FMCG",           "Natraj",     "12pcs",  28,  40,  12),
    ("Stayfree Pads",               "FMCG",           "J&J",        "8pcs",   65,  95,  12),
    ("Whisper Ultra",               "FMCG",           "P&G",        "8pcs",   68,  98,  12),
    ("Carefree Liner",              "FMCG",           "J&J",        "20pcs",  55,  80,  12),
    # Household (10)
    ("Bisleri Water 1L",            "Household",      "Bisleri",    "1L",     12,  20,  18),
    ("Bisleri Water 500ml",         "Household",      "Bisleri",    "500ml",  8,   15,  18),
    ("Aquaguard Filter Candle",     "Household",      "Aquaguard",  "1pc",    145, 210, 12),
    ("Comfort Fabric Softener",     "Household",      "HUL",        "800ml",  95,  145, 12),
    ("Dynamo Liquid Detergent",     "Household",      "HUL",        "1L",     115, 170, 12),
    ("Fevicol SH Adhesive",         "Household",      "Pidilite",   "200g",   62,  95,  12),
    ("Pidilite M-Seal",             "Household",      "Pidilite",   "50g",    48,  72,  18),
    ("Castrol Oil",                 "Household",      "Castrol",    "1L",     245, 360, 18),
    ("Battery Duracell AA",         "Household",      "Duracell",   "2pcs",   58,  85,  12),
    ("Battery Eveready AA",         "Household",      "Eveready",   "2pcs",   42,  62,  12),
    # Agricultural (5)
    ("Sarpan Hybrid Seeds",         "Agricultural",   "Sarpan",     "500g",   185, 260, 5),
    ("Parle Groundnut Oil",         "Agricultural",   "Parle",      "1L",     110, 150, 5),
    ("Ruchi Soya Oil",              "Agricultural",   "Ruchi Soya", "1L",     120, 165, 5),
    ("Naturefresh Oil",             "Agricultural",   "Cargill",    "1L",     115, 158, 5),
    ("Dhara Mustard Oil",           "Agricultural",   "Dhara",      "1L",     105, 145, 5),
]
assert len(PRODUCT_CATALOG) == 135, f"Expected 135 products, got {len(PRODUCT_CATALOG)}"

# ---------------------------------------------------------------------------
# TOWNS / TERRITORIES
# ---------------------------------------------------------------------------
TOWNS = ["Uniara", "Tonk", "Deoli", "Niwai", "Malpura",
         "Todaraisingh", "Khanpur", "Sawai Madhopur"]

TOWN_BEHAVIOR = {
    "Tonk":           (1.4, 1.10),
    "Uniara":         (1.1, 1.05),
    "Deoli":          (1.0, 0.90),
    "Niwai":          (0.85, 0.95),
    "Malpura":        (1.0, 0.95),
    "Todaraisingh":   (0.75, 0.88),
    "Khanpur":        (0.70, 0.85),
    "Sawai Madhopur": (1.2, 1.00),
}

TOWN_REPS = {
    "Uniara":         ["Ramesh Kumar",  "Vijay Sharma"],
    "Tonk":           ["Suresh Yadav",  "Manoj Patel"],
    "Deoli":          ["Rakesh Singh",  "Arun Gupta"],
    "Niwai":          ["Dinesh Verma",  "Bharat Meena"],
    "Malpura":        ["Pradeep Saini", "Kamal Jain"],
    "Todaraisingh":   ["Sanjay Rajput", "Ravi Choudhary"],
    "Khanpur":        ["Amit Sharma",   "Nikhil Gupta"],
    "Sawai Madhopur": ["Tushar Patel",  "Ramesh Kumar"],
}

BEAT_DEFS = [
    ("Uniara-1",    "Uniara",         "Monday",    "Ramesh Kumar"),
    ("Uniara-2",    "Uniara",         "Wednesday", "Vijay Sharma"),
    ("Uniara-3",    "Uniara",         "Friday",    "Ramesh Kumar"),
    ("Tonk-Main",   "Tonk",           "Monday",    "Suresh Yadav"),
    ("Tonk-Station","Tonk",           "Tuesday",   "Manoj Patel"),
    ("Tonk-Civil",  "Tonk",           "Thursday",  "Suresh Yadav"),
    ("Tonk-Market", "Tonk",           "Saturday",  "Manoj Patel"),
    ("Deoli-Main",  "Deoli",          "Tuesday",   "Rakesh Singh"),
    ("Deoli-East",  "Deoli",          "Friday",    "Arun Gupta"),
    ("Deoli-West",  "Deoli",          "Wednesday", "Rakesh Singh"),
    ("Niwai-1",     "Niwai",          "Monday",    "Dinesh Verma"),
    ("Niwai-2",     "Niwai",          "Thursday",  "Bharat Meena"),
    ("Niwai-3",     "Niwai",          "Saturday",  "Dinesh Verma"),
    ("Malpura-Main","Malpura",        "Tuesday",   "Pradeep Saini"),
    ("Malpura-North","Malpura",       "Friday",    "Kamal Jain"),
    ("Malpura-South","Malpura",       "Wednesday", "Pradeep Saini"),
    ("Toda-Main",   "Todaraisingh",   "Monday",    "Sanjay Rajput"),
    ("Toda-Mandi",  "Todaraisingh",   "Thursday",  "Ravi Choudhary"),
    ("Toda-Rural",  "Todaraisingh",   "Saturday",  "Sanjay Rajput"),
    ("Khanpur-1",   "Khanpur",        "Wednesday", "Amit Sharma"),
    ("Khanpur-2",   "Khanpur",        "Saturday",  "Nikhil Gupta"),
    ("Khanpur-3",   "Khanpur",        "Monday",    "Amit Sharma"),
    ("SM-City",     "Sawai Madhopur", "Tuesday",   "Tushar Patel"),
    ("SM-Station",  "Sawai Madhopur", "Thursday",  "Ramesh Kumar"),
    ("SM-Mandi",    "Sawai Madhopur", "Saturday",  "Tushar Patel"),
]
assert len(BEAT_DEFS) == 25

GODOWNS = ["Main Godown", "Tonk Branch", "Sawai Madhopur Branch"]

PINCODES = {
    "Uniara":         "304024",
    "Tonk":           "304001",
    "Deoli":          "304804",
    "Niwai":          "304021",
    "Malpura":        "304502",
    "Todaraisingh":   "304505",
    "Khanpur":        "304803",
    "Sawai Madhopur": "322001",
}

SUPPLIERS = [
    "Amul Regional Office Jaipur", "HUL Distributor Ajmer",
    "Nestle Area Office Jaipur",   "P&G Sub-Distributor Tonk",
    "ITC Tobacco & Foods Jaipur",  "Britannia Industries Jaipur",
    "Parle Products Jaipur",       "Marico Industries",
    "Reckitt Benckiser",           "Dabur India Jaipur",
    "Godrej Consumer Products",    "Tata Consumer Products",
    "Coca-Cola Area Office",       "PepsiCo Rajasthan",
    "Local Supplier",
]

BRAND_SUPPLIER = {
    "Amul":"Amul Regional Office Jaipur", "Mother Dairy":"Amul Regional Office Jaipur",
    "HUL":"HUL Distributor Ajmer", "Nestle":"Nestle Area Office Jaipur",
    "P&G":"P&G Sub-Distributor Tonk", "Gillette":"P&G Sub-Distributor Tonk",
    "ITC":"ITC Tobacco & Foods Jaipur", "Britannia":"Britannia Industries Jaipur",
    "Parle":"Parle Products Jaipur", "Marico":"Marico Industries",
    "Reckitt":"Reckitt Benckiser", "Dabur":"Dabur India Jaipur",
    "Godrej":"Godrej Consumer Products", "Tata":"Tata Consumer Products",
    "Coca-Cola":"Coca-Cola Area Office", "PepsiCo":"PepsiCo Rajasthan",
    "Colgate":"HUL Distributor Ajmer", "Nivea":"HUL Distributor Ajmer",
    "Cadbury":"HUL Distributor Ajmer", "Mondelez":"HUL Distributor Ajmer",
    "Kwality Walls":"HUL Distributor Ajmer",
}

SURNAMES = [
    "Sharma","Gupta","Patel","Verma","Agarwal","Singh","Jain","Meena",
    "Kumar","Yadav","Mali","Rajput","Saini","Bairwa","Nagar","Kumawat",
    "Choudhary","Bansal","Mittal","Garg","Khandelwal","Maheshwari",
    "Rathi","Sogani","Kasliwal","Natani","Bohra","Surana","Kothari","Lodha",
]
BIZ_TYPES = [
    "General Store","Kirana","Traders","Provisions","Supermart",
    "Enterprises","Brothers","Sons","Medical Store","Cold Store","Departmental Store",
]

# ---------------------------------------------------------------------------
# ARCHETYPES
# ---------------------------------------------------------------------------
ARCHETYPE_DIST = [
    ("high_frequency_high_value", 0.10),
    ("moderate_loyal",            0.30),
    ("growing",                   0.10),
    ("declining",                 0.10),
    ("low_frequency",             0.20),
    ("slow_payer",                0.10),
    ("chronic_overdue",           0.05),
    ("inactive",                  0.05),
]
ARCHETYPE_PARAMS = {
    "high_frequency_high_value": dict(freq_lo=8,  freq_hi=12, val_lo=15000, val_hi=50000, delay_lo=-5,  delay_hi=5,   full_prob=0.95, credit_days=30),
    "moderate_loyal":            dict(freq_lo=4,  freq_hi=6,  val_lo=5000,  val_hi=15000, delay_lo=0,   delay_hi=15,  full_prob=0.88, credit_days=30),
    "growing":                   dict(freq_lo=2,  freq_hi=6,  val_lo=3000,  val_hi=10000, delay_lo=0,   delay_hi=10,  full_prob=0.90, credit_days=30),
    "declining":                 dict(freq_lo=1,  freq_hi=5,  val_lo=5000,  val_hi=12000, delay_lo=5,   delay_hi=20,  full_prob=0.80, credit_days=30),
    "low_frequency":             dict(freq_lo=1,  freq_hi=2,  val_lo=2000,  val_hi=8000,  delay_lo=5,   delay_hi=25,  full_prob=0.82, credit_days=45),
    "slow_payer":                dict(freq_lo=3,  freq_hi=5,  val_lo=8000,  val_hi=20000, delay_lo=30,  delay_hi=60,  full_prob=0.75, credit_days=30),
    "chronic_overdue":           dict(freq_lo=2,  freq_hi=4,  val_lo=10000, val_hi=40000, delay_lo=60,  delay_hi=150, full_prob=0.45, credit_days=30),
    "inactive":                  dict(freq_lo=0,  freq_hi=0,  val_lo=5000,  val_hi=15000, delay_lo=30,  delay_hi=90,  full_prob=0.40, credit_days=30),
}

def assign_archetype(c_idx: int) -> str:
    local = np.random.default_rng(SEED + c_idx * 17)
    v = local.random()
    cum = 0.0
    for name, pct in ARCHETYPE_DIST:
        cum += pct
        if v < cum:
            return name
    return ARCHETYPE_DIST[-1][0]

# ---------------------------------------------------------------------------
# SEASONAL MULTIPLIERS
# ---------------------------------------------------------------------------
def seasonal_mult(category: str, month: int) -> float:
    if category == "Beverages":
        return 1.5 if month in (4,5,6) else 1.2 if month in (7,8,9) else 0.85
    if category == "Personal Care":
        return 1.35 if month == 10 else 1.10 if month == 11 else 1.0
    if category in ("Snacks","Packaged Foods"):
        return 1.4 if month in (10,11) else 1.25 if month in (3,4) else 0.9
    if category == "Dairy":
        if month in (10,11,12,1,2): return 1.1
        if month in (3,4):          return 1.2
        if month in (6,7,8):        return 0.85
        return 1.0
    if category == "Home Care":
        return 1.2 if month in (2,3) else 1.15 if month == 10 else 1.0
    return 1.0  # FMCG, Household, Agricultural

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _ageing(days_ov: int) -> str:
    if days_ov <= 0:  return "Current"
    if days_ov <= 30: return "0-30"
    if days_ov <= 60: return "31-60"
    if days_ov <= 90: return "61-90"
    return "90+"

def _recv_status(outstanding: float, bill: float, days_ov: int) -> str:
    if outstanding <= 0.01:           return "PAID"
    if outstanding < bill - 0.01:    return "PARTIALLY_PAID"
    if days_ov > 0:                   return "OVERDUE"
    return "DUE"

def _date_in_month(yr: int, mo: int, crng) -> date | None:
    _, dim = calendar.monthrange(yr, mo)
    s = max(date(yr, mo, 1), DATA_START)
    e = min(date(yr, mo, dim), DATA_END)
    if s > e: return None
    cands = [s + timedelta(d) for d in range((e - s).days + 1) if (s + timedelta(d)).weekday() < 6]
    if not cands: return None
    return cands[int(crng.integers(0, len(cands)))]

# ---------------------------------------------------------------------------
# GENERATE TERRITORIES
# ---------------------------------------------------------------------------
def gen_territories() -> pd.DataFrame:
    rows = []
    for i, (beat, town, rday, rep) in enumerate(BEAT_DEFS, 1):
        rows.append({"territory_id": f"T{i:03d}", "territory_name": beat,
                     "town": town, "beat": beat, "route_day": rday, "sales_rep": rep})
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# GENERATE ITEM MASTER
# ---------------------------------------------------------------------------
def gen_item_master() -> pd.DataFrame:
    rows = []
    for idx, (pname, cat, brand, size, prate, srate, gst) in enumerate(PRODUCT_CATALOG, 1):
        pr = np.random.default_rng(SEED + idx * 31)
        rows.append({
            "product_id":    f"PRD{idx:04d}",
            "product_name":  pname,
            "product_alias": f"{pname.split()[0]} {size}",
            "category":      cat,
            "sub_category":  cat,
            "brand":         brand,
            "unit":          "PCS",
            "gst_rate":      gst,
            "purchase_rate": float(prate),
            "selling_rate":  float(srate),
            "size_variant":  size,
            "reorder_level": int(pr.integers(20, 150)),
            "opening_stock": int(pr.integers(50, 500)),
        })
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# GENERATE CUSTOMER MASTER
# ---------------------------------------------------------------------------
def gen_customer_master() -> pd.DataFrame:
    town_wts = np.array([0.12, 0.20, 0.13, 0.12, 0.12, 0.10, 0.09, 0.12])
    town_wts /= town_wts.sum()
    town_idx = rng.choice(len(TOWNS), size=N_CUSTOMERS, p=town_wts)

    used_names: set = set()
    rows = []
    for i in range(N_CUSTOMERS):
        cr   = np.random.default_rng(SEED + i * 53)
        town = TOWNS[town_idx[i]]
        arch = assign_archetype(i)
        apar = ARCHETYPE_PARAMS[arch]
        for _ in range(200):
            nm = f"{cr.choice(SURNAMES)} {cr.choice(BIZ_TYPES)}"
            if nm not in used_names:
                used_names.add(nm); break
        ob = 0.0
        if arch in ("chronic_overdue","inactive"):
            ob = float(int(cr.integers(5000,50000)//100)*100)
        elif arch == "slow_payer":
            ob = float(int(cr.integers(2000,20000)//100)*100)
        rows.append({
            "customer_id":       f"CUST{i+1:04d}",
            "party_name":        nm,
            "address":           f"{int(cr.integers(1,999))} Main Road",
            "city":              town,
            "district":          "Tonk" if town != "Sawai Madhopur" else "Sawai Madhopur",
            "state":             "Rajasthan",
            "pincode":           PINCODES[town],
            "phone":             f"9{int(cr.integers(100000000,999999999))}",
            "customer_type":     "Retailer" if cr.random() < 0.75 else "Wholesaler",
            "ledger_group":      "Sundry Debtors",
            "opening_balance":   ob,
            "credit_limit":      int(cr.integers(30000,300000)//5000)*5000,
            "credit_days":       apar["credit_days"],
            "gstin_placeholder": f"08XXXXX{i+1:04d}X1ZA",
        })
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# GENERATE SALES + RECEIVABLES + PAYMENTS
# ---------------------------------------------------------------------------
def gen_sales_recv_pay(customer_df: pd.DataFrame, item_df: pd.DataFrame):
    products = item_df.to_dict("records")
    N = len(products)

    months = []
    cur = date(DATA_START.year, DATA_START.month, 1)
    while cur <= DATA_END:
        months.append((cur.year, cur.month))
        cur = date(cur.year + (1 if cur.month == 12 else 0),
                   1 if cur.month == 12 else cur.month + 1, 1)
    TM = len(months)

    sales_rows, recv_rows, pay_rows = [], [], []
    vc = 1   # voucher counter
    pc = 1   # payment counter
    ia_rng = np.random.default_rng(SEED + 9999)  # inactive cutoff

    for _, cust in customer_df.iterrows():
        cid   = cust["customer_id"]
        cname = cust["party_name"]
        city  = cust["city"]
        cidx  = int(cid.replace("CUST","")) - 1
        arch  = assign_archetype(cidx)
        apar  = ARCHETYPE_PARAMS[arch]
        cred  = int(cust["credit_days"])
        cr    = np.random.default_rng(SEED + cidx * 53 + 1000)
        tvol, tcoll = TOWN_BEHAVIOR.get(city, (1.0, 1.0))
        reps  = TOWN_REPS.get(city, ["Ramesh Kumar","Vijay Sharma"])

        if arch == "inactive":
            n_inv = int(cr.integers(1, 4))
            cutoff = int(ia_rng.integers(180, 550))
            last_dt = DATA_END - timedelta(days=cutoff)
            if last_dt < DATA_START: last_dt = DATA_START + timedelta(30)
            for _ in range(n_inv):
                span = max((last_dt - DATA_START).days, 1)
                inv_dt = DATA_START + timedelta(int(cr.integers(0, span)))
                inv_dt = min(inv_dt, last_dt)
                vno = f"SAL{vc:06d}"; vc += 1
                n_lines = int(cr.integers(1, 5))
                line_sum = 0.0
                for _ in range(n_lines):
                    p = products[int(cr.integers(0, N))]
                    qty = int(cr.integers(1, 20))
                    disc = float(cr.choice([0,0,2,3,5]))
                    rc = round(p["purchase_rate"]*(1+cr.uniform(0,0.02)),2)
                    rs = p["selling_rate"]
                    tax = round(qty*rs*(1-disc/100),2)
                    gst = round(tax*p["gst_rate"]/100,2)
                    line_sum += tax+gst
                    sales_rows.append({"voucher_no":vno,"voucher_date":inv_dt,
                        "customer_id":cid,"party_name":cname,"place":city,
                        "product_id":p["product_id"],"stock_item":p["product_name"],
                        "pack":p["size_variant"],"qty":qty,"unit":"PCS",
                        "rate_cost":rc,"rate_sale":rs,"discount_pct":disc,
                        "taxable_amount":tax,"gst_amount":gst,"invoice_amount":0.0,
                        "godown":str(cr.choice(GODOWNS)),
                        "salesman_name":str(cr.choice(reps)),"voucher_type":"Sales"})
                inv_val = round(line_sum, 2)
                for r2 in sales_rows:
                    if r2["voucher_no"] == vno: r2["invoice_amount"] = inv_val
                due = inv_dt + timedelta(cred)
                dov = max(0,(DATA_END-due).days)
                amtr = round(inv_val*float(cr.uniform(0,0.5)),2) if cr.random()>0.4 else 0.0
                amtr = min(amtr, inv_val)
                out = round(max(0.0, inv_val-amtr),2)
                recv_rows.append({"customer_id":cid,"party_name":cname,"voucher_no":vno,
                    "voucher_date":inv_dt,"due_date":due,"bill_amount":inv_val,
                    "amount_received":amtr,"outstanding_amount":out,
                    "days_overdue":dov,"ageing_bucket":_ageing(dov),
                    "status":_recv_status(out,inv_val,dov)})
                if amtr > 0:
                    pay_rows.append({"payment_voucher_no":f"PAY{pc:06d}",
                        "payment_date":inv_dt+timedelta(int(cr.integers(cred,cred+30))),
                        "customer_id":cid,"party_name":cname,"voucher_no":vno,
                        "payment_amount":amtr,
                        "payment_mode":str(cr.choice(["Cash","UPI","NEFT","Cheque"])),
                        "reference_no":f"REF{pc:08d}"}); pc+=1
            continue

        # Active customers
        for mi, (yr, mo) in enumerate(months):
            if arch == "growing":
                frac = mi/(TM-1) if TM>1 else 1
                base_f = apar["freq_lo"] + frac*(apar["freq_hi"]-apar["freq_lo"])
            elif arch == "declining":
                frac = mi/(TM-1) if TM>1 else 0
                base_f = apar["freq_hi"] - frac*(apar["freq_hi"]-apar["freq_lo"])
            else:
                base_f = (apar["freq_lo"]+apar["freq_hi"])/2.0
            freq = max(0, int(round(int(cr.poisson(max(base_f,0.1))) * tvol)))

            for _ in range(freq):
                inv_dt = _date_in_month(yr, mo, cr)
                if inv_dt is None: continue
                n_lines = int(cr.choice([1,2,3,4,5,6,7,8],
                              p=[0.05,0.10,0.20,0.25,0.20,0.10,0.07,0.03]))
                vno = f"SAL{vc:06d}"; vc += 1
                salesman = str(cr.choice(reps))
                chosen: set = set()
                line_sum = 0.0
                for _ in range(n_lines):
                    for _ in range(25):
                        pidx = int(cr.integers(0,N))
                        if products[pidx]["product_id"] not in chosen:
                            break
                    p = products[pidx]
                    chosen.add(p["product_id"])
                    base_qty = int(cr.integers(1,50))
                    qty = max(1, int(round(base_qty * seasonal_mult(p["category"], mo))))
                    disc = float(cr.choice([0,0,0,2,3,5,7,10],
                                 p=[0.30,0.20,0.10,0.15,0.10,0.08,0.05,0.02]))
                    rc = round(p["purchase_rate"]*(1+cr.uniform(0,0.02)),2)
                    rs = p["selling_rate"]
                    tax = round(qty*rs*(1-disc/100),2)
                    gst = round(tax*p["gst_rate"]/100,2)
                    line_sum += tax+gst
                    sales_rows.append({"voucher_no":vno,"voucher_date":inv_dt,
                        "customer_id":cid,"party_name":cname,"place":city,
                        "product_id":p["product_id"],"stock_item":p["product_name"],
                        "pack":p["size_variant"],"qty":qty,"unit":"PCS",
                        "rate_cost":rc,"rate_sale":rs,"discount_pct":disc,
                        "taxable_amount":tax,"gst_amount":gst,"invoice_amount":0.0,
                        "godown":str(cr.choice(GODOWNS)),
                        "salesman_name":salesman,"voucher_type":"Sales"})
                inv_val = round(line_sum, 2)
                for r2 in sales_rows:
                    if r2["voucher_no"]==vno and r2["invoice_amount"]==0.0:
                        r2["invoice_amount"] = inv_val

                due = inv_dt + timedelta(cred)
                dov = max(0,(DATA_END-due).days)
                delay = int(cr.integers(max(0,apar["delay_lo"]),apar["delay_hi"]+1))
                pay_dt = due + timedelta(delay)
                eff = min(1.0, apar["full_prob"]*tcoll)

                if cr.random() < eff:
                    amtr = inv_val
                elif pay_dt > DATA_END:
                    amtr = 0.0
                else:
                    amtr = round(inv_val*float(cr.uniform(0.2,0.9)),2)
                amtr = min(amtr, inv_val)
                out  = round(max(0.0, inv_val-amtr), 2)
                dov_r = dov if out>0 else 0

                recv_rows.append({"customer_id":cid,"party_name":cname,"voucher_no":vno,
                    "voucher_date":inv_dt,"due_date":due,"bill_amount":inv_val,
                    "amount_received":round(amtr,2),"outstanding_amount":out,
                    "days_overdue":dov_r,"ageing_bucket":_ageing(dov_r),
                    "status":_recv_status(out,inv_val,dov_r)})

                if amtr>0 and pay_dt<=DATA_END:
                    if arch in ("slow_payer","chronic_overdue") and cr.random()<0.3 and amtr>500:
                        sp = round(amtr*float(cr.uniform(0.3,0.7)),2)
                        for pa in [sp, round(amtr-sp,2)]:
                            if pa>0:
                                pay_rows.append({"payment_voucher_no":f"PAY{pc:06d}",
                                    "payment_date":pay_dt,"customer_id":cid,"party_name":cname,
                                    "voucher_no":vno,"payment_amount":pa,
                                    "payment_mode":str(cr.choice(["Cash","UPI","NEFT","Cheque"])),
                                    "reference_no":f"REF{pc:08d}"}); pc+=1
                    else:
                        pay_rows.append({"payment_voucher_no":f"PAY{pc:06d}",
                            "payment_date":pay_dt,"customer_id":cid,"party_name":cname,
                            "voucher_no":vno,"payment_amount":round(amtr,2),
                            "payment_mode":str(cr.choice(["Cash","UPI","NEFT","Cheque"])),
                            "reference_no":f"REF{pc:08d}"}); pc+=1

    s = pd.DataFrame(sales_rows)
    r = pd.DataFrame(recv_rows)
    p = pd.DataFrame(pay_rows)
    print(f"  Raw sales lines generated: {len(s)}")

    # Scale toward target
    if len(s) > TARGET_SALES_LINES * 1.05:
        keep = rng.random(len(s)) < (TARGET_SALES_LINES / len(s))
        kept_v = set(s[keep]["voucher_no"].unique())
        # keep entire invoices that are selected
        s = s[s["voucher_no"].isin(kept_v)].reset_index(drop=True)
        r = r[r["voucher_no"].isin(kept_v)].reset_index(drop=True)
        p = p[p["voucher_no"].isin(kept_v)].reset_index(drop=True)

    return s, r, p

# ---------------------------------------------------------------------------
# PURCHASE REGISTER
# ---------------------------------------------------------------------------
def gen_purchases(sales_df: pd.DataFrame, item_df: pd.DataFrame) -> pd.DataFrame:
    prod_map = {r["product_id"]: r for _, r in item_df.iterrows()}
    sales_df = sales_df.copy()
    sales_df["_ym"] = sales_df["voucher_date"].apply(lambda d: (d.year, d.month))
    agg = (sales_df.groupby(["product_id","_ym"])["qty"].sum()
           .reset_index().rename(columns={"qty":"sold"}))
    rows = []
    pc = 1
    for _, row in agg.iterrows():
        pid = row["product_id"]; yr,mo = row["_ym"]; sold = row["sold"]
        prod = prod_map.get(pid); 
        if not prod: continue
        pr = np.random.default_rng(SEED + pc * 7)
        qty = int(sold * pr.uniform(1.1,1.3)) + 1
        pdate = date(yr,mo,1) - timedelta(int(pr.integers(0,15)))
        pdate = max(pdate, DATA_START); pdate = min(pdate, DATA_END)
        rate = round(prod["purchase_rate"]*(1+pr.uniform(-0.005,0.01)),2)
        disc = float(pr.choice([0,0,1,2,3]))
        tax  = round(qty*rate*(1-disc/100),2)
        gst  = round(tax*prod["gst_rate"]/100,2)
        sup  = BRAND_SUPPLIER.get(prod["brand"],"Local Supplier")
        rows.append({"voucher_no":f"PUR{pc:06d}","voucher_date":pdate,
            "supplier_id":f"SUP{(pc%15)+1:03d}","supplier_name":sup,
            "product_id":pid,"stock_item":prod["product_name"],"pack":prod.get("size_variant",""),
            "qty":qty,"unit":"PCS","rate":rate,"discount_pct":disc,
            "taxable_amount":tax,"gst_amount":gst,"invoice_amount":round(tax+gst,2),
            "godown":"Main Godown" if pr.random()<0.6 else "Tonk Branch"}); pc+=1
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# STOCK SUMMARY
# ---------------------------------------------------------------------------
def gen_stock(item_df, sales_df, purch_df) -> pd.DataFrame:
    rows = []
    for _, prod in item_df.iterrows():
        pid = prod["product_id"]
        sq = int(sales_df[sales_df["product_id"]==pid]["qty"].sum()) if not sales_df.empty else 0
        pq = int(purch_df[purch_df["product_id"]==pid]["qty"].sum()) if not purch_df.empty else 0
        for gi, gd in enumerate(GODOWNS):
            gr = np.random.default_rng(SEED + hash(pid+gd)%100000)
            gf = [0.6,0.25,0.15][gi]
            gs = int(sq*gf); gp = int(pq*gf)
            op = int(gr.integers(5, int(prod["opening_stock"]*gf)+20))
            cl = max(0, op+gp-gs)
            cr2 = round(prod["purchase_rate"]*(1+gr.uniform(-0.01,0.02)),2)
            rows.append({"product_id":pid,"product_name":prod["product_name"],"godown":gd,
                "opening_qty":op,"inward_qty":gp,"outward_qty":gs,"closing_qty":cl,
                "closing_rate":cr2,"closing_value":round(cl*cr2,2)})
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# DEMO SCENARIOS
# ---------------------------------------------------------------------------
SCENARIO_TYPES = ["large_amount_high_prob","large_amount_low_prob","small_low_risk",
    "severely_overdue","repeat_late_payer","partial_payer","recent_invoice",
    "payment_link_candidate","escalation_candidate","do_not_contact"]

def gen_scenarios(customer_df, recv_df) -> pd.DataFrame:
    if recv_df.empty:
        return pd.DataFrame(columns=["scenario_id","customer_id","scenario_type","notes"])
    agg = recv_df.groupby("customer_id").agg(
        total_out=("outstanding_amount","sum"), max_dov=("days_overdue","max"),
        n_partial=("status",lambda x:(x=="PARTIALLY_PAID").sum()),
        n_overdue=("status",lambda x:(x=="OVERDUE").sum()),
        last_inv=("voucher_date","max")).reset_index()
    rows = []; sc=1
    for _, rw in agg.iterrows():
        out=rw["total_out"]; dov=rw["max_dov"]; np_=rw["n_partial"]; nov=rw["n_overdue"]
        last=rw["last_inv"]
        if out < 100: sc_type="small_low_risk"
        elif dov > 120: sc_type="severely_overdue"
        elif out > 50000 and dov < 60: sc_type="large_amount_high_prob"
        elif out > 30000 and dov > 60: sc_type="large_amount_low_prob"
        elif np_ >= 3: sc_type="partial_payer"
        elif nov >= 2: sc_type="repeat_late_payer"
        else:
            last_d = last.date() if hasattr(last,"date") else last
            if isinstance(last_d, date):
                ds = (DATA_END-last_d).days
                if ds<=7: sc_type="do_not_contact"
                elif ds<=30: sc_type="recent_invoice"
                elif out>5000 and dov<60: sc_type="payment_link_candidate"
                elif out>20000: sc_type="escalation_candidate"
                else: sc_type="payment_link_candidate"
            else: sc_type="payment_link_candidate"
        rows.append({"scenario_id":f"SC{sc:04d}","customer_id":rw["customer_id"],
            "scenario_type":sc_type,
            "notes":f"Outstanding={out:.0f},MaxDaysOv={dov},Partial={np_},Overdue={nov}"}); sc+=1
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# PROCESSED CANONICAL FILES
# ---------------------------------------------------------------------------
SALES_COLS = ["invoice_no","date","customer_name","customer_area","product_name",
    "category","company","size_variant","quantity","purchase_price",
    "sale_price","discount_pct","salesperson","payment_status","payment_due_date"]
CUST_COLS  = ["customer_id","customer_name","area","pincode","customer_type",
    "credit_limit","outstanding_amount","last_order_date","last_payment_date","total_business_ytd"]
INV_COLS   = ["product_name","category","company","size_variant","current_stock",
    "last_purchase_date","last_sale_date","purchase_price","mrp","reorder_level"]

STATUS_MAP = {"PAID":"PAID","PARTIALLY_PAID":"PARTIAL","OVERDUE":"OVERDUE","DUE":"UNPAID"}

def build_proc_sales(sales_df, customer_df, recv_df, item_df) -> pd.DataFrame:
    if sales_df.empty: return pd.DataFrame(columns=SALES_COLS)
    cl = customer_df.set_index("customer_id")[["party_name","city"]].to_dict("index")
    il = item_df.set_index("product_id")[["product_name","category","brand","size_variant","purchase_rate","selling_rate"]].to_dict("index")
    rl = recv_df.set_index("voucher_no")[["status","due_date"]].to_dict("index")
    rows=[]
    for _, r in sales_df.iterrows():
        ci=cl.get(r["customer_id"],{}); ii=il.get(r["product_id"],{}); ri=rl.get(r["voucher_no"],{})
        ps=STATUS_MAP.get(ri.get("status","DUE"),"UNPAID")
        dd=ri.get("due_date",""); dd="" if ps=="PAID" else (str(dd)[:10] if dd else "")
        rows.append({"invoice_no":r["voucher_no"],"date":r["voucher_date"],
            "customer_name":ci.get("party_name",r["party_name"]),"customer_area":ci.get("city",r["place"]),
            "product_name":ii.get("product_name",r["stock_item"]),"category":ii.get("category",""),
            "company":ii.get("brand",""),"size_variant":ii.get("size_variant",r.get("pack","")),
            "quantity":r["qty"],"purchase_price":ii.get("purchase_rate",r["rate_cost"]),
            "sale_price":ii.get("selling_rate",r["rate_sale"]),"discount_pct":r["discount_pct"],
            "salesperson":r["salesman_name"],"payment_status":ps,"payment_due_date":dd})
    return pd.DataFrame(rows)[SALES_COLS]

def build_proc_customers(customer_df, recv_df, sales_df) -> pd.DataFrame:
    ra = recv_df.groupby("customer_id").agg(outstanding_amount=("outstanding_amount","sum"),
        lp=("voucher_date","max")).reset_index() if not recv_df.empty else pd.DataFrame(
        columns=["customer_id","outstanding_amount","lp"])
    sa = pd.DataFrame()
    if not sales_df.empty:
        lo = sales_df.groupby("customer_id")["voucher_date"].max().reset_index().rename(columns={"voucher_date":"last_order_date"})
        it = sales_df.drop_duplicates("voucher_no").groupby("customer_id")["invoice_amount"].sum().reset_index().rename(columns={"invoice_amount":"total_business_ytd"})
        sa = lo.merge(it,on="customer_id",how="left")
    rows=[]
    for _, c in customer_df.iterrows():
        cid=c["customer_id"]
        rr=ra[ra["customer_id"]==cid]; ss=sa[sa["customer_id"]==cid] if not sa.empty else pd.DataFrame()
        out=float(rr["outstanding_amount"].iloc[0]) if not rr.empty else 0.0
        lo_=str(ss["last_order_date"].iloc[0])[:10] if not ss.empty else ""
        lp_=str(rr["lp"].iloc[0])[:10] if not rr.empty else ""
        ytd=float(ss["total_business_ytd"].iloc[0]) if not ss.empty else 0.0
        rows.append({"customer_id":cid,"customer_name":c["party_name"],"area":c["city"],
            "pincode":c["pincode"],"customer_type":c["customer_type"],"credit_limit":c["credit_limit"],
            "outstanding_amount":round(out,2),"last_order_date":lo_,"last_payment_date":lp_,
            "total_business_ytd":round(ytd,2)})
    return pd.DataFrame(rows)[CUST_COLS]

def build_proc_inv(item_df, purch_df, sales_df, stock_df) -> pd.DataFrame:
    pl = purch_df.groupby("product_id")["voucher_date"].max().reset_index().rename(
        columns={"voucher_date":"lpd"}) if not purch_df.empty else pd.DataFrame(columns=["product_id","lpd"])
    sl = sales_df.groupby("product_id")["voucher_date"].max().reset_index().rename(
        columns={"voucher_date":"lsd"}) if not sales_df.empty else pd.DataFrame(columns=["product_id","lsd"])
    st = stock_df.groupby("product_id")["closing_qty"].sum().reset_index().rename(
        columns={"closing_qty":"cs"}) if not stock_df.empty else pd.DataFrame(columns=["product_id","cs"])
    rows=[]
    for _, p in item_df.iterrows():
        pid=p["product_id"]
        lpd=str(pl[pl["product_id"]==pid]["lpd"].iloc[0])[:10] if pid in pl["product_id"].values else ""
        lsd=str(sl[sl["product_id"]==pid]["lsd"].iloc[0])[:10] if pid in sl["product_id"].values else ""
        cs=int(st[st["product_id"]==pid]["cs"].iloc[0]) if pid in st["product_id"].values else 0
        rows.append({"product_name":p["product_name"],"category":p["category"],"company":p["brand"],
            "size_variant":p.get("size_variant",""),"current_stock":cs,
            "last_purchase_date":lpd,"last_sale_date":lsd,
            "purchase_price":float(p["purchase_rate"]),"mrp":float(p["selling_rate"]),
            "reorder_level":int(p["reorder_level"])})
    return pd.DataFrame(rows)[INV_COLS]

# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------
def validate(cd,id_,sd,pd_,rd,py,ps,pc2,pi) -> dict:
    R={}
    vcids=set(cd["customer_id"]); vpids=set(id_["product_id"])
    R["1_sales_customer_refs"]    = sd["customer_id"].isin(vcids).all() if not sd.empty else True
    R["2_sales_product_refs"]     = sd["product_id"].isin(vpids).all()  if not sd.empty else True
    R["3_purchase_product_refs"]  = pd_["product_id"].isin(vpids).all() if not pd_.empty else True
    R["4_recv_customer_refs"]     = rd["customer_id"].isin(vcids).all() if not rd.empty else True
    vvno=set(rd["voucher_no"]) if not rd.empty else set()
    R["5_payment_voucher_refs"]   = py["voucher_no"].isin(vvno).all() if not py.empty else True
    R["6_outstanding_nonnegative"]= (rd["outstanding_amount"]>=-0.01).all() if not rd.empty else True
    if not rd.empty:
        diff=(rd["bill_amount"]-rd["amount_received"]-rd["outstanding_amount"]).abs()
        R["7_outstanding_reconciles"]=( diff<=0.51).all()
    else: R["7_outstanding_reconciles"]=True
    R["8_due_date_valid"]         = (rd["due_date"]>=rd["voucher_date"]).all() if not rd.empty else True
    R["9_proc_sales_cols"]        = list(ps.columns)==SALES_COLS
    R["10_proc_cust_cols"]        = list(pc2.columns)==CUST_COLS
    R["11_proc_inv_cols"]         = list(pi.columns)==INV_COLS
    R["12_payment_status_values"] = ps["payment_status"].isin({"PAID","UNPAID","OVERDUE","PARTIAL"}).all() if not ps.empty else True
    R["13_all_towns_covered"]     = len(cd["city"].unique())>=8
    R["14_payment_behaviors"]     = len(rd["status"].unique())>=2 if not rd.empty else False
    if not sd.empty:
        bids=set(id_[id_["category"]=="Beverages"]["product_id"])
        bev=sd[sd["product_id"].isin(bids)].copy()
        if not bev.empty:
            bev["mo"]=bev["voucher_date"].apply(lambda d:d.month)
            mm=bev.groupby("mo")["qty"].sum()
            R["15_seasonal_variation"]=(mm.std()/mm.mean()>0.1) if mm.mean()>0 else False
        else: R["15_seasonal_variation"]=False
    else: R["15_seasonal_variation"]=False
    return R

# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------
def report(cd,id_,sd,pd_,rd,py,stk,scd,val):
    SEP="="*65
    print(f"\n{SEP}\n   RECONCILIATION REPORT\n{SEP}")
    n_inv=rd["voucher_no"].nunique() if not rd.empty else 0
    print(f"  Customers  : {len(cd)}")
    print(f"  Products   : {len(id_)}")
    print(f"  Sales Lines: {len(sd)}")
    print(f"  Invoices   : {n_inv}")
    if not rd.empty:
        ts=rd["bill_amount"].sum(); tr=rd["amount_received"].sum(); to=rd["outstanding_amount"].sum()
        print(f"\n  Total Sales Value        : Rs.{ts:>14,.2f}")
    if not pd_.empty:
        tp=pd_["invoice_amount"].sum(); print(f"  Total Purchase Value     : Rs.{tp:>14,.2f}")
    if not rd.empty:
        print(f"  Total Payments Collected : Rs.{tr:>14,.2f}")
        print(f"  Total Outstanding        : Rs.{to:>14,.2f}")
    if not stk.empty:
        iv=stk["closing_value"].sum(); print(f"  Inventory Total Value    : Rs.{iv:>14,.2f}")
    if not rd.empty:
        orw=rd[rd["outstanding_amount"]>0]
        ab=orw.groupby("ageing_bucket")["outstanding_amount"].sum()
        print(f"\n  --- Outstanding by Ageing ---")
        for b in ["Current","0-30","31-60","61-90","90+"]:
            print(f"    {b:<10}: Rs.{ab.get(b,0.0):>12,.2f}")
        cwo=rd[rd["outstanding_amount"]>0]["customer_id"].nunique()
        print(f"\n  Customers with outstanding > 0 : {cwo}")
    if not scd.empty:
        print(f"\n  --- Demo Scenario Distribution ---")
        sc_c=scd["scenario_type"].value_counts()
        for t in SCENARIO_TYPES:
            print(f"    {t:<35}: {sc_c.get(t,0)}")
    print(f"\n  --- Territory Distribution ---")
    tc=cd["city"].value_counts().to_dict()
    for t in TOWNS: print(f"    {t:<22}: {tc.get(t,0)}")
    if not sd.empty and not rd.empty:
        isum=sd.groupby("voucher_no").apply(lambda x:(x["taxable_amount"]+x["gst_amount"]).sum())
        ri2=rd[["voucher_no","bill_amount"]].drop_duplicates()
        chk=isum.rename("ls").reset_index().merge(ri2,on="voucher_no",how="inner")
        mm=(abs(chk["ls"]-chk["bill_amount"])>1.0).sum()
        print(f"\n  Invoice Total == Sum of Lines  : mismatches = {mm}")
    if not py.empty and not rd.empty:
        ps2=py.groupby("voucher_no")["payment_amount"].sum().reset_index().rename(columns={"payment_amount":"tp"})
        rc2=rd[["voucher_no","amount_received"]].drop_duplicates()
        pc3=ps2.merge(rc2,on="voucher_no",how="inner")
        pm=(abs(pc3["tp"]-pc3["amount_received"])>0.51).sum()
        print(f"  Payment Sum == amount_received : mismatches = {pm}")
    if not rd.empty:
        od=(rd["bill_amount"]-rd["amount_received"]-rd["outstanding_amount"]).abs()
        om=(od>0.51).sum(); print(f"  Outstanding == Bill - Received : mismatches = {om}")
    LABELS={"1_sales_customer_refs":"1.  Sales -> valid customer_id",
        "2_sales_product_refs":"2.  Sales -> valid product_id",
        "3_purchase_product_refs":"3.  Purchases -> valid product_id",
        "4_recv_customer_refs":"4.  Receivables -> valid customer_id",
        "5_payment_voucher_refs":"5.  Payments -> valid voucher_no",
        "6_outstanding_nonnegative":"6.  Outstanding >= 0",
        "7_outstanding_reconciles":"7.  Outstanding ~ Bill - Received",
        "8_due_date_valid":"8.  Due date >= voucher date",
        "9_proc_sales_cols":"9.  demo_sales.csv canonical cols",
        "10_proc_cust_cols":"10. demo_customers.csv canonical cols",
        "11_proc_inv_cols":"11. demo_inventory.csv canonical cols",
        "12_payment_status_values":"12. Payment status values valid",
        "13_all_towns_covered":"13. All 8 towns covered",
        "14_payment_behaviors":"14. Multiple payment behaviors",
        "15_seasonal_variation":"15. Beverage seasonal variation CV>0.1"}
    print(f"\n  --- Validation Results ---")
    ok=True
    for k,lbl in LABELS.items():
        st=val.get(k,False); ic="PASS" if st else "FAIL"
        if not st: ok=False
        print(f"    [{ic}] {lbl}")
    print(f"\n  Overall: {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
    print(SEP)
    return ok

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("\n"+"="*65)
    print("  Wholesale BI - ERP Synthetic Data Generator")
    print("  SEED=42 | 2024-09-01 to 2026-08-31 | 380 customers | 135 products")
    print("="*65+"\n")

    move_legacy_files()

    print("[1/9] Territories...")
    terr=gen_territories(); terr.to_csv(CONFIG_DIR/"territories.csv",index=False)
    print(f"  {len(terr)} beats written")

    print("[2/9] Item master...")
    item_df=gen_item_master(); item_df.to_csv(RAW_DIR/"item_master.csv",index=False)
    print(f"  {len(item_df)} products")

    print("[3/9] Customer master...")
    cust_df=gen_customer_master(); cust_df.to_csv(RAW_DIR/"customer_master.csv",index=False)
    print(f"  {len(cust_df)} customers | towns: {cust_df['city'].nunique()}")

    print("[4/9] Sales + Receivables + Payments...")
    sales_df,recv_df,pay_df=gen_sales_recv_pay(cust_df,item_df)
    sales_df.to_csv(RAW_DIR/"sales_register.csv",index=False)
    recv_df.to_csv(RAW_DIR/"receivables.csv",index=False)
    pay_df.to_csv(RAW_DIR/"payment_register.csv",index=False)
    print(f"  Sales lines: {len(sales_df)} | Invoices: {recv_df['voucher_no'].nunique()} | Payments: {len(pay_df)}")

    print("[5/9] Purchase register...")
    purch_df=gen_purchases(sales_df,item_df); purch_df.to_csv(RAW_DIR/"purchase_register.csv",index=False)
    print(f"  {len(purch_df)} purchase rows")

    print("[6/9] Stock summary...")
    stock_df=gen_stock(item_df,sales_df,purch_df); stock_df.to_csv(RAW_DIR/"stock_summary.csv",index=False)
    print(f"  {len(stock_df)} stock rows ({len(stock_df)//3} products x 3 godowns)")

    print("[7/9] Demo scenarios...")
    scen_df=gen_scenarios(cust_df,recv_df); scen_df.to_csv(CONFIG_DIR/"demo_scenarios.csv",index=False)
    print(f"  {len(scen_df)} scenario entries")

    print("[8/9] Business profile + Processed files...")
    bp={"business_name":"Raj Distributors","owner_name":"Rajesh Kumar Sharma",
        "business_type":"FMCG Wholesale Distributor","address":"Near Railway Station, Main Market",
        "city":"Tonk","district":"Tonk","state":"Rajasthan","gstin":"08AAAPL1234N1ZA",
        "financial_year":"2024-25 / 2025-26",
        "data_note":"Revenue and operational metrics are computed from transaction data, not stored here."}
    with open(CONFIG_DIR/"business_profile.json","w",encoding="utf-8") as f:
        json.dump(bp,f,indent=2,ensure_ascii=False)

    ps=build_proc_sales(sales_df,cust_df,recv_df,item_df)
    pc2=build_proc_customers(cust_df,recv_df,sales_df)
    pi=build_proc_inv(item_df,purch_df,sales_df,stock_df)
    ps.to_csv(PROC_DIR/"demo_sales.csv",index=False)
    pc2.to_csv(PROC_DIR/"demo_customers.csv",index=False)
    pi.to_csv(PROC_DIR/"demo_inventory.csv",index=False)
    print(f"  demo_sales: {len(ps)} | demo_customers: {len(pc2)} | demo_inventory: {len(pi)}")

    print("[9/9] Validation + Report...")
    val=validate(cust_df,item_df,sales_df,purch_df,recv_df,pay_df,ps,pc2,pi)
    ok=report(cust_df,item_df,sales_df,purch_df,recv_df,pay_df,stock_df,scen_df,val)

    print("\nSample â€” sales_register (first 3):")
    if not sales_df.empty: print(sales_df.head(3).to_string(index=False))
    print("\nSample â€” customer_master (first 3):")
    print(cust_df.head(3).to_string(index=False))
    print("\nSample â€” receivables (first 3):")
    if not recv_df.empty: print(recv_df.head(3).to_string(index=False))

    print(f"\nOutput directory: {DATA_DIR}")
    return 0 if ok else 1

if __name__=="__main__":
    sys.exit(main())
'''

TARGET.write_text(CONTENT, encoding="utf-8")
print(f"Written {TARGET} ({TARGET.stat().st_size:,} bytes)")

