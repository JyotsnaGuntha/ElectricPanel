"""
PDF extraction and parsing for solar bill analysis.
"""

from __future__ import annotations

import base64
import io
import re
from typing import Any, Dict, Iterable, List

import pdfplumber


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

    slot_values: Dict[str, float] = {}
    slot_pattern = re.compile(r"^\s*(NH|EP|OP|MP)\s+(.*)$", re.IGNORECASE | re.MULTILINE)
    for match in slot_pattern.finditer(text):
        slot = match.group(1).upper()
        rest = match.group(2)
        raw_numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", rest)
        parsed_numbers = [value for value in (_parse_number(item) for item in raw_numbers) if value is not None]
        consumed = _pick_consumed_from_slot_numbers(parsed_numbers)
        if consumed is not None:
            slot_values[slot.lower()] = consumed

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


def parse_uploaded_bill_files(files: Iterable[Dict[str, Any]]) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    fallback_index = 1
    for file_payload in files or []:
        pdf_bytes = _decode_uploaded_pdf(file_payload.get("content"))
        file_rows = _extract_monthly_usage_rows(pdf_bytes)
        for row in file_rows:
            if not _clean_text(row.get("month")):
                row["month"] = f"Entry {fallback_index}"
                fallback_index += 1
            rows.append(row)
    return rows
