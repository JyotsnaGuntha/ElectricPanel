import streamlit as st
import math
import io
import svgwrite as svg
import base64
import pandas as pd
import datetime

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.platypus import PageBreak
from reportlab.pdfgen import canvas
 
# ---------------- STANDARDS & CONSTANTS ----------------
STANDARD_MCCBS = [16,20,25,32,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500]

MCCB_DIMENSIONS = {
    100: "150x75x130",
    250: "200x105x160",
    400: "255x140x180",
    630: "320x210x200"
}

def get_standard_rating(val):
    for r in STANDARD_MCCBS:
        if r >= val:
            return r
    return STANDARD_MCCBS[-1]

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Professional Microgrid SLD Generator", layout="wide")

# ---------- UI STYLE (Premium Dark Theme) ----------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #062a30, #020617);
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        color: #c37c5a;
        margin-bottom: 30px;
        text-shadow: 0 0 20px rgba(195, 124, 91, 0.3);
    }
    .section-title {
        font-size: 22px;
        font-weight: 600;
        color: #19988b;
        margin-top: 25px;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(25, 152, 139, 0.2);
        padding-bottom: 5px;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #062a30 !important;
        font-weight: 800 !important;
    }
    [data-testid="stExpander"] summary p,
    .streamlit-expanderHeader p {
        color: #062a30 !important;
        font-weight: 800 !important;
        font-size: 16px !important;
    }
    .stNumberInput label, .stSelectbox label,
    .stNumberInput label p, .stSelectbox label p {
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        opacity: 1 !important;
    }
    .stButton>button, [data-testid="stDownloadButton"]>button {
        background: linear-gradient(90deg, #19988b, #15803d) !important;
        color: white !important;
        border: none !important;
        padding: 12px 30px !important;
        font-size: 16px !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        transition: none !important;
        box-shadow: 0 4px 15px rgba(25, 152, 139, 0.3) !important;
    }
    .stButton>button:hover, .stButton>button:active, .stButton>button:focus,
    [data-testid="stDownloadButton"]>button:hover, [data-testid="stDownloadButton"]>button:active, [data-testid="stDownloadButton"]>button:focus {
        background: linear-gradient(90deg, #19988b, #15803d) !important;
        color: white !important;
        transform: none !important;
        box-shadow: 0 4px 15px rgba(25, 152, 139, 0.3) !important;
    }
    .result-card {
        background: rgba(6, 42, 48, 0.8);
        border: 1px solid rgba(195, 124, 91, 0.3);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 15px;
        backdrop-filter: blur(10px);
    }
    .warning-card {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #fca5a5;
    }
    .info-card {
        background: rgba(25, 152, 139, 0.1);
        border-left: 4px solid #19988b;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #93c5fd;
    }
    /* ── Metrics row styling ── */
    [data-testid="stMetric"] {
        background: rgba(6, 42, 48, 0.8);
        border: 1px solid rgba(195, 124, 91, 0.3);
        border-radius: 12px;
        padding: 16px 20px;
        backdrop-filter: blur(10px);
    }
    [data-testid="stMetricLabel"] p {
        color: #94a3b8 !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        color: #19988b !important;
        font-size: 22px !important;
        font-weight: 800 !important;
    }
</style>
<div class="main-title">Microgrid Panel SLD Generator</div>
""", unsafe_allow_html=True)

# ---------------- INPUTS (Sidebar & Main) ----------------
with st.sidebar:
    st.header("⚙️ Design Parameters")

    with st.expander("Capacity Inputs", expanded=True):
        solar_kw   = st.number_input("Solar (kWp)",    value=100, min_value=0)
        grid_kw    = st.number_input("Grid (kW)",       value=120, min_value=0)
        num_dg     = st.number_input("Number of DGs",   value=2,   min_value=0, max_value=4)
        dg_ratings = []
        if num_dg > 0:
            st.markdown(
                "<div style='font-size:13px;color:#64748b;margin-top:5px;margin-bottom:5px;'>"
                "DG Specifications</div>",
                unsafe_allow_html=True,
            )
            for i in range(int(num_dg)):
                dg = st.number_input(f"DG {i+1} Rating (kVA)", value=250, key=f"dg_in_{i}")
                dg_ratings.append(dg)

        num_outputs = st.number_input("Outgoing Feeders", value=3, min_value=1, max_value=10)
        mccb_outputs = []
        if num_outputs > 0:
            st.markdown(
                "<div style='font-size:13px;color:#64748b;margin-top:5px;margin-bottom:5px;'>"
                "Outgoing Feeder Specifications (Amperes)</div>",
                unsafe_allow_html=True,
            )
            for i in range(int(num_outputs)):
                default_val = 400 if i < 2 else 250
                out_r = st.number_input(
                    f"O/G {i+1} Rating (Amp)", value=default_val, key=f"og_in_{i}", min_value=0
                )
                mccb_outputs.append(get_standard_rating(out_r))

        busbar_material = st.selectbox("Busbar Material", ["Copper", "Aluminium"], index=1)
        num_poles       = st.selectbox("System Phases/Poles", [3, 4], index=1)

    st.divider()
    submit = st.button("Generate Final SLD & BOM", use_container_width=True)

# ---------------- CORE CALCULATIONS ----------------
 
def get_mccb_rating(current):
    required = current * 1.25
    for rating in STANDARD_MCCBS:
        if rating >= required:
            return rating
    return STANDARD_MCCBS[-1]

def get_mccb_dims(rating):
    # Try to find an exact match first, otherwise check nearest standard rating
    return MCCB_DIMENSIONS.get(rating, "")

V  = 415
PF = 0.8

i_solar    = (solar_kw * 1000) / (math.sqrt(3) * V * PF) if solar_kw > 0 else 0
mccb_solar = get_mccb_rating(i_solar) if solar_kw > 0 else 0

i_grid    = (grid_kw * 1000) / (math.sqrt(3) * V * PF) if grid_kw > 0 else 0
mccb_grid = get_mccb_rating(i_grid) if grid_kw > 0 else 0

dg_mccbs    = []
dg_currents = []
for dg in dg_ratings:
    i = (dg * 1000) / (math.sqrt(3) * V)
    dg_currents.append(i)
    dg_mccbs.append(get_mccb_rating(i))

total_busbar_current = i_solar + i_grid + sum(dg_currents)

density     = 1.6 if busbar_material == "Copper" else 1.0
busbar_area = total_busbar_current / density
suggested_width = math.ceil(busbar_area / 10 / 5) * 5
if suggested_width < 20:
    suggested_width = 20
busbar_spec = f"1 Set ({suggested_width} x 20 mm {busbar_material})"

total_outgoing_rating = sum(mccb_outputs)

# ---------------- DRAWING HELPERS (SVG) ----------------

def draw_mccb(dwg, x, y, rating, poles, label, side="left"):
    dwg.add(dwg.line(start=(x, y - 50), end=(x, y - 18), stroke="white", stroke_width=2))
    dwg.add(dwg.line(start=(x, y + 12), end=(x, y + 50), stroke="white", stroke_width=2))
    dwg.add(dwg.path(
        d=f"M{x},{y-18} A14,14 0 0,0 {x+2},{y+12}",
        stroke="#10b981", fill="none", stroke_width=2.5,
    ))
    if side == "left":
        info_x, anchor        = x - 25, "end"
        label_x, label_anchor = x + 35, "start"
    else:
        info_x, anchor        = x + 25, "start"
        label_x, label_anchor = x - 35, "end"
    dwg.add(dwg.text(f"{rating} A, {poles}pole,", insert=(info_x, y - 5),
                     font_size=12, fill="#e2e8f0", text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text("Motorised MCCB",       insert=(info_x, y + 12),
                     font_size=11, fill="#94a3b8", text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text(label,                  insert=(label_x, y + 5),
                     font_size=14, font_weight="bold", fill="#f1f5f9",
                     text_anchor=label_anchor, font_family="Arial"))

def draw_tower(dwg, x, y):
    h = 90
    w = 25
    # Lattice Pylon structure
    # Main legs
    dwg.add(dwg.line((x, y - 5), (x - w, y + h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x, y - 5), (x + w, y + h), stroke="white", stroke_width=2))
    # Base
    dwg.add(dwg.line((x - w, y + h), (x + w, y + h), stroke="white", stroke_width=2))
    # Cross arms (shorter at top, wider at middle)
    arm_y = [y + 15, y + 40, y + 65]
    arm_w = [18, 28, 24]
    for i in range(3):
        dwg.add(dwg.line((x - arm_w[i], arm_y[i]), (x + arm_w[i], arm_y[i]), stroke="white", stroke_width=2))
        # Insulators (small vertical bits at arm ends)
        dwg.add(dwg.line((x - arm_w[i], arm_y[i]), (x - arm_w[i], arm_y[i] + 8), stroke="white", stroke_width=1.2))
        dwg.add(dwg.line((x + arm_w[i], arm_y[i]), (x + arm_w[i], arm_y[i] + 8), stroke="white", stroke_width=1.2))
    # Internal lattice bracing (X-pattern)
    for i in range(len(arm_y) - 1):
        y1, y2 = arm_y[i], arm_y[i+1]
        w1, w2 = arm_w[i], arm_w[i+1]
        dwg.add(dwg.line((x - w1, y1), (x + w2, y2), stroke="white", stroke_width=0.8, stroke_opacity=0.4))
        dwg.add(dwg.line((x + w1, y1), (x - w2, y2), stroke="white", stroke_width=0.8, stroke_opacity=0.4))

def draw_solar(dwg, x, y):
    # Panel in perspective (Trapezoid)
    dwg.add(dwg.path(
        d=f"M{x-20},{y+55} L{x+20},{y+55} L{x+30},{y+20} L{x-30},{y+20} Z",
        fill="#1e293b", stroke="white", stroke_width=2
    ))
    # Grid lines on panel
    for i in range(1, 4):
        h_y = y + 20 + i * (35 / 4)
        dwg.add(dwg.line((x - 30 + i*2.5, h_y), (x + 30 - i*2.5, h_y), stroke="white", stroke_opacity=0.4))
    dwg.add(dwg.line((x, y+20), (x, y+55), stroke="white", stroke_opacity=0.4))
    dwg.add(dwg.line((x-10, y+20), (x-8, y+55), stroke="white", stroke_opacity=0.4))
    dwg.add(dwg.line((x+10, y+20), (x+8, y+55), stroke="white", stroke_opacity=0.4))
    
    # Sun with rays
    cx, cy = x - 25, y - 5
    dwg.add(dwg.circle(center=(cx, cy), r=10, stroke="#fbbf24", fill="none", stroke_width=2.5))
    for i in range(8):
        angle = i * 45
        import math
        r1, r2 = 12, 17
        x1 = cx + r1 * math.cos(math.radians(angle))
        y1 = cy + r1 * math.sin(math.radians(angle))
        x2 = cx + r2 * math.cos(math.radians(angle))
        y2 = cy + r2 * math.sin(math.radians(angle))
        dwg.add(dwg.line((x1, y1), (x2, y2), stroke="#fbbf24", stroke_width=1.5))

def draw_mgc(dwg, x, y):
    size = 100
    # Outer frame
    dwg.add(dwg.rect(insert=(x, y), size=(size, size),
                     fill="#1e1b4b", stroke="#a78bfa", stroke_width=3, rx=8))
    # Inner board
    dwg.add(dwg.rect(insert=(x + 15, y + 15), size=(70, 70),
                     fill="none", stroke="#a78bfa", stroke_width=2))
    
    # 6 Pins on each side
    pin_len = 12
    spacing = size / 7
    for i in range(1, 7):
        pos = i * spacing
        # Top
        dwg.add(dwg.line((x + pos, y - pin_len), (x + pos, y), stroke="#a78bfa", stroke_width=2.5))
        # Bottom
        dwg.add(dwg.line((x + pos, y + size), (x + pos, y + size + pin_len), stroke="#a78bfa", stroke_width=2.5))
        # Left
        dwg.add(dwg.line((x - pin_len, y + pos), (x, y + pos), stroke="#a78bfa", stroke_width=2.5))
        # Right
        dwg.add(dwg.line((x + size, y + pos), (x + size + pin_len, y + pos), stroke="#a78bfa", stroke_width=2.5))

    dwg.add(dwg.text("MGC", insert=(x + size / 2, y + size / 2 + 8),
                     font_size=20, fill="white", font_weight="bold", text_anchor="middle"))

# ── DYNAMIC CANVAS SIZING ─────────────────────────────────────────────────────
def compute_canvas(n_dg, g_kw, s_kw, n_out):
    n_incomers = int(n_dg) + (1 if g_kw > 0 else 0) + (1 if s_kw > 0 else 0)
    n_incomers = max(n_incomers, 1)
    n_out      = max(int(n_out), 1)

    MIN_COL    = 250
    MARGIN_L   = 100
    MARGIN_R   = 120

    width = MARGIN_L + max(n_incomers, n_out + 0.5) * MIN_COL + MARGIN_R
    width = max(width, 950)

    # Distribute columns
    inc_spacing = MIN_COL
    out_spacing = MIN_COL
    return int(width), 950, int(inc_spacing), int(out_spacing), int(MARGIN_L + 60)


# ---------------- MAIN UI LOGIC ----------------
if submit:
    warning_flag = total_busbar_current > total_outgoing_rating

    st.markdown(f"""
    <div class="info-card">
        <strong>📊 Busbar Calculation Summary</strong><br>
        Total Busbar Current: <strong>{total_busbar_current:.2f}A</strong><br>
        Total Outgoing Rating: <strong>{total_outgoing_rating:.0f}A</strong><br>
        Recommended Busbar Size: <strong>{busbar_spec}</strong>
    </div>
    """, unsafe_allow_html=True)

    if warning_flag:
        st.markdown(f"""
        <div class="warning-card">
            <strong>⚠️ WARNING: Insufficient Outgoing Capacity</strong><br>
            Total busbar current (<strong>{total_busbar_current:.2f}A</strong>) exceeds total outgoing
            breaker rating (<strong>{total_outgoing_rating:.0f}A</strong>).<br>
            Please increase outgoing feeder ratings or review your system configuration.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-card">
            ✅ System is properly sized. Outgoing feeders match source capacity.
        </div>
        """, unsafe_allow_html=True)

    # ── 1. GENERATE SLD SVG ──────────────────────────────────────────────────
    def generate_sld():
        # Compute dynamic layout
        width, height, inc_spacing, out_spacing, x_init = compute_canvas(
            num_dg, grid_kw, solar_kw, num_outputs
        )

        dwg = svg.Drawing(size=(width, height), profile="full")
        dwg.viewbox(0, 0, width, height)

        # Background
        dwg.add(dwg.rect((0, 0), (width, height),
                         fill="#020617", stroke="#334155", stroke_width=2, rx=15))

        # Proportional vertical landmarks
        y_division = int(height * 0.40)   # ~380 px at h=950
        y_sources  = int(height * 0.17)   # ~160 px
        y_busbar   = int(height * 0.58)   # ~551 px (Tightened from 0.67)
        dwg.add(dwg.text("Customer Scope",
                         insert=(width / 2, 50),
                         font_size=20, font_weight="bold", fill="#94a3b8", text_anchor="middle"))
        dwg.add(dwg.text("Kirloskar Scope",
                         insert=(50, height - 40),
                         font_size=20, font_weight="bold", fill="#94a3b8"))
        dwg.add(dwg.text("Smart AMF Panel",
                         insert=(width - 220, height - 40),
                         font_size=18, fill="#6366f1"))

        # MGC — anchored to right side
        mgc_x = width - 155
        # Align MGC top-third with the trunk (comm_y = y_division + 25)
        # mgc_pin_y = mgc_y + 42.8  ->  y_div + 25 = mgc_y + 42.8
        mgc_y = y_division - 18
        draw_mgc(dwg, mgc_x, mgc_y)
        dwg.add(dwg.text("Auto / Manual",
                         insert=(mgc_x + 50, mgc_y - 15),
                         font_size=13, fill="#cbd5e1", text_anchor="middle"))

        current_x    = x_init
        active_ics_x = []
        ic_index     = 1

        # ── DGs ──────────────────────────────────────────────────────────────
        for i in range(int(num_dg)):
            cx = current_x
            dwg.add(dwg.text(f"{dg_ratings[i]} kVA",
                             insert=(cx, y_sources - 85),
                             font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            dwg.add(dwg.circle(center=(cx, y_sources), r=45,
                               stroke="#60a5fa", fill="none", stroke_width=2.5))
            dwg.add(dwg.text(f"DG {i+1}",
                             insert=(cx, y_sources + 7),
                             font_size=15, fill="white", text_anchor="middle"))
            # wire → MCCB → busbar
            dwg.add(dwg.line((cx, y_sources + 45), (cx, y_division + 50),
                             stroke="white", stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, dg_mccbs[i], num_poles, f"I/C {ic_index}", "left")
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar),
                             stroke="white", stroke_width=2))

            active_ics_x.append(cx)
            current_x += inc_spacing
            ic_index  += 1

        # ── Grid ─────────────────────────────────────────────────────────────
        if grid_kw > 0:
            cx = current_x
            dwg.add(dwg.text(f"{grid_kw} kW",
                             insert=(cx, y_sources - 85),
                             font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            draw_tower(dwg, cx, y_sources - 30)
            dwg.add(dwg.line((cx, y_sources + 30), (cx, y_division + 50),
                             stroke="white", stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, mccb_grid, num_poles, f"I/C {ic_index}", "left")
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar),
                             stroke="white", stroke_width=2))
            active_ics_x.append(cx)
            current_x += inc_spacing
            ic_index  += 1

        # ── Solar ─────────────────────────────────────────────────────────────
        if solar_kw > 0:
            cx = current_x
            dwg.add(dwg.text(f"{solar_kw} kWp",
                             insert=(cx, y_sources - 85),
                             font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            draw_solar(dwg, cx, y_sources - 30)
            dwg.add(dwg.line((cx, y_sources + 25), (cx, y_division + 50),
                             stroke="white", stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, mccb_solar, num_poles, f"I/C {ic_index}", "left")
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar),
                             stroke="white", stroke_width=2))
            active_ics_x.append(cx)

        # ── Main Busbar with Pole Hashing ─────────────────────────────────────
        dwg.add(dwg.line((40, y_busbar), (width - 40, y_busbar),
                         stroke="#ef4444", stroke_width=7))
        
        # Diagonal Hashing lines for poles (instead of 'MAIN BUSBAR' text)
        hash_start_x = 60
        for p in range(int(num_poles)):
            # Draw a diagonal line crossing the busbar
            dwg.add(dwg.line((hash_start_x + p*7, y_busbar + 12), 
                             (hash_start_x + p*7 + 8, y_busbar - 12),
                             stroke="white", stroke_width=1.5))
        
        dwg.add(dwg.text(f"{total_busbar_current:.1f}A",
                         insert=(width - 50, y_busbar - 12),
                         font_size=13, fill="#f87171", text_anchor="end"))

        # ── Communication Line Trunks & Branches ───────────────────────────────
        if active_ics_x:
            # Trunk inside Kirloskar scope, above I/C MCCBs
            comm_y = y_division + 25
            # Top trunk (dashed line for communication)
            dwg.add(dwg.line((active_ics_x[0], comm_y), (mgc_x - 12, comm_y),
                             stroke="#a78bfa", stroke_width=1.2, stroke_dasharray="6,3"))
            # Vertical drops from each incomer source to the comm trunk
            for ax in active_ics_x:
                dwg.add(dwg.line((ax, comm_y), (ax, y_division + 50),
                                 stroke="#a78bfa", stroke_width=1, stroke_dasharray="4,2"))
            
            # Bottom trunk
            n_out       = int(num_outputs)
            x_out_start = x_init + (inc_spacing / 2)
            mgc_pin_x   = mgc_x + (3 * (100 / 7))
            comm_y_bottom = y_busbar + 160
            
            dwg.add(dwg.line((x_out_start, comm_y_bottom), (mgc_pin_x, comm_y_bottom),
                             stroke="#a78bfa", stroke_width=1.2, stroke_dasharray="6,3"))
            dwg.add(dwg.line((mgc_pin_x, mgc_y + 112), (mgc_pin_x, comm_y_bottom),
                             stroke="#a78bfa", stroke_width=1.2, stroke_dasharray="6,3"))
            # Vertical branches for outgoers
            for i in range(n_out):
                ox = x_out_start + i * inc_spacing
                if ox > (mgc_x - 50): break
                dwg.add(dwg.line((ox, comm_y_bottom), (ox, y_busbar + 125),
                                 stroke="#a78bfa", stroke_width=1, stroke_dasharray="4,2"))

        # ── Outgoing Feeders — Interlaced between Incomer columns ─────────────
        n_out       = int(num_outputs)
        x_out_start = x_init + (inc_spacing / 2)
        
        for i in range(n_out):
            ox = x_out_start + i * inc_spacing
            # Safety break to avoid drawing over MGC
            if ox > (mgc_x - 50):
                break
            rating = mccb_outputs[i] if i < len(mccb_outputs) else 250
            dwg.add(dwg.line((ox, y_busbar),       (ox, y_busbar + 25),  stroke="white", stroke_width=2))
            draw_mccb(dwg, ox, y_busbar + 75, rating, num_poles, f"O/G {i+1}", "right")
            dwg.add(dwg.line((ox, y_busbar + 125), (ox, height - 80),    stroke="white", stroke_width=2))

        # --- FINAL PASS: Communication Labels (Draw on top of power lines to mask them) ---
        if active_ics_x:
            label_text = "Communication and Control Lines"
            comm_y = y_division + 25
            comm_y_bottom = y_busbar + 160
            
            # Top Label mask
            dwg.add(dwg.rect(insert=(width / 2 - 120, comm_y - 12), size=(240, 24),
                             fill="#020617", stroke="none"))
            dwg.add(dwg.text(label_text, insert=(width / 2, comm_y + 6),
                             font_size=13, fill="#c4b5fd", text_anchor="middle"))
            
            # Bottom Label mask
            dwg.add(dwg.rect(insert=(width / 2 - 120, comm_y_bottom - 12), size=(240, 24),
                             fill="#020617", stroke="none"))
            dwg.add(dwg.text(label_text, insert=(width / 2, comm_y_bottom + 6),
                             font_size=13, fill="#c4b5fd", text_anchor="middle"))

        return dwg.tostring(), width, height

    # ── 2. RENDER SLD ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📋 Professional Single Line Diagram</div>',
                unsafe_allow_html=True)
    sld_svg, svg_width, svg_height = generate_sld()
    b64 = base64.b64encode(sld_svg.encode("utf-8")).decode("utf-8")
    st.markdown(
        f'<div style="background:#020617;padding:20px;border-radius:15px;border:1px solid #334155;margin-bottom:35px;">'
        f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;"></div>',
        unsafe_allow_html=True,
    )

    # ---------------- PDF UTILITIES ----------------
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            """Add page info to each page (Page X of Y)"""
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_footer(num_pages)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def draw_footer(self, page_count):
            self.saveState()
            
            # --- 1. Top Right Logo ---
            logo_path = "Kirloskar Oil Engine Logo.png"
            logo_w, logo_h = 100, 35
            # Position at top right corner, high enough to avoid heading overlap
            self.drawImage(logo_path, A4[0] - 45 - logo_w, A4[1] - 30 - logo_h, 
                           width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')

            # --- 2. Footer Styling ---
            self.setFont("Helvetica", 8)
            self.setStrokeColor(colors.HexColor("#cbd5e1")) 
            self.setLineWidth(0.5)
            # Horizontal line above footer
            self.line(45, 50, A4[0] - 45, 50)
            
            # Footer Text
            self.setFillColor(colors.HexColor("#475569"))
            # Left: Company Name
            self.drawString(45, 35, "Kirloskar Oil Engines Ltd.")
            
            # Center: Dynamic Date and Time
            now = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
            self.drawCentredString(A4[0]/2.0, 35, f"Report Generated: {now}")
            
            # Right: Page number (Page X of Y)
            page_num = self.getPageNumber()
            self.drawRightString(A4[0] - 45, 35, f"Page {page_num} of {page_count}")
            
            self.restoreState()

    # ── 3. PDF BOM GENERATOR ─────────────────────────────────────────────────
    def generate_pdf_report():
        buffer = io.BytesIO()
        # Increased topMargin to 80 to prevent overlap with the logo
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=45, leftMargin=45,
                                topMargin=80, bottomMargin=45)
        styles = getSampleStyleSheet()

        title_style            = styles["Title"]
        title_style.fontSize   = 22
        title_style.textColor  = colors.HexColor("#c37c5a")
        title_style.alignment  = 1

        h2_style             = styles["Heading2"]
        h2_style.fontSize    = 16
        h2_style.textColor   = colors.HexColor("#19988b")
        h2_style.spaceBefore = 12
        h2_style.spaceAfter  = 8

        normal_style           = styles["Normal"]
        normal_style.fontSize  = 10
        normal_style.leading   = 13
        normal_style.alignment = 4

        story = []

        # Page 1 – System Overview & SLD
        story.append(Paragraph("Microgrid Panel Technical Report", title_style))
        story.append(Spacer(1, 15))

        story.append(Paragraph("1. System Overview", h2_style))
        grid_text  = f"<b>{grid_kw} kW</b> Grid supply, " if grid_kw > 0 else ""
        solar_text = f"and <b>{solar_kw} kWp</b> Solar PV" if solar_kw > 0 else ""
        description = (
            f"This report details the configuration and material requirements for a customized "
            f"Microgrid Panel. The system handles <b>{int(num_dg)} DG(s)</b>, "
            f"{grid_text}{solar_text}. "
            f"Managed via a centralized Microgrid Controller (MGC) for seamless power source management."
        )
        story.append(Paragraph(description, normal_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("2. System Specifications", h2_style))
        specs_text = (
            f"<b>Total Busbar Current Rating:</b> {total_busbar_current:.2f}A<br/>"
            f"<b>Total Outgoing Capacity:</b> {total_outgoing_rating:.0f}A<br/>"
            f"<b>Recommended Busbar:</b> {busbar_spec}<br/>"
            f"<b>System Configuration:</b> {int(num_poles)}-Phase, {int(num_outputs)} Outgoing Feeders<br/>"
            
        )
        if warning_flag:
            specs_text += (
                "<br/><font color='red'><b>WARNING:</b> Total busbar current exceeds total outgoing "
                "rating. Please review system configuration.</font>"
            )
        story.append(Paragraph(specs_text, normal_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("3. Single Line Diagram (SLD)", h2_style))
        with open("temp_sld.svg", "w", encoding="utf-8") as f:
            f.write(sld_svg)

        try:
            drawing        = svg2rlg("temp_sld.svg")
            drawing.width  = svg_width
            drawing.height = svg_height
            scale          = 505.0 / svg_width   # fit to A4 printable width
            drawing.scale(scale, scale)
            drawing.width  = svg_width  * scale
            drawing.height = svg_height * scale
            sld_table = Table([[drawing]], colWidths=[505])
            sld_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(sld_table)
        except Exception as e:
            story.append(Paragraph(f"[Error rendering SLD: {str(e)}]", normal_style))

        story.append(Spacer(1, 20))
        story.append(Paragraph(
            "<i>Note: The diagram above illustrates the electrical topology and power flow "
            "between sources and outgoing feeders.</i>", normal_style))

        story.append(PageBreak())

        # Page 2 – Bill of Materials
        story.append(Paragraph("4. Bill Of Material (BOM)", h2_style))
        story.append(Spacer(1, 8))

        # BOM Data Construction
        bom_items = []
        if solar_kw > 0:
            bom_items.append({"desc": "Solar Incomer MCCB", "rating": f"{mccb_solar}A", "poles": f"{num_poles}P", "qty": "1", "uom": "Nos"})
        if grid_kw > 0:
            bom_items.append({"desc": "Grid Incomer MCCB", "rating": f"{mccb_grid}A", "poles": f"{num_poles}P", "qty": "1", "uom": "Nos"})
        
        # Group DGs if they have same rating
        if num_dg > 0:
            from collections import Counter
            dg_counts = Counter(dg_mccbs)
            for r, count in dg_counts.items():
                label = "DG Incomer MCCB" if len(dg_counts) == 1 else f"DG Incomer MCCB ({r}A)"
                bom_items.append({"desc": label, "rating": f"{r}A", "poles": f"{num_poles}P", "qty": str(count), "uom": "Nos"})
        
        # Group Feeders
        if num_outputs > 0:
            from collections import Counter
            out_counts = Counter(mccb_outputs)
            for r, count in out_counts.items():
                bom_items.append({"desc": f"Outgoing Feeder MCCB ({int(r)}A)", "rating": f"{int(r)}A", "poles": f"{num_poles}P", "qty": str(count), "uom": "Nos"})

        # Busbar and MGC
        bom_items.append({"desc": f"{busbar_material} Main Busbar", "rating": f"{total_busbar_current:.1f}A Rated", "poles": "-", "qty": busbar_spec, "uom": "-"})
        bom_items.append({"desc": "Microgrid Controller (MGC)", "rating": "Standard", "poles": "-", "qty": "1", "uom": "Nos"})

        # Cables and Enclosure (Moved below MGC)
        bom_items.append({"desc": "Control Cable", "rating": "1.5 sqmm", "poles": "-", "qty": "100", "uom": "Meters"})
        bom_items.append({"desc": "Power/Consumable Cable", "rating": "Varied", "poles": "-", "qty": "50", "uom": "Meters"})
        bom_items.append({"desc": "Enclosure (Panel Body)", "rating": "Standard IP54", "poles": "-", "qty": "1", "uom": "Set"})

        table_data = [["Sr No", "Component / Description", "Rating", "Poles", "Qty", "UOM"]]
        for i, item in enumerate(bom_items):
            table_data.append([str(i+1), item["desc"], item["rating"], item["poles"], item["qty"], item["uom"]])

        # Adjusted column widths for 6 columns to fit the long Busbar Qty string: SrNo(30), Desc(160), Rating(75), Poles(40), Qty(150), UOM(50)
        table = Table(table_data, colWidths=[30, 160, 75, 40, 150, 50])
        table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#19988b")),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.whitesmoke),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  10),
            ("BACKGROUND",    (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("5. Notes & Remarks", h2_style))
        notes = (
            "• This Bill of Materials is subject to final design review and customer requirements.<br/>"
            "• All MCCB ratings include a 1.25x safety factor as per standard practice.<br/>"
            "• Busbar sizing considers thermal conductivity and current density limits.<br/>"
            "• The MGC provides automatic/manual source selection and switchover capability.<br/>"
            "• All components are to be sourced and installed as per relevant Indian Standards and IEC guidelines."
        )
        story.append(Paragraph(notes, normal_style))

        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer

    pdf_buffer = generate_pdf_report()
    
    # ── 3.5 EXCEL BOM GENERATOR ──────────────────────────────────────────────
    def generate_excel_bom():
        bom_items = []
        if solar_kw > 0:
            bom_items.append({"Description": "Solar Incomer MCCB", "Rating": f"{mccb_solar}A", "Poles": f"{num_poles}P", "Qty": 1, "UOM": "Nos"})
        if grid_kw > 0:
            bom_items.append({"Description": "Grid Incomer MCCB", "Rating": f"{mccb_grid}A", "Poles": f"{num_poles}P", "Qty": 1, "UOM": "Nos"})
        
        if num_dg > 0:
            from collections import Counter
            dg_counts = Counter(dg_mccbs)
            for r, count in dg_counts.items():
                label = "DG Incomer MCCB" if len(dg_counts) == 1 else f"DG Incomer MCCB ({r}A)"
                bom_items.append({"Description": label, "Rating": f"{r}A", "Poles": f"{num_poles}P", "Qty": count, "UOM": "Nos"})
        
        if num_outputs > 0:
            from collections import Counter
            out_counts = Counter(mccb_outputs)
            for r, count in out_counts.items():
                bom_items.append({"Description": f"Outgoing Feeder MCCB ({int(r)}A)", "Rating": f"{int(r)}A", "Poles": f"{num_poles}P", "Qty": count, "UOM": "Nos"})

        bom_items.append({"Description": f"{busbar_material} Main Busbar", "Rating": f"{total_busbar_current:.1f}A Rated", "Poles": "-", "Qty": busbar_spec, "UOM": "-"})
        bom_items.append({"Description": "Microgrid Controller (MGC)", "Rating": "Standard", "Poles": "-", "Qty": 1, "UOM": "Nos"})

        # Cables and Enclosure (Moved below MGC)
        bom_items.append({"Description": "Control Cable", "Rating": "1.5 sqmm", "Poles": "-", "Qty": 100, "UOM": "Meters"})
        bom_items.append({"Description": "Power/Consumable Cable", "Rating": "Varied", "Poles": "-", "Qty": 50, "UOM": "Meters"})
        bom_items.append({"Description": "Enclosure (Panel Body)", "Rating": "Standard IP54", "Poles": "-", "Qty": 1, "UOM": "Set"})

        df = pd.DataFrame(bom_items)
        df.insert(0, "Sr No", range(1, len(df) + 1))
        
        # Add Dimensions column mapping based on rating
        def map_dims(row):
            if "MCCB" in row["Description"]:
                try:
                    r_val = int(''.join(filter(str.isdigit, row["Rating"])))
                    return get_mccb_dims(r_val)
                except: return ""
            return ""
        
        df["Dimensions (mm)"] = df.apply(map_dims, axis=1)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="BOM")
        return output.getvalue()

    excel_data = generate_excel_bom()

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📄 Download Technical Report (PDF)",
            data=pdf_buffer,
            file_name="Microgrid_Panel_Technical_Report.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with col_dl2:
        st.download_button(
            label="📊 Download BOM (Excel)",
            data=excel_data,
            file_name="Microgrid_Panel_BOM.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # ── 4. Summary metrics ────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Busbar Current",  f"{total_busbar_current:.2f}A")
    with col2:
        st.metric("Total Outgoing Rating", f"{total_outgoing_rating:.0f}A")
    with col3:
        st.metric("System Voltage",        "415V, 3Φ")
    with col4:
        st.metric("Busbar Size",           busbar_spec)
    with col5:
        st.metric("Canvas Size",           f"{svg_width} × {svg_height} px")