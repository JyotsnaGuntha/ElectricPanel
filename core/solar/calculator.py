"""
Solar bill aggregation and recommendation calculations.

Time Period Mapping:
- MP (Morning Period): 06:00 AM – 08:00 AM
- NH (Normal Hours): 08:00 AM – 06:00 PM
- EP (Evening Period): 06:00 PM – 10:00 PM
- OP (Off-Peak Period): 10:00 PM – 06:00 AM

Solar Capacity Formula:
Solar Capacity (kW) = (MP Units + NH Units) / 130
Where 130 units/month = 1 kW of solar capacity

Solar generation is considered only during MP and NH periods.
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
    """
    Calculate recommended solar capacity based on bill analysis.
    
    Considers only MP (Morning Period) and NH (Normal Hours) consumption,
    as these are the primary solar generation hours.
    
    Formula: Solar Capacity (kW) = (MP Units + NH Units) / 130
    
    Returns:
        Dict with keys:
        - months: Number of bills analyzed
        - mp_units: Total MP consumption across all bills
        - nh_units: Total NH consumption across all bills
        - solar_usable_units: Sum of MP and NH units
        - average_monthly_units: Average monthly solar-usable units
        - recommended_kw: Recommended solar capacity in kW
        - total_units: Total units from all periods (for reference)
    """
    validated_rows = [_validate_row(row) for row in rows or []]
    if not validated_rows:
        raise ValueError("No UNIT CONSUMED data was found in the uploaded PDFs.")

    total_solar_usable_units = 0.0
    total_mp_units = 0.0
    total_nh_units = 0.0
    total_units = 0.0

    # Calculate solar-usable units (MP + NH only, as these are solar generation hours)
    for row in validated_rows:
        mp_units = row["mp"]
        nh_units = row["nh"]
        solar_usable = mp_units + nh_units
        
        total_solar_usable_units += solar_usable
        total_mp_units += mp_units
        total_nh_units += nh_units
        total_units += row["total"]

    average_monthly_units = total_solar_usable_units / len(validated_rows)
    # Formula: Solar Capacity (kW) = Total Units / 130
    # Where 130 units/month = 1 kW of solar capacity
    recommended_kw = _round_practical_kw(average_monthly_units / 130.0)

    return {
        "months": len(validated_rows),
        "mp_units": round(total_mp_units, 2),
        "nh_units": round(total_nh_units, 2),
        "solar_usable_units": round(total_solar_usable_units, 2),
        "average_monthly_units": round(average_monthly_units, 2),
        "recommended_kw": recommended_kw,
        "total_units": round(total_units, 2),
    }
