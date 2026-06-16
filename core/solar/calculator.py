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
        # Total Consumption = MP + EP
        total_solar_consumption += (row["mp"] + row["ep"])

    # Average Monthly Consumption = (MP + EP) / Total Number of Months
    average_monthly_consumption = total_solar_consumption / months
    # Average Daily Consumption = Average Monthly Consumption / 30
    average_daily_consumption = average_monthly_consumption / 30.0
    # Estimated Solar Capacity
    recommended_kw = _round_practical_kw(average_daily_consumption / 4.2)

    bill_data = [
        {
            "month": row["month"],
            "mp": row["mp"],
            "nh": row["nh"],
            "ep": row["ep"],
            "op": row["op"],
            "total": row["total"],
        }
        for row in validated_rows
    ]

    # BESS calculations
    avg_mp = total_mp_units / months
    avg_ep = total_ep_units / months
    avg_op = total_op_units / months

    daily_mp = avg_mp / 30.0
    daily_ep = avg_ep / 30.0
    daily_op = avg_op / 30.0

    daily_mp_ep = daily_mp + daily_ep

    if daily_mp_ep >= daily_op:
        backup_hours = 6
        daily_consumption = daily_mp_ep
    else:
        backup_hours = 8
        daily_consumption = daily_op

    if daily_consumption <= 0:
        backup_hours = 6
        daily_consumption = 0.0

    rte = 0.85 #round trip efficiency
    dod = 0.90 #Depth of Discharge
    divisor = rte * dod

    recommended_bess_kwh = daily_consumption / divisor if divisor > 0 else 0.0
    recommended_bess_kw = recommended_bess_kwh / backup_hours if backup_hours > 0 else 0.0

    return {
        "months": months,

        # Solar Metrics
        "solar_total_consumption": round(total_solar_consumption, 2),
        "solar_avg_monthly_consumption": round(average_monthly_consumption, 2),
        "solar_avg_daily_consumption": round(average_daily_consumption, 2),
        "recommended_kw": recommended_kw,

        # BESS Metrics
        "op_units": round(total_op_units, 2),
        "ep_units": round(total_ep_units, 2),
        "average_monthly_op_units": round(avg_op, 2),
        "daily_op_units": round(daily_consumption, 2),
        "recommended_bess_kwh": recommended_bess_kwh,
        "recommended_bess_kw": recommended_bess_kw,
        "backup_hours": backup_hours,

        # Reference
        "total_units": round(total_units, 2),
        "bill_data": bill_data,
    }
