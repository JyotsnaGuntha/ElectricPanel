"""
Solar bill aggregation and recommendation calculations.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable


def _round_up_to_step(value: float, step: int) -> int:
    if value <= 0:
        return 0
    return int(math.ceil(value / step) * step)


def _round_practical_kw(value: float) -> int:
    if value <= 0:
        return 0

    if value < 1000:
        return _round_up_to_step(value, 10)
    return _round_up_to_step(value, 5)


def _validate_row(row: Dict[str, Any]) -> Dict[str, float]:
    required_keys = ("month", "nh", "ep", "op", "mp", "total")
    missing = [key for key in required_keys if key not in row]
    if missing:
        raise ValueError(f"Missing required bill fields: {', '.join(missing)}")

    try:
        month = str(row["month"]).strip()
        nh = float(row["nh"])
        ep = float(row["ep"])
        op = float(row["op"])
        mp = float(row["mp"])
        total = float(row["total"])
    except Exception as error:
        raise ValueError(f"Invalid bill row values for {row.get('month', 'unknown month')}") from error

    if not month:
        raise ValueError("Bill row month label is empty.")

    if min(nh, ep, op, mp, total) < 0:
        raise ValueError(f"Negative UNIT CONSUMED value found for {month}.")

    calculated_total = nh + ep + op + mp
    if abs(total - calculated_total) > 2:
        raise ValueError(f"Invalid UNIT CONSUMED values found for {month}.")

    return {
        "month": month,
        "nh": nh,
        "ep": ep,
        "op": op,
        "mp": mp,
        "total": total,
    }


def calculate_bill_recommendation(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    validated_rows = [_validate_row(row) for row in rows or []]
    if not validated_rows:
        raise ValueError("No UNIT CONSUMED data was found in the uploaded PDFs.")

    total_solar_usable_units = 0.0
    total_units = 0.0

    for row in validated_rows:
        solar_usable = (row["nh"] * 0.60) + (row["mp"] * 0.70) + (row["ep"] * 0.15) + (row["op"] * 0.00)
        total_solar_usable_units += solar_usable
        total_units += row["total"]

    average_monthly_units = total_solar_usable_units / len(validated_rows)
    recommended_kw = _round_practical_kw(average_monthly_units / 130.0)

    return {
        "months": len(validated_rows),
        "total_solar_usable_units": round(total_solar_usable_units, 2),
        "average_monthly_units": round(average_monthly_units, 2),
        "recommended_kw": recommended_kw,
        "total_units": round(total_units, 2),
    }
