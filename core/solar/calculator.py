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
from decimal import Decimal, ROUND_HALF_UP

OFF_PEAK_HOURS = 8


def _round_half_up(value: float, decimals: int = 2) -> float:
    try:
        s = f"{value:.12f}"
        d = Decimal(s)
        return float(d.quantize(Decimal('1.' + '0' * decimals), rounding=ROUND_HALF_UP))
    except Exception:
        return round(value, decimals)


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

    # Check if the extracted values are likely tariff rates (small values < 25.0)
    # instead of actual energy consumption.
    non_zero_vals = [val for val in (nh, ep, op, mp) if val > 0]
    if non_zero_vals and all(val < 25.0 for val in non_zero_vals):
        raise ValueError(f"Extracted values for {month} look like tariff rates (all < 25 Units).")

    mp_hours = float(row.get("mp_hours", 0.0))
    op_hours = float(row.get("op_hours", 0.0))

    return {
        "month": month,
        "nh": nh,
        "ep": ep,
        "op": op,
        "mp": mp,
        "total": total,
        "mp_hours": mp_hours,
        "op_hours": op_hours,
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
    total_mp_units = 0.0
    total_nh_units = 0.0
    total_ep_units = 0.0
    total_op_units = 0.0
    total_units = 0.0
    total_solar_consumption = 0.0

    for row in validated_rows:
        total_mp_units += row["mp"]
        total_nh_units += row["nh"]
        total_ep_units += row["ep"]
        total_op_units += row["op"]
        total_units += row["total"]

    # 1. Total Solar Consumable Units = Σ(NH + MP)
    solar_total_consumable = _round_half_up(total_nh_units + total_mp_units, 2)
    # 2. Solar Usable Units = Total Solar Consumable Units ÷ 126
    solar_usable_units = _round_half_up(solar_total_consumable / 126.0, 2)
    # 3. Average Monthly Solar Usable Units = Solar Usable Units ÷ Number of Months
    average_monthly_consumption = _round_half_up(solar_usable_units / months, 2)
    # 4. Average Daily Consumption = Average Monthly Solar Usable Units ÷ 30
    average_daily_consumption = _round_half_up(average_monthly_consumption / 30.0, 2)
    # 5. Recommended Solar Capacity (kW) = Average Monthly Solar Capacity
    recommended_kw = average_monthly_consumption

    bill_data = [
        {
            "month": row["month"],
            "mp": row["mp"],
            "nh": row["nh"],
            "ep": row["ep"],
            "op": row["op"],
            "total": row["total"],
            "mp_hours": row.get("mp_hours", 0.0),
            "op_hours": row.get("op_hours", 0.0),
        }
        for row in validated_rows
    ]

    # BESS calculations
    avg_mp = total_mp_units / months
    avg_nh = total_nh_units / months
    avg_ep = total_ep_units / months
    avg_op = total_op_units / months

    daily_mp = avg_mp / 30.0
    daily_nh = avg_nh / 30.0
    daily_ep = avg_ep / 30.0
    daily_op = avg_op / 30.0

    daily_non_solar_units = daily_mp + daily_op

    RTE = 0.85 #round trip efficiency
    DOD = 0.90 #Depth of Discharge
    system_divisor = RTE * DOD  # 0.765

    recommended_bess_kwh = daily_non_solar_units / system_divisor if system_divisor > 0.0 else 0.0

    # Determine MP and OP durations dynamically
    mp_hours_list = [row.get("mp_hours", 0.0) for row in validated_rows if row.get("mp_hours", 0.0) > 0.0]
    op_hours_list = [row.get("op_hours", 0.0) for row in validated_rows if row.get("op_hours", 0.0) > 0.0]

    mp_hours = mp_hours_list[0] if mp_hours_list else 3.0
    op_hours = op_hours_list[0] if op_hours_list else 8.0

    # Calculate the average power demand during each non-solar period
    mp_power = daily_mp / mp_hours if mp_hours > 0.0 else 0.0
    op_power = daily_op / op_hours if op_hours > 0.0 else 0.0

    # Size the BESS power rating based on the maximum hourly demand
    recommended_bess_kw = max(mp_power, op_power)

    return {
        "months": months,

        # Solar Metrics
        "solar_total_consumable": solar_total_consumable,
        "solar_usable_units": solar_usable_units,
        "solar_avg_monthly_consumption": average_monthly_consumption,
        "solar_avg_daily_consumption": average_daily_consumption,
        "recommended_kw": recommended_kw,

        # BESS Metrics
        "op_units": round(total_op_units, 2),
        "ep_units": round(total_ep_units, 2),
        "average_monthly_op_units": round(avg_op, 2),
        "daily_op_units": round(daily_non_solar_units, 2),
        "recommended_bess_kwh": recommended_bess_kwh,
        "recommended_bess_kw": recommended_bess_kw,
        "backup_hours": op_hours,

        # New keys requested by user
        "daily_mp": daily_mp,
        "daily_op": daily_op,
        "mp_hours": mp_hours,
        "op_hours": op_hours,
        "mp_power": mp_power,
        "op_power": op_power,

        # Reference
        "total_units": round(total_units, 2),
        "bill_data": bill_data,
    }
