import pandas as pd
import os

files = ["Circuit Breaker Dimensions.xlsx", "BusBar_dimensions.xlsx", "Pole_modification.xlsx"]

for f in files:
    if os.path.exists(f):
        print(f"\n--- {f} ---")
        try:
            df = pd.read_excel(f, header=None)
            print("First 20 rows:")
            print(df.head(20).to_string())
        except Exception as e:
            print(f"Error reading {f}: {e}")
    else:
        print(f"{f} not found")
