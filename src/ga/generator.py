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
    CLEARANCE_PP,
    CLEARANCE_PE,
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
    # Override plinth height to 300 mm per user request
    PLINTH_H = 300

    # 1. Compute all real-world mm dimensions
    pd_info = compute_panel_dimensions(incomer_mccbs, outgoing_mccbs, mccb_db, busbar_current)
    PANEL_W = pd_info["PANEL_W"]
    PANEL_H = pd_info["PANEL_H"]
    PANEL_D_ = pd_info["PANEL_D"]
    MOUNT_W = pd_info["MOUNT_W"]
    MOUNT_H = pd_info["MOUNT_H"]
    BUSBAR_CH = pd_info["BUSBAR_CH_MM"]
    MAX_INC_H = pd_info["MAX_INC_H"]
    MAX_OUT_H = pd_info["MAX_OUT_H"]
    busbar_thick = get_busbar_thickness(busbar_current)

    # Vertical positions in mm from top of panel:
    # HMI Screen: positioned at 100mm-400mm (300mm tall)
    # Busbar chamber: positioned below HMI to avoid overlap
    
    tallest_all_h = max(MAX_INC_H, MAX_OUT_H)
    y_outgoing_row_bottom = 150 + tallest_all_h
    
    # Busbar chamber positioned below HMI (starts at 100mm, 300mm tall, ends at 400mm)
    # Add 20mm gap + 420mm minimum ensures clear separation
    y_busbar_start = max(420, tallest_all_h + 150)
    total_busbar_h = BUSBAR_CH
    y_busbar_end = y_busbar_start + total_busbar_h
    y_incomer_row_bottom = PANEL_H - 250


    # 2. SVG canvas & scale factors
    SVG_W = GA_SVG_WIDTH
    SVG_H = GA_SVG_HEIGHT

    # Scale: fit front view into FRONT_MAX_W × (SVG_H – top/bottom space)
    AVAIL_H = SVG_H - 100 - GA_BOTTOM_STRIP
    front_max_w = GA_FRONT_MAX_W
    if not include_spec_box:
        front_max_w = SVG_W - GA_LEFT_MARGIN - GA_ELEV_GAP - GA_SIDE_MAX_W - 20
    SCALE = min(front_max_w / PANEL_W, AVAIL_H / (PANEL_H + PLINTH_H))
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

    # Positioning
    TOP_Y = 90
    if include_spec_box:
        FRONT_X = GA_LEFT_MARGIN
    else:
        FRONT_X = max(10, (SVG_W - (pF_W + GA_ELEV_GAP + pF_D)) / 2)
    SIDE_GAP = GA_ELEV_GAP if include_spec_box else 72
    SIDE_X = FRONT_X + pF_W + SIDE_GAP

    # Mounting plate top-left inside front view (starts 50mm inset)
    mp_x = FRONT_X + mm(50)
    mp_y = TOP_Y + mm(50)

    # 3. Colors (Responsive to Theme)
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
    DOOR_STROKE = "#f59e0b" if is_dark_theme else "#334155"
    HMI_STROKE = "#3b82f6" if is_dark_theme else "#94a3b8"
    HMI_BG = "#0a1a2e" if is_dark_theme else "#f8fafc"
    HMI_TXT = "#60a5fa" if is_dark_theme else "#334155"
    SPEC_HEADER_BG = "#0d3a4a" if is_dark_theme else "#e6f4f3"
    SPEC_GRID = "#1e3a5f" if is_dark_theme else "#cbd5e1"
    TITLE_STRIP_BG = "#060d1a" if is_dark_theme else "#e2e8f0"

    # 4. Create SVG Drawing
    dwg = svg.Drawing(size=(SVG_W, SVG_H), profile="full")
    dwg.viewbox(0, 0, SVG_W, SVG_H)
    dwg.add(dwg.rect((0, 0), (SVG_W, SVG_H), fill=BG))

    # 5. Helper functions
    def arr_h(x1, x2, y, label, above=True):
        """Horizontal dim arrow with ticked ends."""
        sign = -1 if above else 1
        lbl_y = y + sign * 14
        dwg.add(dwg.line((x1, y), (x2, y), stroke=DIM_C, stroke_width=1.3))
        for (tx, flip) in [(x1, 1), (x2, -1)]:
            dwg.add(dwg.line((tx, y - 5), (tx, y + 5), stroke=DIM_C, stroke_width=1.3))
            dwg.add(dwg.polygon([(tx, y), (tx + flip * 10, y - 4), (tx + flip * 10, y + 4)], fill=DIM_C))
        dwg.add(dwg.text(label, insert=((x1 + x2) / 2, lbl_y),
                         font_size=max(8, mm(11)), fill=DIM_C, text_anchor="middle",
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
                       font_size=max(8, mm(11)), fill=DIM_C, text_anchor="middle",
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

    # 6. FRONT ELEVATION — outer shell + plinth
    plinth_y = TOP_Y + pF_H
    # Plinth
    dwg.add(dwg.rect(insert=(FRONT_X, plinth_y), size=(pF_W, pF_PL),
                     fill=BASE_PLINTH, stroke=STROKE, stroke_width=1.5))
    hatch(FRONT_X, plinth_y, pF_W, pF_PL, step=12)
    # Main outer enclosure shell
    dwg.add(dwg.rect(insert=(FRONT_X, TOP_Y), size=(pF_W, pF_H),
                     fill=SHELL, stroke=STROKE, stroke_width=2.5))
    # Bezel guide
    bz = 10
    dwg.add(dwg.rect(insert=(FRONT_X + bz, TOP_Y + bz), size=(pF_W - 2 * bz, pF_H - 2 * bz),
                     fill="none", stroke=PANEL_GUIDE, stroke_width=0.9, stroke_dasharray="8,5"))

    # Mounting plate background
    dwg.add(dwg.rect(insert=(mp_x, mp_y), size=(mF_W, mF_H),
                     fill=MP_C, stroke=HMI_STROKE, stroke_width=1.1, stroke_dasharray="6,4"))

    # ── Busbar chamber layout
    bb_top_px = TOP_Y + mm(y_busbar_start)
    bb_h_px = mm(total_busbar_h)
    dwg.add(dwg.rect(insert=(mp_x + 5, bb_top_px), size=(mF_W - 10, bb_h_px),
                     fill="#1c1917" if is_dark_theme else "#f4f4f5",
                     stroke=BB_ST, stroke_width=1.2, stroke_dasharray="4,2"))
    # Busbar chamber header text (placed slightly above the chamber to not overlap the busbars)
    dwg.add(dwg.text(f"BUSBAR CHAMBER (4-POLE) — {BUSBAR_CH} mm",
                     insert=(mp_x + mF_W / 2, bb_top_px - 8),
                     font_size=max(8, mm(11)), fill=BB_ST, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))

    # Render 4 horizontal busbars inside the chamber
    colors_bb = ["#ef4444", "#f59e0b", "#3b82f6", "#4b5563" if is_dark_theme else "#9ca3af"]
    phases_bb = ["L1 (Red)", "L2 (Yellow)", "L3 (Blue)", "Neutral"]
    for idx_bb in range(4):
        y_center_bb = y_busbar_start + (busbar_thick / 2) + idx_bb * (busbar_thick + 25)
        bar_y_px = TOP_Y + mm(y_center_bb - busbar_thick / 2)
        bar_h_px = mm(busbar_thick)
        dwg.add(dwg.rect(insert=(mp_x + 10, bar_y_px), size=(mF_W - 20, bar_h_px),
                         fill=colors_bb[idx_bb], stroke=TEXT_C, stroke_width=0.5))
        # Add phase indicator text inside the busbar
        dwg.add(dwg.text(phases_bb[idx_bb], insert=(mp_x + 25, bar_y_px + bar_h_px / 2 + 2.5),
                         font_size=max(5.5, mm(8)), fill="#ffffff",
                         font_family="Arial", font_weight="bold"))


    # NOTE: Incoming and outgoing feeder MCCB drawings removed per user request.

    # Cable entry duct / gland plate at bottom of mounting plate
    duct_y_px = TOP_Y + mm(PANEL_H - 120)
    duct_h_px = mm(70)
    hatch(mp_x + 5, duct_y_px, mF_W - 10, duct_h_px, step=8)
    dwg.add(dwg.rect(insert=(mp_x + 5, duct_y_px), size=(mF_W - 10, duct_h_px),
                     fill="none", stroke=ZONE_ST, stroke_width=0.7, stroke_dasharray="5,3"))
    dwg.add(dwg.text("Cable Gland Plate / Entry Zone", insert=(mp_x + mF_W / 2, duct_y_px + duct_h_px / 2 + 3),
                     font_size=max(8, mm(10)), fill=SUB_C, text_anchor="middle", font_family="Arial", font_style="italic"))

    # TECHNICAL CAD-STYLE DOUBLE-DOOR CABINET FRONT ELEVATION
    # Create engineering drawing quality door representation
    
    # Main frame border (outermost edge)
    frame_margin = 3
    dwg.add(dwg.rect(insert=(FRONT_X + frame_margin, TOP_Y + frame_margin), 
                     size=(pF_W - 2*frame_margin, pF_H - 2*frame_margin),
                     fill="none", stroke=STROKE, stroke_width=2.2))
    
    # Inner frame (cabinet body)
    inner_margin = 8
    dwg.add(dwg.rect(insert=(FRONT_X + inner_margin, TOP_Y + inner_margin), 
                     size=(pF_W - 2*inner_margin, pF_H - 2*inner_margin),
                     fill="none", stroke=STROKE, stroke_width=1.4))
    
    # Center vertical seam (door split line)
    center_x = FRONT_X + (pF_W / 2)
    dwg.add(dwg.line((center_x, TOP_Y + 5), (center_x, TOP_Y + pF_H - 5),
                     stroke=STROKE, stroke_width=1.6))
    
    # Horizontal midline for door symmetry
    center_y = TOP_Y + (pF_H / 2)
    
    # LEFT DOOR - vertical handle (centered on door)
    left_handle_x = center_x - 15
    handle_height = mm(150)
    left_handle_y_top = center_y - (handle_height / 2)
    left_handle_y_bot = center_y + (handle_height / 2)
    handle_width = 2.5
    # Left handle vertical line
    dwg.add(dwg.line((left_handle_x - handle_width, left_handle_y_top), 
                     (left_handle_x - handle_width, left_handle_y_bot),
                     stroke=STROKE, stroke_width=1.2))
    # Left handle outline
    dwg.add(dwg.rect(insert=(left_handle_x - handle_width*2.5, left_handle_y_top - 2), 
                     size=(handle_width*5, left_handle_y_bot - left_handle_y_top + 4),
                     fill="none", stroke=STROKE, stroke_width=0.8))
    
    # RIGHT DOOR - vertical handle (centered on door)
    right_handle_x = center_x + 15
    right_handle_y_top = center_y - (handle_height / 2)
    right_handle_y_bot = center_y + (handle_height / 2)
    # Right handle vertical line
    dwg.add(dwg.line((right_handle_x + handle_width, right_handle_y_top), 
                     (right_handle_x + handle_width, right_handle_y_bot),
                     stroke=STROKE, stroke_width=1.2))
    # Right handle outline
    dwg.add(dwg.rect(insert=(right_handle_x - handle_width*2.5, right_handle_y_top - 2), 
                     size=(handle_width*5, right_handle_y_bot - right_handle_y_top + 4),
                     fill="none", stroke=STROKE, stroke_width=0.8))
    
    # PERIMETER FASTENING BOLTS/SCREWS - positioned around frame edges
    bolt_radius = 1.8
    bolt_positions = [
        # Top edge bolts
        (FRONT_X + 25, TOP_Y + 8),
        (FRONT_X + pF_W - 25, TOP_Y + 8),
        # Bottom edge bolts (above plinth)
        (FRONT_X + 25, TOP_Y + pF_H - 8),
        (FRONT_X + pF_W - 25, TOP_Y + pF_H - 8),
        # Left edge bolts
        (FRONT_X + 8, TOP_Y + 45),
        (FRONT_X + 8, TOP_Y + pF_H - 45),
        # Right edge bolts
        (FRONT_X + pF_W - 8, TOP_Y + 45),
        (FRONT_X + pF_W - 8, TOP_Y + pF_H - 45),
        # Mid-height bolts on sides
        (FRONT_X + 8, center_y - 30),
        (FRONT_X + 8, center_y + 30),
        (FRONT_X + pF_W - 8, center_y - 30),
        (FRONT_X + pF_W - 8, center_y + 30),
    ]
    
    for bolt_x, bolt_y in bolt_positions:
        # Bolt circle (screw head)
        dwg.add(dwg.circle(center=(bolt_x, bolt_y), r=bolt_radius,
                          fill="none", stroke=STROKE, stroke_width=0.9))
        # Bolt cross (screw slot)
        dwg.add(dwg.line((bolt_x - bolt_radius*0.6, bolt_y), (bolt_x + bolt_radius*0.6, bolt_y),
                        stroke=STROKE, stroke_width=0.7))
        dwg.add(dwg.line((bolt_x, bolt_y - bolt_radius*0.6), (bolt_x, bolt_y + bolt_radius*0.6),
                        stroke=STROKE, stroke_width=0.7))
    
    # DOOR FRAME CORNER REINFORCEMENT (small radius corners for door frame)
    corner_radius = 4
    corners = [
        (FRONT_X + inner_margin, TOP_Y + inner_margin),  # Top-left
        (FRONT_X + pF_W - inner_margin, TOP_Y + inner_margin),  # Top-right
        (FRONT_X + inner_margin, TOP_Y + pF_H - inner_margin),  # Bottom-left
        (FRONT_X + pF_W - inner_margin, TOP_Y + pF_H - inner_margin),  # Bottom-right
    ]
    
    for corner_x, corner_y in corners:
        # Small corner accent lines (reinforcement brackets)
        dwg.add(dwg.line((corner_x, corner_y + corner_radius), (corner_x, corner_y + corner_radius*2),
                        stroke=STROKE, stroke_width=0.7))
        dwg.add(dwg.line((corner_x + corner_radius, corner_y), (corner_x + corner_radius*2, corner_y),
                        stroke=STROKE, stroke_width=0.7))

    # HMI / Display Cutout on the Door (centered on left door half)
    # Measurement: width 420mm, height 300mm
    # Position HMI centered horizontally within left door half with proper top margin
    hmi_x_px = FRONT_X + mm((PANEL_W / 2 - 420) / 2)
    hmi_y_px = TOP_Y + mm(100)
    hmi_w_px = mm(420)
    hmi_h_px = mm(300)
    
    # Draw HMI cutout box with rounded corners
    dwg.add(dwg.rect(insert=(hmi_x_px, hmi_y_px), size=(hmi_w_px, hmi_h_px),
                     fill=HMI_BG, stroke=HMI_STROKE, stroke_width=2.0, rx=6))
    # Inner border for depth effect
    dwg.add(dwg.rect(insert=(hmi_x_px + 8, hmi_y_px + 8), size=(hmi_w_px - 16, hmi_h_px - 16),
                     fill="none", stroke=ZONE_ST, stroke_width=0.8, rx=4))
    
    # HMI text with proportional scaling
    hmi_fs = max(8, mm(13))
    hmi_sub_fs = max(6.5, mm(10))
    dwg.add(dwg.text("HMI / TOUCH SCREEN",
                     insert=(hmi_x_px + hmi_w_px / 2, hmi_y_px + hmi_h_px / 2 - hmi_fs / 4),
                     font_size=hmi_fs, fill=HMI_TXT, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))
    dwg.add(dwg.text("Control Display",
                     insert=(hmi_x_px + hmi_w_px / 2, hmi_y_px + hmi_h_px / 2 + hmi_fs),
                     font_size=hmi_sub_fs, fill=SUB_C, text_anchor="middle",
                     font_family="Arial", font_style="italic"))

    # Labels for Front view
    dwg.add(dwg.text("FRONT ELEVATION GA",
                     insert=(FRONT_X + pF_W / 2, TOP_Y + pF_H + pF_PL + 22),
                     font_size=max(10, mm(13)), fill=TEXT_C, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))

    # 7. SIDE ELEVATION
    # Plinth side view
    dwg.add(dwg.rect(insert=(SIDE_X, plinth_y), size=(pF_D, pF_PL),
                     fill=BASE_PLINTH, stroke=STROKE, stroke_width=1.5))
    hatch(SIDE_X, plinth_y, pF_D, pF_PL, step=12)
    # Outer side shell
    dwg.add(dwg.rect(insert=(SIDE_X, TOP_Y), size=(pF_D, pF_H),
                     fill=SHELL, stroke=STROKE, stroke_width=2.5))
    # Bezel
    dwg.add(dwg.rect(insert=(SIDE_X + bz, TOP_Y + bz), size=(pF_D - 2 * bz, pF_H - 2 * bz),
                     fill="none", stroke=PANEL_GUIDE, stroke_width=0.9, stroke_dasharray="8,5"))

    # Internal Mounting Plate line in side view (50mm from back)
    mp_x_side = SIDE_X + pF_D - mm_s(50)
    dwg.add(dwg.line((mp_x_side, TOP_Y + mm(50)), (mp_x_side, TOP_Y + pF_H - mm(50)),
                     stroke=HMI_STROKE, stroke_width=2.0, stroke_dasharray="4,2"))
    dwg.add(dwg.text("MP", insert=(mp_x_side - 8, TOP_Y + mm(80)),
                     font_size=max(8, mm(10)), fill=HMI_STROKE, text_anchor="end", font_family="Arial", font_weight="bold"))

    # Busbars stacked vertically in Side View
    for idx_bb in range(4):
        y_center_bb = y_busbar_start + (busbar_thick / 2) + idx_bb * (busbar_thick + 25)
        bar_y_side = TOP_Y + mm(y_center_bb)
        # Draw each busbar as a circle representing its cross section profile
        dwg.add(dwg.circle(center=(mp_x_side - mm_s(60), bar_y_side), r=mm(busbar_thick) / 2,
                           fill=colors_bb[idx_bb], stroke=TEXT_C, stroke_width=0.5))

    # HMI profile on front door (represented on side elevation)
    hmi_side_y = TOP_Y + mm(100)  # Match front view HMI Y position
    hmi_side_h = mm(300)  # Height matches front view
    hmi_side_d = mm_s(20)  # 20 mm door panel projection depth
    dwg.add(dwg.rect(insert=(SIDE_X, hmi_side_y), size=(hmi_side_d, hmi_side_h),
                     fill=HMI_BG, stroke=HMI_STROKE, stroke_width=1.2))
    dwg.add(dwg.text("HMI", insert=(SIDE_X + hmi_side_d + 4, hmi_side_y + hmi_side_h / 2 + 3),
                     font_size=max(8, mm(11)), fill=HMI_TXT, font_family="Arial", font_weight="bold"))


    # Side label
    dwg.add(dwg.text("SIDE ELEVATION",
                     insert=(SIDE_X + pF_D / 2, TOP_Y + pF_H + pF_PL + 22),
                     font_size=max(10, mm(13)), fill=TEXT_C, text_anchor="middle",
                     font_family="Arial", font_weight="bold"))

    # 8. Dimension arrows and annotations
    # Width dimension line (above front view)
    dim_y_top = TOP_Y - 44
    ext_h(FRONT_X, TOP_Y - 5, dim_y_top + 2)
    ext_h(FRONT_X + pF_W, TOP_Y - 5, dim_y_top + 2)
    arr_h(FRONT_X, FRONT_X + pF_W, dim_y_top, f"Width: {PANEL_W} mm")

    # Height and Plinth vertical dimensions stacked continuously along a single vertical line on the left
    dim_x_H = FRONT_X - 50
    # extension lines for vertical stacked dimensions
    ext_v(TOP_Y, FRONT_X - 5, dim_x_H - 5)
    ext_v(TOP_Y + pF_H, FRONT_X - 5, dim_x_H - 5)
    ext_v(TOP_Y + pF_H + pF_PL, FRONT_X - 5, dim_x_H - 5)
    
    # 1. Height arrow
    arr_v(dim_x_H, TOP_Y, TOP_Y + pF_H, f"{PANEL_H} mm", right=False)
    # 2. Plinth arrow (continued on the same vertical line, name plinth removed, showing only measurement "300 mm")
    arr_v(dim_x_H, TOP_Y + pF_H, TOP_Y + pF_H + pF_PL, "300 mm", right=False)

    # Depth dimension line (above side view)
    ext_h(SIDE_X, TOP_Y - 5, dim_y_top + 2)
    ext_h(SIDE_X + pF_D, TOP_Y - 5, dim_y_top + 2)
    arr_h(SIDE_X, SIDE_X + pF_D, dim_y_top, f"Depth: {PANEL_D_} mm")

    # NOTE: Clearance measurement near the HMI Touch board removed per user request.

    # Busbar chamber height dimension (between Front & Side)
    dim_x_bb = FRONT_X + pF_W + 25
    ext_v(bb_top_px, FRONT_X + pF_W, dim_x_bb - 2)
    ext_v(bb_top_px + bb_h_px, FRONT_X + pF_W, dim_x_bb - 2)
    arr_v(dim_x_bb, bb_top_px, bb_top_px + bb_h_px, f"Busbar Chamber: {BUSBAR_CH} mm", right=True)

    # 9. SPEC BOX (optional)
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

    # 10. Title strip at bottom
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
                     font_size=max(8, mm(10)), fill=SUB_C, text_anchor="end", font_family="Arial"))

    return dwg.tostring(), SVG_W, SVG_H, PANEL_W, PANEL_H, PANEL_D_
