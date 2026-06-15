"""
Global constants and standards for Microgrid Panel design.
All values follow IEC 61439 and industry best practices.
"""

# ============================================================================
# ELECTRICAL STANDARDS & CURRENT RATINGS
# ============================================================================
# MCCB ratings are loaded from Circuit breaker_dimensions.xlsx

# System electrical parameters
NOMINAL_VOLTAGE = 415          # 3-phase, line-to-line (Volts)
POWER_FACTOR = 0.8             # Standard PF for calculations
DG_POWER_FACTOR = 1.0          # DG power factor (unity)

# MCCB safety margin
MCCB_SAFETY_MARGIN = 1.25      # 25% safety factor on current

# ============================================================================
# PANEL PHYSICAL DIMENSIONS (IEC 61439 aligned)
# ============================================================================
PLINTH_H = 200                 # Panel plinth / cable entry zone (mm)
PANEL_D = 400                  # Fixed panel depth (mm)
CABLE_DUCT_H = 150             # Wiring duct at bottom of mounting plate (mm)
TOP_MARGIN_H = 80              # Clearance above incomers (mm)

# ============================================================================
# CLEARANCES (IEC 61439 - Safety & Thermal)
# ============================================================================
CLEARANCE_PP = 25              # Phase-to-phase clearance (mm)
CLEARANCE_PE = 20              # Phase-to-earth clearance (mm)
MCCB_COL_GAP = 150             # Horizontal gap between MCCBs (mm)
ROW_GAP_MM = 100               # Vertical gap between incomer and outgoing rows (mm)
SIDE_MARGIN = 150             # Left+right margin inside mounting plate (mm)

# ============================================================================
# BUSBAR CHAMBER SIZING (IEC 61439 / OEM practice)
# ============================================================================
BUSBAR_CHAMBER_HEIGHTS = {
    400: 100,                  # ≤ 400 A → 100 mm
    800: 150,                  # 401–800 A → 150 mm
    float('inf'): 200,         # > 800 A → 200 mm
}

BUSBAR_THICKNESS = {
    400: 5,                    # ≤ 400 A → 5 mm
    800: 10,                   # 401–800 A → 10 mm
    float('inf'): 12,          # > 800 A → 12 mm
}

# ============================================================================
# BUSBAR MATERIAL PROPERTIES
# ============================================================================
BUSBAR_DENSITY = {
    "Copper": 1.6,
    "Aluminium": 1.0,
    "Aluminum": 1.0,
}

# ============================================================================
# MCCB FALLBACK DIMENSIONS (if Excel file not provided)
# ============================================================================
FALLBACK_MCCB_DB = {
    125:  {"h": 137, "w":  81, "d":  89, "frame": "B-Frame", "poles": "1,2,3,4", "label": "137×81×89 mm"},
    150:  {"h": 163, "w": 104, "d":  86, "frame": "H-Frame", "poles": "2,3",     "label": "163×104×86 mm"},
    250:  {"h": 191, "w": 104, "d":  86, "frame": "J-Frame", "poles": "2,3",     "label": "191×104×86 mm"},
    400:  {"h": 279, "w": 152, "d": 148, "frame": "400A",    "poles": "3",       "label": "279×152×148 mm"},
    630:  {"h": 340, "w": 140, "d": 110, "frame": "L-Frame", "poles": "3,4",     "label": "340×140×110 mm"},
    800:  {"h": 325, "w": 210, "d": 205, "frame": "M-Frame", "poles": "2,3",     "label": "325×210×205 mm"},
    1200: {"h": 413, "w": 210, "d": 205, "frame": "P-Frame", "poles": "2,3,4",   "label": "413×210×205 mm"},
}

# ============================================================================
# PANEL SIZING RULES
# ============================================================================
MIN_PANEL_WIDTH = 800          # Minimum panel width (mm)
MIN_PANEL_HEIGHT = 1200        # Minimum panel height (mm)
DIMENSION_ROUNDING = 100       # Round panel dimensions to nearest 100 mm

# ============================================================================
# DEFAULT MATERIAL SPECIFICATIONS
# ============================================================================
DEFAULT_PANEL_COLOR = "RAL 7035"           # Light Grey
DEFAULT_MOUNTING_FINISH = "Chrome Plating / Zinc Passivated"
DEFAULT_MCCB_BREAKING_CAPACITY = "36kA"    # Standard breaking capacity
DEFAULT_CONTROL_CABLE_SIZE = "1.5 sqmm"    # Control cable
DEFAULT_CABLE_LENGTH_CONTROL = 100         # Meters
DEFAULT_CABLE_LENGTH_POWER = 50            # Meters

# ============================================================================
# THEME COLORS - Dark Theme
# ============================================================================
THEME_DARK = {
    "bg": "linear-gradient(135deg, #062a30, #020617)",
    "card": "rgba(6, 42, 48, 0.8)",
    "text": "#e2e8f0",
    "subtitle": "#94a3b8",
    "border": "rgba(195, 124, 91, 0.3)",
    "title": "#c37c5a",
    "svg_bg": "#020617",
    "svg_stroke": "#334155",
}

# ============================================================================
# THEME COLORS - Light Theme
# ============================================================================
THEME_LIGHT = {
    "bg": "linear-gradient(135deg, #f8fafc, #e2e8f0)",
    "card": "rgba(255, 255, 255, 0.95)",
    "text": "#0f172a",
    "subtitle": "#475569",
    "border": "rgba(25, 152, 139, 0.4)",
    "title": "#19988b",
    "svg_bg": "#fcfdfd",
    "svg_stroke": "#cbd5e1",
}

# ============================================================================
# GA DRAWING COLORS (Responsive)
# ============================================================================
GA_COLORS_DARK = {
    "bg": "#0a0f1e",
    "shell": "#1a2e4a",
    "stroke": "#4a9eca",
    "dim": "#f59e0b",
    "text": "#e2e8f0",
    "hatch": "#1e4080",
    "mounting_plate": "#0d1f36",
    "busbar": "#7f1d1d",
    "busbar_stroke": "#ef4444",
    "zone_separator": "#2563eb",
    "spec_bg": "#0b1929",
    "spec_border": "#2dd4bf",
    "header": "#2dd4bf",
    "sub": "#94a3b8",
    "grid": "#1e3252",
}

GA_COLORS_LIGHT = {
    "bg": "#ffffff",
    "shell": "#e2e8f0",
    "stroke": "#64748b",
    "dim": "#d97706",
    "text": "#0f172a",
    "hatch": "#cbd5e1",
    "mounting_plate": "#f1f5f9",
    "busbar": "#fee2e2",
    "busbar_stroke": "#f87171",
    "zone_separator": "#94a3b8",
    "spec_bg": "#ffffff",
    "spec_border": "#19988b",
    "header": "#19988b",
    "sub": "#64748b",
    "grid": "#cbd5e1",
}

# ============================================================================
# SVG CANVAS SIZING
# ============================================================================
GA_SVG_WIDTH = 1500            # GA drawing canvas pixel width
GA_SVG_HEIGHT = 940            # GA drawing canvas pixel height

# GA Layout dimensions (pixels)
GA_LEFT_MARGIN = 120           # Room for vertical dimension arrows
GA_FRONT_MAX_W = 680           # Max width for front elevation
GA_ELEV_GAP = 70               # Gap between front and side elevation
GA_SIDE_MAX_W = 140            # Max width for side elevation
GA_BOTTOM_STRIP = 46           # Title strip height at bottom

# ============================================================================
# SLD CANVAS SIZING
# ============================================================================
SLD_MIN_WIDTH = 950            # Minimum SLD canvas width
SLD_HEIGHT = 950               # Fixed SLD canvas height
SLD_MIN_COL_SPACING = 250      # Minimum column spacing (px)
SLD_MARGIN_LEFT = 100          # Left margin
SLD_MARGIN_RIGHT = 120         # Right margin

# ============================================================================
# PDF EXPORT SETTINGS
# ============================================================================
PDF_PAGE_MARGIN_H = 40         # Horizontal margin (mm)
PDF_PAGE_MARGIN_V = 50         # Vertical margin (mm)
