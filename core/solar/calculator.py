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

BESS Calculation:
1. Daily OP Units = Monthly OP Units / 30
2. Average Hourly OP Units = Daily OP Units / 8
3. Recommended BESS (kWh) = Average Hourly OP Units

"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable

OFF_PEAK_HOURS = 8


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
    
    BESS:
        Daily OP Units = Monthly OP Units / 30
        Average Hourly OP Units = Daily OP Units / 8
        Recommended BESS (kWh) = Average Hourly OP Units
        
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

    months = len(validated_rows)
    total_solar_usable_units = 0.0
    total_mp_units = 0.0
    total_nh_units = 0.0
    total_op_units = 0.0
    total_units = 0.0

    # Calculate solar-usable units (MP + NH only, as these are solar generation hours)
    for row in validated_rows:
        total_mp_units += row["mp"]
        total_nh_units += row["nh"]
        total_op_units += row["op"]
        total_units += row["total"]
        total_solar_usable_units += (row["mp"] + row["nh"])

    average_monthly_units = total_solar_usable_units / months
    recommended_kw = _round_practical_kw(average_monthly_units / 126.0)
    # 126 = 30*4.2
    bill_data = [{"mp": row["mp"], "ep": row["ep"], "total": row["total"], "month": row["month"]} for row in validated_rows]

    # BESS calculations
    average_monthly_op_units = total_op_units / months
    daily_op_units = average_monthly_op_units / 30.0
    average_hourly_op_units = daily_op_units / float(OFF_PEAK_HOURS)
    recommended_bess_kwh = average_hourly_op_units

    return {
        "months": months,

        # Solar Metrics
        "mp_units": round(total_mp_units, 2),
        "nh_units": round(total_nh_units, 2),
        "solar_usable_units": round(total_solar_usable_units, 2),
        "average_monthly_units": round(average_monthly_units, 2),
        "recommended_kw": recommended_kw,

        # BESS Metrics
        "op_units": round(total_op_units, 2),
        "average_monthly_op_units": round(average_monthly_op_units, 2),
        "daily_op_units": round(daily_op_units, 2),
        "average_hourly_op_units": round(average_hourly_op_units, 2),
        "recommended_bess_kwh": recommended_bess_kwh,

        # Reference
        "total_units": round(total_units, 2),
        "bill_data": bill_data,
    }
