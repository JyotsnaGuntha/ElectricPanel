import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.solar.parser import _extract_llamaparse_table

# 1. Test Case: Unit Rate before Unit Consumed
bill_text_1 = """
BILLING MONTH: Jan 2025
| TOD ZONE | UNIT RATE (Rs./Unit) | UNIT CONSUMED |
|---|---|---|
| NH | 6.40 | 101796 |
| MP | 8.32 | 28764 |
| EP | 8.32 | 43200 |
| OP | 4.80 | 91284 |
| TOTAL | | 265044 |
"""

# 2. Test Case: Unit Consumed before Unit Rate
bill_text_2 = """
MONTH/YEAR: 02/2025
| TOD SLOT | UNIT CONSUMED | UNIT TARIFF RATE (Rs./Unit) |
|---|---|---|
| NH | 115000 | 6.40 |
| MP | 32000 | 8.32 |
| EP | 48000 | 8.32 |
| OP | 95000 | 4.80 |
| TOTAL | 290000 | |
"""

# 3. Test Case: No headers (fallback logic) with tariff rates
bill_text_3 = """
MONTH/YEAR: 03/2025
| NH | 100000 | 110000 | 10000 | 6.40 | 64000.00 |
| MP | 20000 | 22500 | 2500 | 8.32 | 20800.00 |
| EP | 30000 | 34000 | 4000 | 8.32 | 33280.00 |
| OP | 50000 | 58000 | 8000 | 4.80 | 38400.00 |
"""

# 4. Test Case: Dynamic Zone-to-Time-Period Mapping (Zones A, B, C, D in different order/timings)
bill_text_4 = """
BILLING MONTH: Apr 2025
TOD Timings:
Zone C : 09:00 - 17:00
Zone A : 00:00 - 06:00
Zone D : 17:00 to 24:00
Zone B : 06.00 to 09.00

| TOD SLOT | UNIT RATE | UNIT CONSUMED |
|---|---|---|
| Zone A | 6.40 | 35803 |
| Zone B | 8.32 | 6843 |
| Zone C | 8.32 | 9510 |
| Zone D | 4.80 | 37826 |
| TOTAL | | 89984 |
"""

# 5. Test Case: Dynamic Zone-to-Time-Period Mapping (Numeric Zones 1, 2, 3, 4)
bill_text_5 = """
MONTH/YEAR: 05/2025
TOD Slots definitions:
Zone 1: 06:00 - 09:00
Zone 2: 17:00 - 24:00
Zone 3: 00:00 - 06:00
Zone 4: 09:00 - 17:00

| TOD Slot | Units |
|---|---|
| Slot 1 | 5000 |
| Slot 2 | 12000 |
| Slot 3 | 25000 |
| Slot 4 | 45000 |
"""

print("--- Running Parser Unit Tests ---")

print("\nTest Case 1 (Unit Rate before Unit Consumed):")
res1 = _extract_llamaparse_table(bill_text_1)
print(res1)
assert res1 and res1[0]["nh"] == 101796.0, f"Expected 101796.0, got {res1[0]['nh'] if res1 else None}"
assert res1[0]["total"] == 265044.0, f"Expected 265044.0, got {res1[0]['total']}"

print("\nTest Case 2 (Unit Consumed before Unit Rate):")
res2 = _extract_llamaparse_table(bill_text_2)
print(res2)
assert res2 and res2[0]["nh"] == 115000.0, f"Expected 115000.0, got {res2[0]['nh'] if res2 else None}"
assert res2[0]["total"] == 290000.0, f"Expected 290000.0, got {res2[0]['total']}"

print("\nTest Case 3 (No headers fallback - dynamic column scoring):")
res3 = _extract_llamaparse_table(bill_text_3)
print(res3)
# Consumption columns is Difference (10000) or total Rs (64000). Difference (10000) matches Prev (100000) and Curr (110000).
# Also 10000 * 6.40 = 64000.00, so Difference scores highest.
assert res3 and res3[0]["nh"] == 10000.0, f"Expected 10000.0, got {res3[0]['nh'] if res3 else None}"

print("\nTest Case 4 (Dynamic mapping with custom timing order):")
res4 = _extract_llamaparse_table(bill_text_4)
print(res4)
assert res4 and res4[0]["op"] == 35803.0, f"Expected OP to be 35803.0, got {res4[0]['op'] if res4 else None}"
assert res4[0]["mp"] == 6843.0, f"Expected MP to be 6843.0, got {res4[0]['mp']}"
assert res4[0]["nh"] == 9510.0, f"Expected NH to be 9510.0, got {res4[0]['nh']}"
assert res4[0]["ep"] == 37826.0, f"Expected EP to be 37826.0, got {res4[0]['ep']}"
assert res4[0]["total"] == 89984.0, f"Expected total to be 89984.0, got {res4[0]['total']}"

print("\nTest Case 5 (Dynamic mapping with numeric slots):")
res5 = _extract_llamaparse_table(bill_text_5)
print(res5)
assert res5 and res5[0]["mp"] == 5000.0, f"Expected MP to be 5000.0, got {res5[0]['mp'] if res5 else None}"
assert res5[0]["ep"] == 12000.0, f"Expected EP to be 12000.0, got {res5[0]['ep']}"
assert res5[0]["op"] == 25000.0, f"Expected OP to be 25000.0, got {res5[0]['op']}"
assert res5[0]["nh"] == 45000.0, f"Expected NH to be 45000.0, got {res5[0]['nh']}"
assert res5[0]["total"] == 87000.0, f"Expected total to be 87000.0, got {res5[0]['total']}"

print("\nALL PARSER TESTS PASSED SUCCESSFULLY!")
