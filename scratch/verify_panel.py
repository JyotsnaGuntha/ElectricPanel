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
    {"month": "Jan 2026", "nh": 12000, "ep": 4000, "op": 6000, "mp": 2000, "total": 24000},
    {"month": "Feb 2026", "nh": 11000, "ep": 3500, "op": 5500, "mp": 1800, "total": 21800},
    {"month": "Mar 2026", "nh": 13000, "ep": 4500, "op": 6500, "mp": 2200, "total": 26200},
]

try:
    analysis = calculate_bill_recommendation(sample_rows)
    print("Bill Recommendation Calculation Succeeded!")
    print("Results:")
    print(f"  Months Analyzed: {analysis['months']}")
    print(f"  Suggested Solar Capacity: {analysis['recommended_kw']} kW")
    print(f"  Daily OP Consumption: {analysis['daily_op_units']:.2f} kWh/day")
    print(f"  Suggested BESS Capacity: {analysis['recommended_bess_kwh']:.2f} kWh")
except Exception as e:
    print("Bill Recommendation failed:", e)
