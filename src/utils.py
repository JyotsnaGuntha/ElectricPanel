"""
Shared utility functions for the Microgrid Panel design system.
Handles data loading, calculations, and common operations.
"""

import pandas as pd
import math
from .constants import (
    STANDARD_MCCBS,
    FALLBACK_MCCB_DB,
    BUSBAR_CHAMBER_HEIGHTS,
    BUSBAR_THICKNESS,
)


# ============================================================================
# MCCB Database Loading
# ============================================================================

def load_mccb_dimensions_from_file(uploaded_file=None, path=None):
    """
    Parse Circuit Breaker Dimensions Excel with dynamic header detection.
    
    Expected columns: Ampere Rating, Height (mm), Width (mm), Depth (mm)
    Returns: dict keyed by ampere rating (int) with dimension data
    """
    def normalize_header(value):
        if value is None:
            return ''
        return str(value).strip().lower()

    try:
        raw = uploaded_file if uploaded_file is not None else path
        if raw is None:
            return {}
        
        df = pd.read_excel(raw, header=None)
        if df.empty:
            return {}

        # Find header row
        header_row = None
        header_cols = None
        for idx in range(min(10, len(df))):
            row = df.iloc[idx]
            normalized = [normalize_header(v) for v in row.tolist()]
            if any('ampere' in v or 'rating' in v for v in normalized) and \
               any('height' in v for v in normalized) and \
               any('width' in v for v in normalized) and \
               any('depth' in v for v in normalized):
                header_row = idx
                header_cols = normalized
                break

        if header_row is None:
            col_rating, col_height, col_width, col_depth = 0, 1, 2, 3
            data_start = 4
        else:
            def find_col(keywords):
                for i, h in enumerate(header_cols):
                    if any(k in h for k in keywords):
                        return i
                return None
            col_rating = find_col(['ampere', 'rating'])
            col_height = find_col(['height'])
            col_width = find_col(['width'])
            col_depth = find_col(['depth'])
            data_start = header_row + 1
            if None in (col_rating, col_height, col_width, col_depth):
                col_rating, col_height, col_width, col_depth = 0, 1, 2, 3
                data_start = 4

        db = {}
        for idx in range(data_start, len(df)):
            row = df.iloc[idx]
            try:
                raw_amp = normalize_header(row[col_rating]).replace('a', '').strip()
                if not raw_amp or raw_amp in ('nan', '') or 'rating' in raw_amp:
                    continue
                amp = int(float(raw_amp))
                h = int(float(str(row[col_height]).replace('mm', '').strip()))
                w = int(float(str(row[col_width]).replace('mm', '').strip()))
                d = int(float(str(row[col_depth]).replace('mm', '').strip()))
                frame = str(row[col_rating]).strip() if col_rating != 0 else f"{amp}A"
                poles = '3,4'
                if amp not in db or h < db[amp]['h']:
                    db[amp] = {
                        "h": h, "w": w, "d": d, "frame": frame,
                        "poles": poles, "label": f"{h}×{w}×{d} mm"
                    }
            except Exception:
                continue
        
        return db
    except Exception as e:
        print(f"MCCB dimension file error: {e}. Using fallback values.")
        return {}


def get_mccb_dims(rating, db):
    """
    Get MCCB dimensions for given rating from database.
    Falls back gracefully if rating not found.
    """
    active = db if db else FALLBACK_MCCB_DB
    if rating in active:
        return active[rating]
    for k in sorted(active.keys()):
        if k >= rating:
            return active[k]
    return active[sorted(active.keys())[-1]]


def get_standard_rating(val):
    """
    Return nearest standard MCCB rating >= given value.
    """
    for r in STANDARD_MCCBS:
        if r >= val:
            return r
    return STANDARD_MCCBS[-1]


# ============================================================================
# Busbar Sizing
# ============================================================================

def get_busbar_chamber_height(current_rating_A):
    """
    Return busbar chamber height (mm) based on total busbar current.
    Per IEC 61439 clearance + thermal derating guidelines.
    
    ≤ 400 A  → 100 mm
    401–800 A → 150 mm
    > 800 A  → 200 mm
    """
    if current_rating_A <= 400:
        return 100
    elif current_rating_A <= 800:
        return 150
    else:
        return 200


def get_busbar_thickness(current_rating_A):
    """Return recommended busbar thickness (mm)."""
    if current_rating_A <= 400:
        return 5
    elif current_rating_A <= 800:
        return 10
    else:
        return 12


# ============================================================================
# Current & Rating Calculations
# ============================================================================

def calculate_current_from_power(power_kw, voltage=415, pf=0.8, is_dg=False):
    """
    Calculate current (A) from power (kW) using 3-phase formula.
    
    For DG: use unity power factor (1.0)
    For grid/solar: use default PF or supplied value
    """
    if power_kw <= 0:
        return 0
    if is_dg:
        pf = 1.0
    current = (power_kw * 1000) / (math.sqrt(3) * voltage * pf)
    return current


def calculate_current_from_kva(kva, voltage=415, is_dg=True):
    """
    Calculate current (A) from power (kVA) using 3-phase formula.
    Used for DGs which are typically specified in kVA.
    """
    if kva <= 0:
        return 0
    current = (kva * 1000) / (math.sqrt(3) * voltage)
    return current


def get_mccb_rating(current):
    """
    Get MCCB rating with 1.25× safety margin.
    """
    required = current * 1.25
    for rating in STANDARD_MCCBS:
        if rating >= required:
            return rating
    return STANDARD_MCCBS[-1]


def get_mccb_breaking_capacity(mccb_rating):
    """
    Return recommended MCCB breaking capacity (kA) from a full rating-wise table.

    Any input is first normalized to the nearest standard MCCB rating so
    non-standard user-entered values are handled consistently.
    """
    rating = int(mccb_rating or 0)
    standard_rating = get_standard_rating(rating)

    breaking_capacity_by_rating = {
        16: "16kA",
        20: "16kA",
        25: "16kA",
        32: "16kA",
        40: "18kA",
        50: "18kA",
        63: "25kA",
        80: "25kA",
        100: "25kA",
        125: "25kA",
        160: "25kA",
        200: "36kA",
        250: "36kA",
        315: "36kA",
        400: "50kA",
        500: "50kA",
        630: "50kA",
        800: "65kA",
        1000: "65kA",
        1250: "85kA",
        1600: "100kA",
        2000: "100kA",
        2500: "100kA",
    }
    #dict.get(key, default)
    return breaking_capacity_by_rating.get(standard_rating, "36kA")


# ============================================================================
# Panel Sizing Helper
# ============================================================================

def calculate_row_width(ratings, mccb_db):
    """
    Calculate total width needed for a row of MCCBs.
    Includes gaps between MCCBs.
    """
    from .constants import MCCB_COL_GAP
    
    if not ratings:
        return 0
    total = sum(get_mccb_dims(r, mccb_db)['w'] for r in ratings)
    total += MCCB_COL_GAP * (len(ratings) - 1)
    return total


# ============================================================================
# Busbar Specification
# ============================================================================

def generate_busbar_spec(total_busbar_current, busbar_material="Copper"):
    """
    Generate busbar specification text based on current and material.
    Returns: formatted string like "1 Set (20 x 20 mm Copper)"
    """
    from .constants import BUSBAR_DENSITY
    
    density = BUSBAR_DENSITY.get(busbar_material, 1.0)
    busbar_area = total_busbar_current / density
    suggested_width = math.ceil(busbar_area / 10 / 5) * 5
    if suggested_width < 20:
        suggested_width = 20
    
    return f"1 Set ({suggested_width} x 20 mm {busbar_material})"


# ============================================================================
# Thickness & Clearance
# ============================================================================

def get_theme_colors(theme_name="dark"):
    """
    Get theme color palette. 'dark' or 'light'.
    Returns dict with color keys for UI styling.
    """
    from .constants import THEME_DARK, THEME_LIGHT
    return THEME_DARK if theme_name == "dark" else THEME_LIGHT


def get_ga_colors(theme_name="dark"):
    """
    Get GA-specific color palette for drawing.
    Returns dict with SVG color keys.
    """
    from .constants import GA_COLORS_DARK, GA_COLORS_LIGHT
    return GA_COLORS_DARK if theme_name == "dark" else GA_COLORS_LIGHT
