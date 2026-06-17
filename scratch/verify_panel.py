import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add root folder to sys.path so we can import from core/src
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils import load_mccb_dimensions_from_file, get_standard_rating, get_mccb_breaking_capacity
from core.solar.calculator import calculate_bill_recommendation

print("--- Testing Excel Database Loading ---")
excel_path = "Circuit_Breaker_Dimensions.xlsx"
db = load_mccb_dimensions_from_file(path=excel_path)
print(f"Successfully loaded {len(db)} entries from {excel_path}")
print("Loaded ratings:", sorted(db.keys()))

print("\n--- Testing get_standard_rating (Excel-Driven) ---")
# 1. With Excel DB:
test_values = [45, 120, 160, 240, 500, 2700, 6000]
print("With Loaded DB:")
for val in test_values:
    rating = get_standard_rating(val, db)
    print(f"  Input: {val:4}A -> Standard: {rating:4}A")

# 2. With Fallback DB (db=None):
print("\nWith Fallback DB:")
for val in test_values:
    rating = get_standard_rating(val, None)
    print(f"  Input: {val:4}A -> Standard: {rating:4}A")

print("\n--- Testing get_mccb_breaking_capacity ---")
for val in test_values:
    rating = get_standard_rating(val, db)
    cap = get_mccb_breaking_capacity(rating, db)
    print(f"  Rating: {rating:4}A -> Capacity: {cap}")

print("\n--- Testing Bill Recommendation Sizing & Calculations ---")
sample_rows = [
    {"month": "M1", "nh": 40000, "ep": 0, "op": 0, "mp": 10000, "total": 50000},
    {"month": "M2", "nh": 40000, "ep": 0, "op": 0, "mp": 10000, "total": 50000},
    {"month": "M3", "nh": 40000, "ep": 0, "op": 0, "mp": 10000, "total": 50000},
    {"month": "M4", "nh": 40000, "ep": 0, "op": 0, "mp": 10000, "total": 50000},
    {"month": "M5", "nh": 40000, "ep": 0, "op": 0, "mp": 10000, "total": 50000},
    {"month": "M6", "nh": 40000, "ep": 0, "op": 0, "mp": 10000, "total": 50000},
    {"month": "M7", "nh": 49990.16, "ep": 0, "op": 0, "mp": 10000, "total": 59990.16},
]

try:
    analysis = calculate_bill_recommendation(sample_rows)
    print("Bill Recommendation Calculation Succeeded!")
    print("Results:")
    print(f"  Total Solar Consumable Units: {analysis['solar_total_consumable']} Units")
    print(f"  Solar Usable Units: {analysis['solar_usable_units']} Units")
    print(f"  Number of Months Considered: {analysis['months']}")
    print(f"  Average Monthly Solar Capacity: {analysis['solar_avg_monthly_consumption']} Units")
    print(f"  Average Daily Consumption: {analysis['solar_avg_daily_consumption']} Units/Day")
    print(f"  Recommended Solar Capacity: {analysis['recommended_kw']} kW")
except Exception as e:
    print("Bill Recommendation failed:", e)
