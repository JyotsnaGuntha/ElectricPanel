"""
GA Drawing Generator
Main General Arrangement drawing generation logic.
"""

import math
import datetime
import svgwrite as svg
from .dimensions import compute_panel_dimensions
from .styles import get_ga_colors
from ..constants import (
    PLINTH_H,
    CLEARANCE_PP,
    CLEARANCE_PE,
    MCCB_COL_GAP,
    ROW_GAP_MM,
    SIDE_MARGIN,
    TOP_MARGIN_H,
    GA_SVG_WIDTH,
    GA_SVG_HEIGHT,
    GA_LEFT_MARGIN,
    GA_FRONT_MAX_W,
    GA_ELEV_GAP,
    GA_SIDE_MAX_W,
    GA_BOTTOM_STRIP,
)
from ..utils import get_mccb_dims, get_busbar_thickness


def generate_ga_svg(
    incomer_mccbs,
    outgoing_mccbs,
    busbar_current,
    busbar_spec_text,
    num_poles_val,
    busbar_material,
    mccb_db,
    theme="dark",
    include_spec_box=True,
):
    """
    Generate GA drawing as SVG string.
    
    Engineering GA drawing (clean shell, dimension arrows, spec box).
    Panel geometry computed entirely from:
      - MCCB dimensions read from Excel (mccb_db)
      - Busbar chamber height per IEC 61439
      - Standard clearance/margin constants
    
    Args:
        incomer_mccbs: List of incomer MCCB ratings
        outgoing_mccbs: List of outgoing MCCB ratings
        busbar_current: Total busbar current (A)
        busbar_spec_text: Busbar specification string
        num_poles_val: 3 or 4
        busbar_material: "Copper" or "Aluminium"
        mccb_db: MCCB dimensions database
        theme: "dark" or "light"
        include_spec_box: include right-side GA specification table
    
    Returns:
        (svg_string, svg_width, svg_height, panel_w_mm, panel_h_mm, panel_d_mm)
    """
    # ────────────────────────────────────────────────────────────────────────
    # 1. Compute all real-world mm dimensions
    # ────────────────────────────────────────────────────────────────────────
    pd_info = compute_panel_dimensions(incomer_mccbs, outgoing_mccbs, mccb_db, busbar_current)
    PANEL_W = pd_info["PANEL_W"]
    PANEL_H = pd_info["PANEL_H"]
    PANEL_D_ = pd_info["PANEL_D"]
    MOUNT_W = pd_info["MOUNT_W"]
    MOUNT_H = pd_info["MOUNT_H"]
    BUSBAR_CH = pd_info["BUSBAR_CH_MM"]
    MAX_INC_H = pd_info["MAX_INC_H"]
    MAX_OUT_H = pd_info["MAX_OUT_H"]
    OUT_ROWS = pd_info["OUT_ROWS"]
    busbar_thick = get_busbar_thickness(busbar_current)

    # Mounting-plate internal zones (all in mm, top-to-bottom)
    zone_top_margin = TOP_MARGIN_H
    zone_incomer = MAX_INC_H
    zone_gap1 = ROW_GAP_MM
    zone_busbar = BUSBAR_CH
    zone_gap2 = ROW_GAP_MM
    zone_outgoing = OUT_ROWS * (MAX_OUT_H + ROW_GAP_MM)
    zone_cable_duct = GA_BOTTOM_STRIP  # Use constant for cable duct

    # ────────────────────────────────────────────────────────────────────────
    # 2. SVG canvas & scale factors
    # ────────────────────────────────────────────────────────────────────────
    SVG_W = GA_SVG_WIDTH
    SVG_H = GA_SVG_HEIGHT

    # Scale: fit front view into FRONT_MAX_W × (SVG_H – top/bottom space)
    AVAIL_H = SVG_H - 100 - GA_BOTTOM_STRIP
    front_max_w = GA_FRONT_MAX_W
    if not include_spec_box:
        front_max_w = SVG_W - GA_LEFT_MARGIN - GA_ELEV_GAP - GA_SIDE_MAX_W - 20
    SCALE = min(front_max_w / PANEL_W, AVAIL_H / (PANEL_H + PLINTH_H))
    # Side uses same vertical scale but independent horizontal scale
    SCALE_S = min(GA_SIDE_MAX_W / PANEL_D_, SCALE)

    def mm(val):
        return val * SCALE

    def mm_s(val):
        return val * SCALE_S

    pF_W = mm(PANEL_W)
    pF_H = mm(PANEL_H)
    pF_PL = mm(PLINTH_H)
    pF_D = mm_s(PANEL_D_)

    mF_W = mm(MOUNT_W)
    mF_H = mm(MOUNT_H)

    # Zone heights in pixels (front view)
    z_top = mm(zone_top_margin)
    z_inc = mm(zone_incomer)
    z_gap1 = mm(zone_gap1)
    z_bb = mm(zone_busbar)
    z_gap2 = mm(zone_gap2)
    z_out = mm(zone_outgoing)
    z_cd = mm(zone_cable_duct)

    # Positioning
    TOP_Y = 90
    if include_spec_box:
        FRONT_X = GA_LEFT_MARGIN
    else:
        FRONT_X = max(10, (SVG_W - (pF_W + GA_ELEV_GAP + pF_D)) / 2)
    # Keep enough clearance for BB/I/C dimension annotations in preview mode.
    SIDE_GAP = GA_ELEV_GAP if include_spec_box else 72
    SIDE_X = FRONT_X + pF_W + SIDE_GAP

    # Mounting plate top-left inside front view
    mp_x = FRONT_X + (pF_W - mF_W) / 2
    mp_y = TOP_Y + (pF_H - mF_H) / 2

    # ────────────────────────────────────────────────────────────────────────
    # 3. Colors (Responsive to Theme)
    # ────────────────────────────────────────────────────────────────────────
    C = get_ga_colors(theme)
    BG = C["bg"]
    SHELL = C["shell"]
    STROKE = C["stroke"]
    DIM_C = C["dim"]
    TEXT_C = C["text"]
    HATCH_C = C["hatch"]
    MP_C = C["mounting_plate"]
    BB_C = C["busbar"]
    BB_ST = C["busbar_stroke"]
    ZONE_ST = C["zone_separator"]
    SPEC_BG = C["spec_bg"]
    SPEC_BD = C["spec_border"]
    HEAD_C = C["header"]
    SUB_C = C["sub"]
    GRID_C = C["grid"]
    is_dark_theme = theme == "dark"
    BASE_PLINTH = "#08121f" if is_dark_theme else "#e5e7eb"
    PANEL_GUIDE = "#2563eb" if is_dark_theme else "#94a3b8"
    PLATE_STROKE = "#3b82f6" if is_dark_theme else "#94a3b8"
    HMI_BG = "#0a1a2e" if is_dark_theme else "#f8fafc"
    HMI_TXT = "#60a5fa" if is_dark_theme else "#334155"
    SPEC_HEADER_BG = "#0d3a4a" if is_dark_theme else "#e6f4f3"
    SPEC_GRID = "#1e3a5f" if is_dark_theme else "#cbd5e1"
    TITLE_STRIP_BG = "#060d1a" if is_dark_theme else "#e2e8f0"

    # ────────────────────────────────────────────────────────────────────────
    # 4. Create SVG
    # ────────────────────────────────────────────────────────────────────────
    dwg = svg.Drawing(size=(SVG_W, SVG_H), profile="full")
    dwg.viewbox(0, 0, SVG_W, SVG_H)
    dwg.add(dwg.rect((0, 0), (SVG_W, SVG_H), fill=BG))

    # ────────────────────────────────────────────────────────────────────────
    # 5. Helper functions
    # ────────────────────────────────────────────────────────────────────────
    def arr_h(x1, x2, y, label, above=True):
        """Horizontal dim arrow with ticked ends."""
        sign = -1 if above else 1
        lbl_y = y + sign * 14
        dwg.add(dwg.line((x1, y), (x2, y), stroke=DIM_C, stroke_width=1.3))
        for (tx, flip) in [(x1, 1), (x2, -1)]:
            dwg.add(dwg.line((tx, y - 5), (tx, y + 5), stroke=DIM_C, stroke_width=1.3))
            dwg.add(dwg.polygon([(tx, y), (tx + flip * 10, y - 4), (tx + flip * 10, y + 4)], fill=DIM_C))
        dwg.add(dwg.text(label, insert=((x1 + x2) / 2, lbl_y),
                         font_size=11, fill=DIM_C, text_anchor="middle",
                         font_family="Arial", font_weight="bold"))

    def arr_v(x, y1, y2, label, right=True):
        """Vertical dim arrow with ticked ends + rotated label."""
        sign = 1 if right else -1
        lbl_x = x + sign * 18
        mid_y = (y1 + y2) / 2
        dwg.add(dwg.line((x, y1), (x, y2), stroke=DIM_C, stroke_width=1.3))
        for (ty, flip) in [(y1, 1), (y2, -1)]:
            dwg.add(dwg.line((x - 5, ty), (x + 5, ty), stroke=DIM_C, stroke_width=1.3))
            dwg.add(dwg.polygon([(x, ty), (x - 4, ty + flip * 10), (x + 4, ty + flip * 10)], fill=DIM_C))
        g = dwg.g(transform=f"rotate(-90,{lbl_x},{mid_y})")
        g.add(dwg.text(label, insert=(lbl_x, mid_y + 4),
                       font_size=11, fill=DIM_C, text_anchor="middle",
                       font_family="Arial", font_weight="bold"))
        dwg.add(g)

    def ext_h(x, y_from, y_to):
        """Horizontal witness/extension line (dashed, vertical)."""
        dwg.add(dwg.line((x, y_from), (x, y_to),
                         stroke=DIM_C, stroke_width=0.6, stroke_dasharray="4,3"))

    def ext_v(y, x_from, x_to):
        """Vertical witness line (dashed, horizontal)."""
        dwg.add(dwg.line((x_from, y), (x_to, y),
                         stroke=DIM_C, stroke_width=0.6, stroke_dasharray="4,3"))

    def hatch(rx, ry, rw, rh, step=10):
        """Diagonal hatch fill clipped to rect."""
        cid = f"cl_{int(rx)}_{int(ry)}_{int(rw)}"
        clip = dwg.defs.add(dwg.clipPath(id=cid))
        clip.add(dwg.rect(insert=(rx, ry), size=(rw, rh)))
        g = dwg.g(clip_path=f"url(#{cid})")
        span = rw + rh
        for d in range(-int(span), int(span), step):
            g.add(dwg.line((rx + d, ry), (rx + d + rh, ry + rh),
                           stroke=HATCH_C, stroke_width=0.7, stroke_opacity="0.4"))
        dwg.add(g)

    def zone_label(label, x, y, w, h, fill=TEXT_C, fs=9):
        """Centred text in a zone."""
        dwg.add(dwg.text(label, insert=(x + w / 2, y + h / 2 + fs / 3),
                         font_size=fs, fill=fill, text_anchor="middle",
                         font_family="Arial", font_style="italic"))

    # ────────────────────────────────────────────────────────────────────────
    # 6. Grid columns
    # ────────────────────────────────────────────────────────────────────────
    n_cols = max(len(incomer_mccbs), len(outgoing_mccbs), 4)
    col_px = pF_W / n_cols
    for i in range(n_cols + 1):
        gx = FRONT_X + i * col_px
        dwg.add(dwg.line((gx, TOP_Y - 28), (gx, TOP_Y + pF_H + pF_PL + 8),
                         stroke=GRID_C, stroke_width=0.4, stroke_dasharray="3,5"))
    for i in range(n_cols):
        gx = FRONT_X + (i + 0.5) * col_px
        dwg.add(dwg.text(str(i), insert=(gx, TOP_Y - 32),
                         font_size=9, fill=SUB_C, text_anchor="middle", font_family="Arial"))

    # ────────────────────────────────────────────────────────────────────────
    # 7. FRONT ELEVATION — outer shell + plinth
    # ────────────────────────────────────────────────────────────────────────
    plinth_y = TOP_Y + pF_H
    dwg.add(dwg.rect(insert=(FRONT_X, plinth_y), size=(pF_W, pF_PL),
                     fill=BASE_PLINTH, stroke=STROKE, stroke_width=1.5))
    hatch(FRONT_X, plinth_y, pF_W, pF_PL, step=12)
    dwg.add(dwg.rect(insert=(FRONT_X, TOP_Y), size=(pF_W, pF_H),
                     fill=SHELL, stroke=STROKE, stroke_width=2.5))
    bz = 10
    dwg.add(dwg.rect(insert=(FRONT_X + bz, TOP_Y + bz), size=(pF_W - 2 * bz, pF_H - 2 * bz),
                     fill="none", stroke=PANEL_GUIDE, stroke_width=0.9, stroke_dasharray="8,5"))

    # Mounting plate outline (dashed, no content inside)
    dwg.add(dwg.rect(insert=(mp_x, mp_y), size=(mF_W, mF_H),
                     fill=MP_C, stroke=PLATE_STROKE, stroke_width=1.1, stroke_dasharray="6,4"))

    # ── Internal zone dividers
    cur_y = mp_y

    # Zone 1: top margin
    cur_y += z_top
    # Zone 2: incomer row
    inc_top = cur_y
    cur_y += z_inc
    inc_bot = cur_y
    dwg.add(dwg.line((mp_x + 5, inc_bot), (mp_x + mF_W - 5, inc_bot),
                     stroke=ZONE_ST, stroke_width=0.7, stroke_dasharray="5,3"))

    cur_y += z_gap1
    # Zone 3: busbar chamber
    bb_bot = cur_y + z_bb
    cur_y = bb_bot
    cur_y += z_gap2

    # Zone 4: outgoing row(s)
    out_top = cur_y
    cur_y += z_out
    out_bot = cur_y
    dwg.add(dwg.line((mp_x + 5, out_bot), (mp_x + mF_W - 5, out_bot),
                     stroke=ZONE_ST, stroke_width=0.7, stroke_dasharray="5,3"))

    # Zone 5: cable duct — hatched
    duct_y = out_bot
    hatch(mp_x + 5, duct_y, mF_W - 10, z_cd, step=8)
    dwg.add(dwg.rect(insert=(mp_x + 5, duct_y), size=(mF_W - 10, z_cd),
                     fill="none", stroke=ZONE_ST, stroke_width=0.7, stroke_dasharray="5,3"))
    zone_label("Cable Duct / Gland Plate", mp_x, duct_y, mF_W, z_cd, fill=SUB_C, fs=9)

    # Large HMI / Display (Centered with margins)
    hmi_m = 35
    hmi_x = FRONT_X + pF_W / 2 + hmi_m
    hmi_w = (pF_W / 2 - bz) - 2 * hmi_m
    hmi_y = TOP_Y + bz + hmi_m
    hmi_h = inc_bot - hmi_y - hmi_m

    dwg.add(dwg.rect(insert=(hmi_x, hmi_y), size=(hmi_w, hmi_h),
                     fill=HMI_BG, stroke=PLATE_STROKE, stroke_width=1.8, rx=8))
    dwg.add(dwg.text("HMI / DISPLAY",
                     insert=(hmi_x + hmi_w / 2, hmi_y + hmi_h / 2 + 6),
                     font_size=13, fill=HMI_TXT, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))

    # Labels
    dwg.add(dwg.text("FRONT ELEVATION",
                     insert=(FRONT_X + pF_W / 2, TOP_Y + pF_H + pF_PL + 20),
                     font_size=12, fill=TEXT_C, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))

    # ────────────────────────────────────────────────────────────────────────
    # 8. SIDE ELEVATION
    # ────────────────────────────────────────────────────────────────────────
    dwg.add(dwg.rect(insert=(SIDE_X, plinth_y), size=(pF_D, pF_PL),
                     fill=BASE_PLINTH, stroke=STROKE, stroke_width=1.5))
    hatch(SIDE_X, plinth_y, pF_D, pF_PL, step=12)
    dwg.add(dwg.rect(insert=(SIDE_X, TOP_Y), size=(pF_D, pF_H),
                     fill=SHELL, stroke=STROKE, stroke_width=2.5))
    dwg.add(dwg.rect(insert=(SIDE_X + bz, TOP_Y + bz), size=(pF_D - 2 * bz, pF_H - 2 * bz),
                     fill="none", stroke=PANEL_GUIDE, stroke_width=0.9, stroke_dasharray="8,5"))
    dwg.add(dwg.text("SIDE ELEVATION",
                     insert=(SIDE_X + pF_D / 2, TOP_Y + pF_H + pF_PL + 20),
                     font_size=12, fill=TEXT_C, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))

    # ────────────────────────────────────────────────────────────────────────
    # 9. Dimension arrows
    # ────────────────────────────────────────────────────────────────────────
    dim_y_top = TOP_Y - 44
    ext_h(FRONT_X, TOP_Y - 5, dim_y_top + 2)
    ext_h(FRONT_X + pF_W, TOP_Y - 5, dim_y_top + 2)
    arr_h(FRONT_X, FRONT_X + pF_W, dim_y_top, f"{PANEL_W} mm")

    dim_x_H = FRONT_X - 60
    ext_v(TOP_Y, FRONT_X - 5, dim_x_H + 2)
    ext_v(TOP_Y + pF_H, FRONT_X - 5, dim_x_H + 2)
    arr_v(dim_x_H, TOP_Y, TOP_Y + pF_H, f"{PANEL_H} mm", right=False)

    dim_x_PL = FRONT_X - 35
    ext_v(TOP_Y + pF_H, FRONT_X - 5, dim_x_PL + 2)
    ext_v(TOP_Y + pF_H + pF_PL, FRONT_X - 5, dim_x_PL + 2)
    arr_v(dim_x_PL, TOP_Y + pF_H, TOP_Y + pF_H + pF_PL, f"{PLINTH_H} mm", right=False)

    ext_h(SIDE_X, TOP_Y - 5, dim_y_top + 2)
    ext_h(SIDE_X + pF_D, TOP_Y - 5, dim_y_top + 2)
    arr_h(SIDE_X, SIDE_X + pF_D, dim_y_top, f"{PANEL_D_} mm")

    mp_dim_y = mp_y + mF_H + 18
    if mp_dim_y < TOP_Y + pF_H - 10:
        ext_h(mp_x, mp_y + mF_H + 3, mp_dim_y + 2)
        ext_h(mp_x + mF_W, mp_y + mF_H + 3, mp_dim_y + 2)
        arr_h(mp_x, mp_x + mF_W, mp_dim_y, f"MP: {MOUNT_W} mm", above=False)

    mp_dim_x = mp_x + mF_W + 30
    if mp_dim_x < FRONT_X + pF_W - 5:
        ext_v(mp_y, mp_x + mF_W + 3, mp_dim_x - 2)
        ext_v(mp_y + mF_H, mp_x + mF_W + 3, mp_dim_x - 2)
        arr_v(mp_dim_x, mp_y, mp_y + mF_H, f"MP: {MOUNT_H} mm", right=True)

    inc_dim_x = FRONT_X + pF_W + 32
    ext_v(inc_top, FRONT_X + pF_W, inc_dim_x - 2)
    ext_v(inc_bot, FRONT_X + pF_W, inc_dim_x - 2)
    arr_v(inc_dim_x, inc_top, inc_bot, f"I/C: {MAX_INC_H} mm", right=True)

    # ────────────────────────────────────────────────────────────────────────
    # 10. SPEC BOX (optional)
    # ────────────────────────────────────────────────────────────────────────
    SB_W = 345
    SB_H = 240
    SB_X = SVG_W - SB_W - 16
    SB_Y = SVG_H - SB_H - GA_BOTTOM_STRIP - 10

    if include_spec_box:
        dwg.add(dwg.rect(insert=(SB_X, SB_Y), size=(SB_W, SB_H),
                         fill=SPEC_BG, stroke=SPEC_BD, stroke_width=1.8, rx=4))
        hdr_h = 26
        dwg.add(dwg.rect(insert=(SB_X, SB_Y), size=(SB_W, hdr_h),
                         fill=SPEC_HEADER_BG, stroke="none", rx=4))
        dwg.add(dwg.line((SB_X, SB_Y + hdr_h), (SB_X + SB_W, SB_Y + hdr_h),
                         stroke=SPEC_BD, stroke_width=0.8))
        dwg.add(dwg.text("PANEL GA DRAWING — SPECIFICATIONS",
                         insert=(SB_X + SB_W / 2, SB_Y + hdr_h / 2 + 5),
                         font_size=11, fill=SPEC_BD, text_anchor="middle",
                         font_family="Arial", font_weight="bold"))

        specs = [
            ("Panel Size  W × H × D", f"{PANEL_W} × {PANEL_H} × {PANEL_D_} mm"),
            ("Mounting Plate  W × H", f"{MOUNT_W} × {MOUNT_H} mm"),
            ("Plinth Height", f"{PLINTH_H} mm"),
            ("Panel Colour", "RAL 7035 (Light Grey)"),
            ("Mounting Plate Finish", "Chrome Plating / Zinc Passivated"),
            ("Busbar Chamber Height", f"{BUSBAR_CH} mm  (IEC 61439)"),
            ("Busbar Thickness", f"{busbar_thick} mm"),
            (f"{busbar_material} Busbar", busbar_spec_text),
            ("Total Busbar Current", f"{busbar_current:.1f} A"),
            ("Incomers / Outgoing", f"{len(incomer_mccbs)} / {len(outgoing_mccbs)}"),
            ("Phase–Phase Clearance", f"≥ {CLEARANCE_PP} mm"),
            ("Phase–Earth Clearance", f"≥ {CLEARANCE_PE} mm"),
        ]

        row_h = (SB_H - hdr_h) / len(specs)
        DIV_X = SB_X + 170

        for i, (key, val) in enumerate(specs):
            ry = SB_Y + hdr_h + i * row_h
            dwg.add(dwg.line((SB_X, ry), (SB_X + SB_W, ry), stroke=SPEC_GRID, stroke_width=0.4))
            dwg.add(dwg.line((DIV_X, ry), (DIV_X, ry + row_h), stroke=SPEC_GRID, stroke_width=0.4))
            ty = ry + row_h / 2 + 3.5
            dwg.add(dwg.text(key, insert=(SB_X + 6, ty),
                             font_size=8.5, fill=SUB_C, font_family="Arial"))
            dwg.add(dwg.text(val, insert=(SB_X + SB_W - 6, ty),
                             font_size=8.5, fill=TEXT_C, text_anchor="end",
                             font_family="Arial", font_weight="bold"))

        dwg.add(dwg.rect(insert=(SB_X, SB_Y), size=(SB_W, SB_H),
                         fill="none", stroke=SPEC_BD, stroke_width=1.8, rx=4))

    # ────────────────────────────────────────────────────────────────────────
    # 11. Title strip at bottom
    # ────────────────────────────────────────────────────────────────────────
    strip_reserved_w = SB_W + 28 if include_spec_box else 28
    strip_text_right_x = SVG_W - SB_W - 45 if include_spec_box else SVG_W - 45
    strip_y = SVG_H - GA_BOTTOM_STRIP
    dwg.add(dwg.rect(insert=(0, strip_y), size=(SVG_W - strip_reserved_w, GA_BOTTOM_STRIP),
                     fill=TITLE_STRIP_BG, stroke=SPEC_GRID, stroke_width=1))
    dwg.add(dwg.text("MICROGRID PANEL  —  GENERAL ARRANGEMENT (GA)",
                     insert=(18, strip_y + GA_BOTTOM_STRIP / 2 + 5),
                     font_size=13, fill=HEAD_C, font_family="Arial", font_weight="bold"))
    now_str = datetime.datetime.now().strftime("%d-%b-%Y")
    dwg.add(dwg.text(f"Date: {now_str}  |  Scale: NTS  |  IEC 61439 compliant",
                     insert=(strip_text_right_x, strip_y + GA_BOTTOM_STRIP / 2 + 5),
                     font_size=9, fill=SUB_C, text_anchor="end", font_family="Arial"))

    return dwg.tostring(), SVG_W, SVG_H, PANEL_W, PANEL_H, PANEL_D_
