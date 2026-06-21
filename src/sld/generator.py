"""
SLD Generator
Main SLD (Single Line Diagram) generation logic.
"""

import svgwrite as svg
from .components import draw_mccb, draw_tower, draw_solar, draw_mgc, draw_bess
from ..constants import SLD_MIN_WIDTH, SLD_HEIGHT, SLD_MIN_COL_SPACING, SLD_MARGIN_LEFT, SLD_MARGIN_RIGHT


def compute_canvas(n_dg, g_kw, s_kw, n_out, bess_kwh=0.0):
    """
    Compute SLD canvas dimensions based on number of sources and outputs.
    
    Args:
        n_dg: Number of DGs
        g_kw: Grid capacity (kW)
        s_kw: Solar capacity (kW)
        n_out: Number of outgoing feeders
        bess_kwh: BESS capacity (kWh)
    
    Returns:
        (width, height, inc_spacing, out_spacing, x_init)
    """
    n_incomers = int(n_dg) + (1 if g_kw > 0 else 0) + (1 if s_kw > 0 else 0) + (1 if bess_kwh > 0 else 0)
    n_incomers = max(n_incomers, 1)
    n_out = max(int(n_out), 1)
    
    width = SLD_MARGIN_LEFT + max(n_incomers, n_out + 0.5) * SLD_MIN_COL_SPACING + SLD_MARGIN_RIGHT
    width = max(width, SLD_MIN_WIDTH)
    
    return int(width), SLD_HEIGHT, SLD_MIN_COL_SPACING, SLD_MIN_COL_SPACING, int(SLD_MARGIN_LEFT + 60)


def get_component_type(rating):
    """
    Determine component type (MCCB or ACB) based on rating.
    
    If rating > 800 A, use ACB; otherwise use MCCB.
    """
    return "ACB" if rating > 800 else "MCCB"


def generate_sld(
    system_calcs,
    num_outputs,
    mccb_outputs,
    num_poles,
    num_dg,
    grid_kw,
    solar_kw,
    total_busbar_current,
    theme_svg_bg="#020617",
    theme_text="#e2e8f0",
    theme_svg_stroke="#334155",
    theme_sub="#94a3b8",
    bess_kwh=0.0,
):
    """
    Generate complete SLD diagram as SVG string.
    
    Args:
        system_calcs: SystemCalculations instance with all electrical data
        num_outputs: Number of outgoing feeders
        mccb_outputs: List of outgoing MCCB ratings
        num_poles: 3 or 4 (system phases)
        num_dg: Number of DGs
        grid_kw: Grid rating (kW)
        solar_kw: Solar rating (kW)
        total_busbar_current: Total busbar current (A)
        theme_svg_bg: Background color
        theme_text: Text color
        theme_svg_stroke: Line stroke color
        theme_sub: Subtitle color
        bess_kwh: BESS capacity (kWh)
    
    Returns:
        (svg_string, canvas_width, canvas_height)
    """
    width, height, inc_spacing, out_spacing, x_init = compute_canvas(num_dg, grid_kw, solar_kw, num_outputs, bess_kwh=bess_kwh)

    is_dark_theme = theme_text.lower() in ("#e2e8f0", "#e7eef9")
    scope_line_color = "#475569" if is_dark_theme else "#94a3b8"
    scope_label_color = "#94a3b8" if is_dark_theme else "#475569"
    panel_label_color = "#6366f1" if is_dark_theme else "#475569"
    auto_manual_color = "#cbd5e1" if is_dark_theme else "#64748b"
    dg_circle_color = "#60a5fa" if is_dark_theme else "#64748b"
    comm_line_color = "#a78bfa" if is_dark_theme else "#64748b"
    comm_label_color = "#c4b5fd" if is_dark_theme else "#64748b"
    solar_panel_fill = "#1e293b" if is_dark_theme else "#f8fafc"
    solar_sun_color = "#fbbf24" if is_dark_theme else "#d97706"
    bess_fill_color = "#1e293b" if is_dark_theme else "#f8fafc"
    bess_highlight_color = "#10b981" if is_dark_theme else "#059669"
    mgc_fill_color = "#1e1b4b" if is_dark_theme else "#eef2ff"
    mgc_stroke_color = "#a78bfa" if is_dark_theme else "#64748b"
    mgc_text_color = "#ffffff" if is_dark_theme else "#334155"
    
    dwg = svg.Drawing(size=(width, height), profile="full")
    dwg.viewbox(0, 0, width, height)
    dwg.add(dwg.rect((0, 0), (width, height), fill=theme_svg_bg, 
                     stroke=theme_svg_stroke, stroke_width=2, rx=15))
    
    y_division = int(height * 0.40)
    y_sources = int(height * 0.17)
    y_busbar = int(height * 0.58)
    
    # Division line between customer scope and supplier scope
    dwg.add(dwg.line((30, y_division), (width - 30, y_division), 
                     stroke=scope_line_color, stroke_width=1, stroke_dasharray="8,4"))
    dwg.add(dwg.text("Customer Scope", insert=(width / 2, 50), 
                     font_size=20, font_weight="bold", fill=scope_label_color, text_anchor="middle"))
    dwg.add(dwg.text("Kirloskar Scope", insert=(50, height - 40), 
                     font_size=20, font_weight="bold", fill=scope_label_color))
    dwg.add(dwg.text("Smart AMF Panel", insert=(width - 220, height - 40), 
                     font_size=18, fill=panel_label_color))
    
    # MGC (Microgrid Controller)
    mgc_x = width - 155
    mgc_y = y_division - 18
    draw_mgc(dwg, mgc_x, mgc_y, mgc_fill_color, mgc_stroke_color, mgc_text_color)
    dwg.add(dwg.text("Auto / Manual", insert=(mgc_x + 50, mgc_y - 15), 
                     font_size=13, fill=auto_manual_color, text_anchor="middle"))
    # ─────────────────────────────────────────────────────────────────────────────
    incomers_to_draw = []
    
    # DGs in reverse order (DG N, ..., DG 1)
    for i in reversed(range(int(num_dg))):
        incomers_to_draw.append({
            "type": "dg",
            "index": i,
            "tag": f"I/C {i + 1}",
        })

    # BESS
    if bess_kwh > 0:
        bess_tag_index = int(num_dg) + 1
        incomers_to_draw.append({
            "type": "bess",
            "tag": f"I/C {bess_tag_index}",
        })
        
    # Grid
    if grid_kw > 0:
        grid_tag_index = int(num_dg) + (1 if bess_kwh > 0 else 0) + 1
        incomers_to_draw.append({
            "type": "grid",
            "tag": f"I/C {grid_tag_index}",
        })
        
    # Solar
    if solar_kw > 0:
        solar_tag_index = int(num_dg) + (1 if bess_kwh > 0 else 0) + (1 if grid_kw > 0 else 0) + 1
        incomers_to_draw.append({
            "type": "solar",
            "tag": f"I/C {solar_tag_index}",
        })

    current_x = x_init
    active_ics_x = []
    
    for inc in incomers_to_draw:
        cx = current_x
        if inc["type"] == "dg":
            i = inc["index"]
            dwg.add(dwg.text(f"{system_calcs.dg_ratings_kva[i]} kVA", insert=(cx, y_sources - 85), 
                             font_size=16, font_weight="bold", fill=theme_text, text_anchor="middle"))
            dwg.add(dwg.circle(center=(cx, y_sources), r=45, stroke=dg_circle_color, 
                               fill="none", stroke_width=2.5))
            dwg.add(dwg.text(f"DG {i + 1}", insert=(cx, y_sources + 7), 
                             font_size=15, fill=theme_text, text_anchor="middle"))
            dwg.add(dwg.line((cx, y_sources + 45), (cx, y_division + 50), 
                             stroke=theme_text, stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, system_calcs.dg_mccbs[i], num_poles, 
                     inc["tag"], theme_text, theme_sub, "left", get_component_type(system_calcs.dg_mccbs[i]))
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar), 
                             stroke=theme_text, stroke_width=2))
            
        elif inc["type"] == "grid":
            dwg.add(dwg.text(f"{grid_kw} kW", insert=(cx, y_sources - 85), 
                             font_size=16, font_weight="bold", fill=theme_text, text_anchor="middle"))
            draw_tower(dwg, cx, y_sources - 30, theme_text)
            dwg.add(dwg.line((cx, y_sources + 30), (cx, y_division + 50), 
                             stroke=theme_text, stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, system_calcs.mccb_grid, num_poles, 
                     inc["tag"], theme_text, theme_sub, "left", get_component_type(system_calcs.mccb_grid))
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar), 
                             stroke=theme_text, stroke_width=2))
            
        elif inc["type"] == "solar":
            dwg.add(dwg.text(f"{solar_kw} kWp", insert=(cx, y_sources - 85), 
                             font_size=16, font_weight="bold", fill=theme_text, text_anchor="middle"))
            draw_solar(dwg, cx, y_sources - 30, theme_text, solar_panel_fill, solar_sun_color)
            dwg.add(dwg.line((cx, y_sources + 25), (cx, y_division + 50), 
                             stroke=theme_text, stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, system_calcs.mccb_solar, num_poles, 
                     inc["tag"], theme_text, theme_sub, "left", get_component_type(system_calcs.mccb_solar))
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar), 
                             stroke=theme_text, stroke_width=2))

        elif inc["type"] == "bess":
            dwg.add(dwg.text(f"{bess_kwh:.0f} kWh", insert=(cx, y_sources - 85), 
                             font_size=16, font_weight="bold", fill=theme_text, text_anchor="middle"))
            draw_bess(dwg, cx, y_sources, theme_text, bess_fill_color, bess_highlight_color)
            dwg.add(dwg.line((cx, y_sources + 23), (cx, y_division + 50), 
                             stroke=theme_text, stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, system_calcs.mccb_bess, num_poles, 
                     inc["tag"], theme_text, theme_sub, "left", get_component_type(system_calcs.mccb_bess))
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar), 
                             stroke=theme_text, stroke_width=2))
            
        active_ics_x.append(cx)
        current_x += inc_spacing
    
    # ────────────────────────────────────────────────────────────────────────────────
    # Draw busbar
    # ────────────────────────────────────────────────────────────────────────────────
    dwg.add(dwg.line((40, y_busbar), (width - 40, y_busbar), 
                     stroke="#ef4444", stroke_width=7))
    hash_start_x = 60
    for p in range(int(num_poles)):
        dwg.add(dwg.line((hash_start_x + p * 7, y_busbar + 12), (hash_start_x + p * 7 + 8, y_busbar - 12), 
                         stroke=theme_text, stroke_width=1.5))
    dwg.add(dwg.text(f"{total_busbar_current:.1f}A", insert=(width - 50, y_busbar - 12), 
                     font_size=13, fill="#f87171", text_anchor="end"))
    
    # ────────────────────────────────────────────────────────────────────────────────
    # Draw control/communication lines
    # ────────────────────────────────────────────────────────────────────────────────
    if active_ics_x:
        comm_y = y_division + 25
        dwg.add(dwg.line((active_ics_x[0], comm_y), (mgc_x - 12, comm_y), 
                         stroke=comm_line_color, stroke_width=1.2, stroke_dasharray="6,3"))
        for ax in active_ics_x:
            dwg.add(dwg.line((ax, comm_y), (ax, y_division + 50), 
                             stroke=comm_line_color, stroke_width=1, stroke_dasharray="4,2"))
        
        x_out_start = x_init + (inc_spacing / 2)
        mgc_pin_x = mgc_x + (3 * (100 / 7))
        comm_y_bottom = y_busbar + 160
        dwg.add(dwg.line((x_out_start, comm_y_bottom), (mgc_pin_x, comm_y_bottom), 
                         stroke=comm_line_color, stroke_width=1.2, stroke_dasharray="6,3"))
        dwg.add(dwg.line((mgc_pin_x, mgc_y + 112), (mgc_pin_x, comm_y_bottom), 
                         stroke=comm_line_color, stroke_width=1.2, stroke_dasharray="6,3"))
        for i in range(int(num_outputs)):
            ox = x_out_start + i * inc_spacing
            if ox > (mgc_x - 50):
                break
            dwg.add(dwg.line((ox, comm_y_bottom), (ox, y_busbar + 125), 
                             stroke=comm_line_color, stroke_width=1, stroke_dasharray="4,2"))
    
    # ────────────────────────────────────────────────────────────────────────────────
    # Draw outgoing feeders
    # ────────────────────────────────────────────────────────────────────────────────
    x_out_start = x_init + (inc_spacing / 2)
    for i in range(int(num_outputs)):
        ox = x_out_start + i * inc_spacing
        if ox > (mgc_x - 50):
            break
        rating = mccb_outputs[i] if i < len(mccb_outputs) else 250
        dwg.add(dwg.line((ox, y_busbar), (ox, y_busbar + 25), 
                         stroke=theme_text, stroke_width=2))
        draw_mccb(dwg, ox, y_busbar + 75, rating, num_poles, f"O/G {i + 1}", 
                 theme_text, theme_sub, "right", get_component_type(rating))
        dwg.add(dwg.line((ox, y_busbar + 125), (ox, height - 80), 
                         stroke=theme_text, stroke_width=2))
    
    # ────────────────────────────────────────────────────────────────────────────────
    # Add communication labels
    # ────────────────────────────────────────────────────────────────────────────────
    if active_ics_x:
        comm_y = y_division + 25
        comm_y_bottom = y_busbar + 160
        label_text = "Communication and Control Lines"
        dwg.add(dwg.rect(insert=(width / 2 - 120, comm_y - 12), size=(240, 24), 
                         fill=theme_svg_bg, stroke="none"))
        dwg.add(dwg.text(label_text, insert=(width / 2, comm_y + 6), 
                         font_size=13, fill=comm_label_color, text_anchor="middle"))
        dwg.add(dwg.rect(insert=(width / 2 - 120, comm_y_bottom - 12), size=(240, 24), 
                         fill=theme_svg_bg, stroke="none"))
        dwg.add(dwg.text(label_text, insert=(width / 2, comm_y_bottom + 6), 
                         font_size=13, fill=comm_label_color, text_anchor="middle"))
    
    return dwg.tostring(), width, height
