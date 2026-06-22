"""
PDF extraction and parsing for solar bill analysis.
"""

from __future__ import annotations

import base64
import io
import re
from typing import Any, Dict, Iterable, List

import pdfplumber

import os
from dotenv import load_dotenv
from llama_parse import LlamaParse
load_dotenv()

parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type="markdown"
)

# from openai import OpenAI
# import json

# client = OpenAI(
#     api_key=os.getenv("OPENAI_API_KEY")
# )

import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_KEY2") or os.getenv("GEMINI_API_KEY")or os.getenv("GEMINI_KEY"))
model = genai.GenerativeModel(
    "gemini-2.5-flash"
)

def _decode_uploaded_pdf(content: Any) -> bytes:
    if not content:
        raise ValueError("Uploaded PDF content is empty.")

    if isinstance(content, bytes):
        return content

    if not isinstance(content, str):
        raise ValueError("Uploaded PDF content must be a string or bytes payload.")

    raw_content = content.strip()
    if raw_content.startswith("data:") and "," in raw_content:
        raw_content = raw_content.split(",", 1)[1]

    return base64.b64decode(raw_content)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None

    text = _clean_text(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group(0))
    except Exception:
        return None


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", _clean_text(value).upper())


def _extract_month_label(text: str) -> str:
    if not text:
        return ""

    month_patterns = [
        r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z]*\s*[-/ ]?\s*\d{2,4}\b",
        r"\b\d{1,2}[-/](?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z]*[-/]\d{2,4}\b",
    ]

    upper = text.upper()
    for pattern in month_patterns:
        match = re.search(pattern, upper)
        if match:
            return _clean_text(match.group(0)).title()
    return ""


def _build_clean_row(month: str, nh: float, ep: float, op: float, mp: float, total: float | None = None) -> Dict[str, float] | None:
    if any(value is None for value in (nh, ep, op, mp)):
        return None

    row_total = float(nh + ep + op + mp)
    if row_total <= 0:
        return None

    clean_total = row_total if total is None else float(total)
    if abs(clean_total - row_total) > 2:
        clean_total = row_total

    return {
        "month": _clean_text(month),
        "nh": float(nh),
        "ep": float(ep),
        "op": float(op),
        "mp": float(mp),
        "total": float(clean_total),
    }


def _extract_labelled_values_map(raw_text: str) -> Dict[str, float]:
    values: Dict[str, float] = {}
    if not raw_text:
        return values

    patterns = {
        "nh": r"\bN\s*H\b\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)",
        "ep": r"\bE\s*P\b\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)",
        "op": r"\bO\s*P\b\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)",
        "mp": r"\bM\s*P\b\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)",
        "total": r"\bTOTAL(?:\s+UNITS?)?\b\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            parsed = _parse_number(match.group(1))
            if parsed is not None:
                values[key] = parsed

    return values


def _extract_bill_month(text: str) -> str:
    if not text:
        return ""

    month_patterns = [
        r"MONTH\s*/\s*YEAR\s*[:\-]\s*(\d{1,2}\s*/\s*\d{2,4})",
        r"MONTH\s*[:\-]\s*(\d{1,2}\s*/\s*\d{2,4})",
    ]
    upper = text.upper()
    for pattern in month_patterns:
        match = re.search(pattern, upper)
        if match:
            return _clean_text(match.group(1)).replace(" ", "")

    return _extract_month_label(text)


def _pick_consumed_from_slot_numbers(numbers: List[float]) -> float | None:
    if len(numbers) < 3:
        return None

    candidate = numbers[-3]
    if candidate is not None:
        return float(candidate)

    for value in reversed(numbers):
        if value is not None:
            return float(value)

    return None


def _extract_slot_rows_from_text(text: str) -> List[Dict[str, float]]:
    if not text:
        return []

    slot_map = _extract_zone_time_mappings(text)
    slot_values: Dict[str, float] = {}
    
    keys = sorted(slot_map.keys(), key=len, reverse=True)
    keys_pat = "|".join(re.escape(k) for k in keys if len(k) <= 10)
    if not keys_pat:
        keys_pat = "NH|EP|OP|MP"
        
    slot_pattern = re.compile(r"^\s*(" + keys_pat + r")\s+(.*)$", re.IGNORECASE | re.MULTILINE)
    for match in slot_pattern.finditer(text):
        slot = match.group(1).upper()
        rest = match.group(2)
        raw_numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", rest)
        parsed_numbers = [value for value in (_parse_number(item) for item in raw_numbers) if value is not None]
        consumed = _pick_consumed_from_slot_numbers(parsed_numbers)
        if consumed is not None:
            mapped_slot = slot_map.get(slot)
            if not mapped_slot:
                for k, v in slot_map.items():
                    if k in slot:
                        mapped_slot = v
                        break
            if mapped_slot:
                slot_values[mapped_slot.lower()] = consumed

    total = None
    total_match = re.search(r"^\s*TOTAL\s+(.*)$", text, flags=re.IGNORECASE | re.MULTILINE)
    if total_match:
        total_numbers = [
            value
            for value in (_parse_number(item) for item in re.findall(r"\d[\d,]*(?:\.\d+)?", total_match.group(1)))
            if value is not None and value > 0
        ]
        if total_numbers:
            total = float(total_numbers[0])

    if {"nh", "ep", "op", "mp"} - slot_values.keys():
        return []

    month_label = _extract_bill_month(text)
    clean_row = _build_clean_row(month_label, slot_values["nh"], slot_values["ep"], slot_values["op"], slot_values["mp"], total)
    return [clean_row] if clean_row else []


def _extract_month_rows_from_label_value_table(table: List[List[str]]) -> List[Dict[str, float]]:
    values: Dict[str, float] = {}
    month_hint = ""

    for row in table:
        if not row:
            continue
        first_cell = row[0] if len(row) > 0 else ""
        second_cell = row[1] if len(row) > 1 else ""
        token = _normalize_token(first_cell)
        number = _parse_number(second_cell)

        if not month_hint:
            month_hint = _extract_month_label(" ".join(row))

        if token in ("NH", "NIGHTHOURS", "NIGHT") and number is not None:
            values["nh"] = number
        elif token in ("EP", "EVENINGPEAK", "EVENING") and number is not None:
            values["ep"] = number
        elif token in ("OP", "OFFPEAK", "OFF") and number is not None:
            values["op"] = number
        elif token in ("MP", "MORNINGPEAK", "MORNING") and number is not None:
            values["mp"] = number
        elif token.startswith("TOTAL") and number is not None:
            values["total"] = number

    if {"nh", "ep", "op", "mp"} - values.keys():
        return []

    row = _build_clean_row(month_hint, values["nh"], values["ep"], values["op"], values["mp"], values.get("total"))
    return [row] if row else []


def _extract_month_rows_from_table(table: Iterable[Iterable[Any]]) -> List[Dict[str, float]]:
    normalized = [[_clean_text(cell) for cell in row] for row in table if any(_clean_text(cell) for cell in row)]
    if not normalized:
        return []

    header_row_index = None
    column_map: Dict[str, int] = {}

    for row_index, row in enumerate(normalized):
        joined = " ".join(row).upper()
        if "UNIT CONSUMED" not in joined:
            continue

        for column_index, cell in enumerate(row):
            cell_upper = cell.upper()
            if "NH" in cell_upper and "EP" not in cell_upper and "MP" not in cell_upper:
                column_map["nh"] = column_index
            elif "EP" in cell_upper:
                column_map["ep"] = column_index
            elif "OP" in cell_upper and "TOP" not in cell_upper:
                column_map["op"] = column_index
            elif "MP" in cell_upper:
                column_map["mp"] = column_index
            elif "TOTAL" in cell_upper:
                column_map["total"] = column_index

        if {"nh", "ep", "op", "mp"}.issubset(column_map):
            header_row_index = row_index
            break

    if header_row_index is None:
        for row_index, row in enumerate(normalized):
            upper_row = [cell.upper() for cell in row]
            if {"NH", "EP", "OP", "MP"}.issubset(set(upper_row)):
                header_row_index = row_index
                for column_index, cell in enumerate(upper_row):
                    if cell == "NH":
                        column_map["nh"] = column_index
                    elif cell == "EP":
                        column_map["ep"] = column_index
                    elif cell == "OP":
                        column_map["op"] = column_index
                    elif cell == "MP":
                        column_map["mp"] = column_index
                    elif "TOTAL" in cell:
                        column_map["total"] = column_index
                break

    if header_row_index is None or {"nh", "ep", "op", "mp"} - column_map.keys():
        return _extract_month_rows_from_label_value_table(normalized)

    rows: List[Dict[str, float]] = []
    for row in normalized[header_row_index + 1 :]:
        if not any(row):
            continue

        month_label = next((cell for cell in row if cell and not re.fullmatch(r"[\d.,-]+", cell)), "")
        month_label = month_label or _extract_month_label(" ".join(row))
        nh = _parse_number(row[column_map["nh"]] if column_map["nh"] < len(row) else None)
        ep = _parse_number(row[column_map["ep"]] if column_map["ep"] < len(row) else None)
        op = _parse_number(row[column_map["op"]] if column_map["op"] < len(row) else None)
        mp = _parse_number(row[column_map["mp"]] if column_map["mp"] < len(row) else None)
        total = _parse_number(row[column_map["total"]] if column_map.get("total", len(row)) < len(row) else None)

        clean_row = _build_clean_row(month_label, nh, ep, op, mp, total)
        if clean_row:
            rows.append(clean_row)

    return rows


def _extract_month_rows_from_text(text: str) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    if not text:
        return rows

    pattern = re.compile(
        r"(?P<month>[A-Za-z0-9][A-Za-z0-9 /_.-]{0,60}?)\s+UNIT\s+CONSUMED.*?"
        r"NH\s*[:\-]?\s*(?P<nh>[\d,]+(?:\.\d+)?)\s+"
        r"EP\s*[:\-]?\s*(?P<ep>[\d,]+(?:\.\d+)?)\s+"
        r"OP\s*[:\-]?\s*(?P<op>[\d,]+(?:\.\d+)?)\s+"
        r"MP\s*[:\-]?\s*(?P<mp>[\d,]+(?:\.\d+)?)\s+"
        r"(?:TOTAL\s+UNITS?|TOTAL)?\s*[:\-]?\s*(?P<total>[\d,]+(?:\.\d+)?)?",
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(text):
        nh = _parse_number(match.group("nh"))
        ep = _parse_number(match.group("ep"))
        op = _parse_number(match.group("op"))
        mp = _parse_number(match.group("mp"))
        total = _parse_number(match.group("total"))
        clean_row = _build_clean_row(match.group("month").strip(), nh, ep, op, mp, total)
        if clean_row:
            rows.append(clean_row)

    if not rows:
        rows.extend(_extract_slot_rows_from_text(text))

    if not rows:
        values = _extract_labelled_values_map(text)
        if {"nh", "ep", "op", "mp"}.issubset(values):
            month_label = _extract_month_label(text)
            clean_row = _build_clean_row(month_label, values["nh"], values["ep"], values["op"], values["mp"], values.get("total"))
            if clean_row:
                rows.append(clean_row)

    return rows


def _extract_monthly_usage_rows(pdf_bytes: bytes) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            rows.extend(_extract_month_rows_from_text(text))

            for table in page.extract_tables() or []:
                rows.extend(_extract_month_rows_from_table(table))

    unique_rows: List[Dict[str, float]] = []
    seen = set()
    for row in rows:
        key = (row["month"], row["nh"], row["ep"], row["op"], row["mp"], row["total"])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    return unique_rows


# def parse_uploaded_bill_files(files: Iterable[Dict[str, Any]]) -> List[Dict[str, float]]:
#     rows: List[Dict[str, float]] = []
#     fallback_index = 1
#     for file_payload in files or []:
#         pdf_bytes = _decode_uploaded_pdf(file_payload.get("content"))
#         file_rows = _extract_monthly_usage_rows(pdf_bytes)
#         for row in file_rows:
#             if not _clean_text(row.get("month")):
#                 row["month"] = f"Entry {fallback_index}"
#                 fallback_index += 1
#             rows.append(row)
#     return rows

def parse_uploaded_bill_files(files):
    rows = []
    fallback_index = 1
    for file_payload in files or []:
        pdf_bytes = _decode_uploaded_pdf(
            file_payload.get("content")
        )
        text = extract_bill_using_llamaparse(
            pdf_bytes
        )
        print("\n========== LLAMAPARSE OUTPUT ==========\n")
        print(text)
        print("\n=======================================\n")
        
        # Try local parsing first to avoid API calls
        file_rows = _extract_llamaparse_table(text)
        if not file_rows:
            file_rows = _extract_month_rows_from_text(text)
        if not file_rows:
            file_rows = _extract_monthly_usage_rows(pdf_bytes)
            
        local_succeeded = False
        if file_rows:
            for r in file_rows:
                if r.get("nh", 0) + r.get("ep", 0) + r.get("op", 0) + r.get("mp", 0) > 0:
                    local_succeeded = True
                    break

        if not local_succeeded:
            try:
                bill_json = extract_bill_json(text)
                if bill_json and isinstance(bill_json, dict):
                    if not bill_json.get("month"):
                        bill_json["month"] = _extract_bill_month(text) or f"Entry {fallback_index}"
                    file_rows = [bill_json]
            except Exception as e:
                print(f"Gemini API error (could be rate limit/quota): {e}")
                if not file_rows:
                    file_rows = [{
                        "month": _extract_bill_month(text) or f"Entry {fallback_index}",
                        "nh": 0.0,
                        "ep": 0.0,
                        "op": 0.0,
                        "mp": 0.0,
                        "total": 0.0
                    }]

        durations = _extract_tod_durations_from_text(text)
        for row in file_rows:
            if not _clean_text(row.get("month")):
                row["month"] = f"Entry {fallback_index}"
                fallback_index += 1
            row["mp_hours"] = durations.get("MP", 0.0)
            row["op_hours"] = durations.get("OP", 0.0)
            rows.append(row)

        print(file_rows)
    return rows

def extract_bill_using_llamaparse(pdf_bytes):

    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False
    ) as temp_pdf:

        temp_pdf.write(pdf_bytes)
        temp_path = temp_pdf.name

    documents = parser.load_data(temp_path)

    return "\n".join(
        doc.text for doc in documents
    )

def _parse_time_str(t_str: str) -> float | None:
    t_str = t_str.strip().upper()
    if not t_str:
        return None
        
    # Check for AM/PM format
    am_pm_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", t_str)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2)) if am_pm_match.group(2) else 0
        am_pm = am_pm_match.group(3)
        if am_pm == "PM" and hour != 12:
            hour += 12
        elif am_pm == "AM" and hour == 12:
            hour = 0
        return hour + minute / 60.0

    # Check for HH:MM or HH.MM format
    hh_mm_match = re.search(r"(\d{1,2})[:.](\d{2})", t_str)
    if hh_mm_match:
        hour = int(hh_mm_match.group(1))
        minute = int(hh_mm_match.group(2))
        return hour + minute / 60.0
        
    # Check for plain hour format (e.g. "6" or "17" or "0600")
    if t_str.isdigit():
        val = int(t_str)
        if len(t_str) == 4:  # e.g. "0600" or "1700"
            hour = val // 100
            minute = val % 100
            return hour + minute / 60.0
        elif val <= 24:      # e.g. "6" or "17"
            return float(val)
            
    return None

def _parse_time_range(range_str: str) -> tuple[float, float] | None:
    range_str = range_str.strip().lower()
    # Replace separators with a standard character |
    for sep in ["to", "till", "–", "—", "-"]:
        if sep in range_str:
            parts = range_str.split(sep, 1)
            s_val = _parse_time_str(parts[0])
            e_val = _parse_time_str(parts[1])
            if s_val is not None and e_val is not None:
                return s_val, e_val
    return None

def _map_time_range_to_period(range_str: str) -> str | None:
    parsed = _parse_time_range(range_str)
    if not parsed:
        return None
    s, e = parsed
    
    # Standard periods
    periods = {
        "OP": (0.0, 6.0),
        "MP": (6.0, 9.0),
        "NH": (9.0, 17.0),
        "EP": (17.0, 24.0)
    }
    
    overlaps = {}
    for p_name, (S, E) in periods.items():
        if e > s:
            overlap = max(0.0, min(e, E) - max(s, S))
        else:
            # Wrap around midnight
            overlap = max(0.0, min(24.0, E) - max(s, S)) + max(0.0, min(e, E) - max(0.0, S))
        overlaps[p_name] = overlap
        
    best_period = max(overlaps, key=overlaps.get)
    if overlaps[best_period] > 0.0:
        return best_period
    return None

def _extract_zone_time_mappings(text: str) -> Dict[str, str]:
    mappings = {}
    lines = text.splitlines()
    for line in lines:
        # Check if line contains a time range
        # Regex to find time ranges like 00:00-06:00, 00.00 to 06.00, 12 AM to 6 AM, etc.
        time_range_pattern = r"(\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM)?)\s*(?:-|–|—|to|till)\s*(\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM)?)"
        match = re.search(time_range_pattern, line, re.IGNORECASE)
        if not match:
            continue
            
        range_str = match.group(0)
        period = _map_time_range_to_period(range_str)
        if not period:
            continue
            
        # Now find the slot/zone label in the same line
        if line.startswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            # Find which column contains the range
            range_col_idx = -1
            for idx, col in enumerate(cols):
                if range_str in col or col in range_str:
                    range_col_idx = idx
                    break
            # Look at other columns for zone/slot label
            for idx, col in enumerate(cols):
                if idx == range_col_idx:
                    continue
                col_upper = col.upper()
                label_match = re.search(r"\b(?:ZONE|SLOT|TOD)?\s*([A-D0-9])\b", col_upper)
                if label_match:
                    zone_label = label_match.group(1)
                    mappings[zone_label] = period
                    mappings[col_upper] = period
                    mappings[f"ZONE {zone_label}"] = period
                    mappings[f"SLOT {zone_label}"] = period
        else:
            line_upper = line.upper()
            label_match = re.search(r"\b(?:ZONE|SLOT|TOD)?\s*([A-D0-9])\b", line_upper)
            if label_match:
                zone_label = label_match.group(1)
                mappings[zone_label] = period
                mappings[line_upper] = period
                mappings[f"ZONE {zone_label}"] = period
                mappings[f"SLOT {zone_label}"] = period
                
    # Always include standard mappings as a fallback if not overwritten
    default_mappings = {
        "NH": "NH", "EP": "EP", "OP": "OP", "MP": "MP",
        "TOTAL": "TOTAL"
    }
    for k, v in default_mappings.items():
        if k not in mappings:
            mappings[k] = v
            
    return mappings


def _extract_tod_durations_from_text(text: str) -> Dict[str, float]:
    time_range_pattern = r"(\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM)?)\s*(?:-|–|—|to|till)\s*(\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM)?)"
    
    period_ranges = {
        "OP": set(),
        "MP": set(),
        "NH": set(),
        "EP": set()
    }
    
    for line in text.splitlines():
        for match in re.finditer(time_range_pattern, line, re.IGNORECASE):
            range_str = match.group(0)
            parsed = _parse_time_range(range_str)
            if not parsed:
                continue
            s, e = parsed
            period = _map_time_range_to_period(range_str)
            if period in period_ranges:
                period_ranges[period].add((s, e))
                
    durations = {}
    for period, ranges in period_ranges.items():
        total_hours = 0.0
        for s, e in ranges:
            if e > s:
                total_hours += (e - s)
            else:
                total_hours += (24.0 - s) + e
        durations[period] = total_hours
        
    return durations

def _find_consumed_column(lines: List[str], slot_map: Dict[str, str]) -> int:
    valid_rows = []
    for line in lines:
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 3:
            continue
        slot = cols[1].upper()
        if slot in slot_map or any(k in slot for k in slot_map):
            valid_rows.append(cols)
            
    if not valid_rows:
        return 5
        
    num_cols = len(valid_rows[0])
    scores = {idx: 0 for idx in range(2, num_cols)}
    
    for cols in valid_rows:
        vals = {}
        for idx in range(2, len(cols)):
            try:
                cleaned = cols[idx].replace(",", "").strip()
                match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
                if match:
                    vals[idx] = float(match.group(0))
            except:
                pass
                
        # Score the columns based on algebraic relationships
        for idx, val in vals.items():
            if idx not in scores:
                continue
            # Exclude very small numbers (likely tariff rates) as consumption
            if val < 25.0:
                scores[idx] -= 20
                continue
                
            # Meter reading diff relation: B - A = C
            for idx_a, val_a in vals.items():
                for idx_b, val_b in vals.items():
                    if idx_a != idx and idx_b != idx and idx_a != idx_b:
                        if abs((val_b - val_a) - val) < 2.0 and val > 20.0:
                            scores[idx] += 15
                            
            # Consumed * Rate = Total relation
            for idx_rate, val_rate in vals.items():
                for idx_total, val_total in vals.items():
                    if idx_rate != idx and idx_total != idx and idx_rate != idx_total:
                        if 1.0 < val_rate < 25.0:
                            if abs((val * val_rate) - val_total) < 10.0:
                                scores[idx] += 10

    best_idx = max(scores, key=scores.get)
    if scores[best_idx] <= 0:
        return 5
    return best_idx


def _extract_llamaparse_table_hardcoded(text: str, month: str):
    values = {}
    slot_map = _extract_zone_time_mappings(text)
    
    lines = text.splitlines()
    consumed_idx = _find_consumed_column(lines, slot_map)
    print(f"Dynamically determined consumed units column index: {consumed_idx}")
    
    for line in lines:
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) <= consumed_idx:
            continue
        slot = cols[1].upper()
        mapped_slot = slot_map.get(slot)
        if not mapped_slot:
            for k, v in slot_map.items():
                if k in slot:
                    mapped_slot = v
                    break
        if not mapped_slot:
            continue
        try:
            unit_consumed = float(cols[consumed_idx].replace(",", ""))
            values[mapped_slot] = unit_consumed
        except:
            continue
            
    if {"NH", "EP", "OP", "MP"}.issubset(values):
        row_total = values["NH"] + values["EP"] + values["OP"] + values["MP"]
        if row_total > 0:
            return [{
                "month": month,
                "nh": values["NH"],
                "ep": values["EP"],
                "op": values["OP"],
                "mp": values["MP"],
                "total": values.get("TOTAL", row_total)
            }]
    return []

def _extract_llamaparse_table(text: str):
    month = ""
    month_match = re.search(
        r"MONTH\s*/\s*YEAR\s*:\s*(\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE
    )
    if not month_match:
        month_match = re.search(
            r"BILL(?:ING)?\s+MONTH\s*:\s*([A-Za-z]{3,9}\s*\d{2,4})",
            text,
            re.IGNORECASE
        )
    if month_match:
        month = month_match.group(1).strip()
    else:
        month = _extract_month_label(text)

    # Parse markdown tables
    lines = text.splitlines()
    table_headers = None
    table_rows = []
    
    for line in lines:
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue
        
        # Check if separator row
        if all(re.match(r"^[-:\s]+$", c) for c in cols):
            continue
            
        # Check for header
        cols_upper = [c.upper() for c in cols]
        if any("SLOT" in c or "ZONE" in c or "TOD" in c for c in cols_upper) and any("CONSUM" in c or "UNIT" in c or "DIFF" in c for c in cols_upper):
            table_headers = cols_upper
            table_rows = []
            continue
            
        if table_headers:
            table_rows.append(cols)
            
    if not table_headers or not table_rows:
        return _extract_llamaparse_table_hardcoded(text, month)
        
    slot_idx = -1
    consum_idx = -1
    for i, h in enumerate(table_headers):
        if "SLOT" in h or "ZONE" in h or "TOD" in h:
            slot_idx = i
        if ("CONSUM" in h or "DIFF" in h or "UNIT" in h) and "RATE" not in h and "TARIFF" not in h and "RS" not in h:
            if "CONSUM" in h or "DIFF" in h:
                consum_idx = i
            elif consum_idx == -1:
                consum_idx = i
            
    if slot_idx == -1 or consum_idx == -1:
        return _extract_llamaparse_table_hardcoded(text, month)
        
    values = {}
    slot_map = _extract_zone_time_mappings(text)
    
    for row in table_rows:
        if len(row) <= max(slot_idx, consum_idx):
            continue
        slot = row[slot_idx].strip().upper()
        mapped_slot = slot_map.get(slot)
        if not mapped_slot:
            for k, v in slot_map.items():
                if k in slot:
                    mapped_slot = v
                    break
        if not mapped_slot:
            continue
            
        try:
            val_str = row[consum_idx].replace(",", "").strip()
            num_match = re.search(r"\d+(?:\.\d+)?", val_str)
            if num_match:
                values[mapped_slot] = float(num_match.group(0))
        except:
            continue
            
    if {"NH", "EP", "OP", "MP"}.issubset(values):
        row_total = values["NH"] + values["EP"] + values["OP"] + values["MP"]
        if row_total > 0:
            return [{
                "month": month,
                "nh": values["NH"],
                "ep": values["EP"],
                "op": values["OP"],
                "mp": values["MP"],
                "total": values.get("TOTAL", row_total)
            }]
            
    return _extract_llamaparse_table_hardcoded(text, month)

import json

def extract_bill_json(text: str):

    prompt = f"""
You are an expert electricity bill analyzer.

Extract ONLY the following JSON.

Rules:

1. If NH EP OP MP exist, use them directly.

2. If the bill contains TOD zones/slots (e.g., Zone A, B, C, D, or Zone 1, 2, 3, 4, etc.):
   Do NOT assume fixed mappings (like Zone A is always OP). Instead, dynamically map each zone/slot to standard periods based on the associated time ranges:
   - 00:00 – 06:00 (or 12 AM to 6 AM) → OP (Off-Peak Period)
   - 06:00 – 09:00 (or 6 AM to 9 AM) → MP (Morning Period)
   - 09:00 – 17:00 (or 9 AM to 5 PM) → NH (Normal Hours)
   - 17:00 – 24:00 (or 5 PM to 12 AM) → EP (Evening Period)

3. Extract UNIT CONSUMED values only.

4. Never use:
   - Current Reading
   - Previous Reading
   - Meter Reading

5. NEVER extract Unit Rate or Tariff Rate values (which are small decimal numbers like 6.4, 8.32, 4.8, 6.85, 8.91, 5.14, etc.). You must always extract the actual energy consumption values (UNIT CONSUMED) which are much larger integers.

6. Return ONLY JSON.

Schema:

{{
    "month":"",
    "nh":0,
    "ep":0,
    "op":0,
    "mp":0,
    "total":0
}}

Bill:

{text}
"""

    response = model.generate_content(prompt)

    content = response.text.strip()

    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    
    print("------------------------GEMINI RESPONSE:")
    print(content)

    return json.loads(content)
    
    