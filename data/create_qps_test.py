import pandas as pd
from datetime import datetime

data = [
    # 1. Normal purchase (no scheme triggered)
    {"invoice_no": "INV-TEST-001", "date": "2024-06-10", "customer_name": "Laxmi Stores", "area": "Jaipur", 
     "product_name": "Ghari Detergent Powder 1kg", "company": "RSPL", "category": "Home Care", 
     "quantity": 2, "sale_price": 60.0, "discount_pct": 0, "invoice_amount": 120.0, "payment_status": "PAID"},

    # 2. Scheme Triggered (Buy 5) but WRONG TOWN (Jaipur instead of Tonk) - should not trigger claim
    {"invoice_no": "INV-TEST-002", "date": "2024-06-15", "customer_name": "Laxmi Stores", "area": "Jaipur", 
     "product_name": "Ghari Detergent Powder 1kg", "company": "RSPL", "category": "Home Care", 
     "quantity": 5, "sale_price": 60.0, "discount_pct": 0, "invoice_amount": 300.0, "payment_status": "PAID"},

    # 3. Scheme Triggered (Buy 5, gets 1 free) in Tonk on the correct day
    {"invoice_no": "INV-TEST-003", "date": "2024-06-15", "customer_name": "Ramesh Provision", "area": "Tonk", 
     "product_name": "Ghari Detergent Powder 1kg", "company": "RSPL", "category": "Home Care", 
     "quantity": 5, "sale_price": 60.0, "discount_pct": 0, "invoice_amount": 300.0, "payment_status": "PAID"},
    
    # 3b. The free item recorded in the same invoice (100% discount or 0 price)
    {"invoice_no": "INV-TEST-003", "date": "2024-06-15", "customer_name": "Ramesh Provision", "area": "Tonk", 
     "product_name": "Ghari Detergent Powder 10 Rs", "company": "RSPL", "category": "Home Care", 
     "quantity": 1, "sale_price": 0.0, "discount_pct": 100, "invoice_amount": 0.0, "payment_status": "PAID"},

    # 4. Mega order: Buys 20 bags, should be eligible for 4 free items
    {"invoice_no": "INV-TEST-004", "date": "2024-06-15", "customer_name": "Tonk Supermart", "area": "Tonk", 
     "product_name": "Ghari Detergent Powder 1kg", "company": "RSPL", "category": "Home Care", 
     "quantity": 20, "sale_price": 60.0, "discount_pct": 0, "invoice_amount": 1200.0, "payment_status": "PAID"},
    
    # 4b. The free items for the mega order (Wait, what if the distributor only gave 2 free instead of 4? System should flag discrepancy)
    {"invoice_no": "INV-TEST-004", "date": "2024-06-15", "customer_name": "Tonk Supermart", "area": "Tonk", 
     "product_name": "Ghari Detergent Powder 10 Rs", "company": "RSPL", "category": "Home Care", 
     "quantity": 2, "sale_price": 0.0, "discount_pct": 100, "invoice_amount": 0.0, "payment_status": "PAID"},
     
    # 5. Some noise data
    {"invoice_no": "INV-TEST-005", "date": "2024-06-15", "customer_name": "Tonk Supermart", "area": "Tonk", 
     "product_name": "Parle-G 50g", "company": "Parle", "category": "Snacks", 
     "quantity": 100, "sale_price": 4.5, "discount_pct": 0, "invoice_amount": 450.0, "payment_status": "PAID"},
]

df = pd.DataFrame(data)
df.to_csv("data/qps_test_sales.csv", index=False)
print("Generated data/qps_test_sales.csv successfully!")
