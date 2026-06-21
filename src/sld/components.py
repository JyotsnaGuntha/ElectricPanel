"""
SLD Component Drawings
Primitive drawing functions for MCCB, Tower, Solar, and MGC.
"""

import math


def draw_mccb(dwg, x, y, rating, poles, label, theme_text="#e2e8f0", theme_sub="#94a3b8", side="left", component_type="MCCB"):
    """
    Draw MCCB/ACB symbol with label text.
    
    Args:
        dwg: svgwrite Drawing object
        x, y: Position of MCCB/ACB center
        rating: Current rating (A)
        poles: Number of poles
        label: Tag label (e.g., "I/C 1")
        theme_text: Text color
        theme_sub: Subtitle color
        side: "left" or "right" (affects label positioning)
        component_type: "MCCB" or "ACB" - determines label text
    """
    dwg.add(dwg.line(start=(x, y - 50), end=(x, y - 18), stroke=theme_text, stroke_width=2))
    dwg.add(dwg.line(start=(x, y + 12), end=(x, y + 50), stroke=theme_text, stroke_width=2))
    dwg.add(dwg.path(d=f"M{x},{y-18} A14,14 0 0,0 {x+2},{y+12}", 
                     stroke="#10b981", fill="none", stroke_width=2.5))
    
    if side == "left":
        info_x, anchor = x - 25, "end"
        label_x, label_anchor = x + 35, "start"
    else:
        info_x, anchor = x + 25, "start"
        label_x, label_anchor = x - 35, "end"
    
    component_label = "ACB" if component_type == "ACB" else "MCCB"
    
    dwg.add(dwg.text(f"{rating} A, {poles}pole,", 
                     insert=(info_x, y - 5), font_size=12, fill=theme_text, 
                     text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text(component_label, 
                     insert=(info_x, y + 12), font_size=11, fill=theme_sub, 
                     text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text(label, 
                     insert=(label_x, y + 5), font_size=14, font_weight="bold", 
                     fill=theme_text, text_anchor=label_anchor, font_family="Arial"))


def draw_tower(dwg, x, y, theme_text="#e2e8f0"):
    """
    Draw transmission tower symbol (for grid supply).
    
    Args:
        dwg: svgwrite Drawing object
        x, y: Position of tower base
        theme_text: Line color
    """
    h = 90
    w = 25
    dwg.add(dwg.line((x, y - 5), (x - w, y + h), stroke=theme_text, stroke_width=2))
    dwg.add(dwg.line((x, y - 5), (x + w, y + h), stroke=theme_text, stroke_width=2))
    dwg.add(dwg.line((x - w, y + h), (x + w, y + h), stroke=theme_text, stroke_width=2))
    
    arm_y = [y + 15, y + 40, y + 65]
    arm_w = [18, 28, 24]
    
    for i in range(3):
        dwg.add(dwg.line((x - arm_w[i], arm_y[i]), (x + arm_w[i], arm_y[i]), 
                         stroke=theme_text, stroke_width=2))
        dwg.add(dwg.line((x - arm_w[i], arm_y[i]), (x - arm_w[i], arm_y[i] + 8), 
                         stroke=theme_text, stroke_width=1.2))
        dwg.add(dwg.line((x + arm_w[i], arm_y[i]), (x + arm_w[i], arm_y[i] + 8), 
                         stroke=theme_text, stroke_width=1.2))
    
    for i in range(len(arm_y) - 1):
        y1, y2 = arm_y[i], arm_y[i + 1]
        w1, w2 = arm_w[i], arm_w[i + 1]
        dwg.add(dwg.line((x - w1, y1), (x + w2, y2), 
                         stroke=theme_text, stroke_width=0.8, stroke_opacity=0.4))
        dwg.add(dwg.line((x + w1, y1), (x - w2, y2), 
                         stroke=theme_text, stroke_width=0.8, stroke_opacity=0.4))


def draw_solar(
    dwg,
    x,
    y,
    theme_text="#e2e8f0",
    panel_fill="#1e293b",
    sun_color="#fbbf24",
):
    """
    Draw solar PV symbol with sun rays.
    
    Args:
        dwg: svgwrite Drawing object
        x, y: Position of solar symbol
        theme_text: Line and text color
        panel_fill: Solar panel body fill color
        sun_color: Sun/rays color
    """
    dwg.add(dwg.path(d=f"M{x-20},{y+55} L{x+20},{y+55} L{x+30},{y+20} L{x-30},{y+20} Z", 
                     fill=panel_fill, stroke=theme_text, stroke_width=2))
    
    for i in range(1, 4):
        h_y = y + 20 + i * (35 / 4)
        dwg.add(dwg.line((x - 30 + i * 2.5, h_y), (x + 30 - i * 2.5, h_y), 
                         stroke=theme_text, stroke_opacity=0.4))
    
    dwg.add(dwg.line((x, y + 20), (x, y + 55), stroke=theme_text, stroke_opacity=0.4))
    dwg.add(dwg.line((x - 10, y + 20), (x - 8, y + 55), stroke=theme_text, stroke_opacity=0.4))
    dwg.add(dwg.line((x + 10, y + 20), (x + 8, y + 55), stroke=theme_text, stroke_opacity=0.4))
    
    cx, cy = x - 25, y - 5
    dwg.add(dwg.circle(center=(cx, cy), r=10, stroke=sun_color, fill="none", stroke_width=2.5))
    
    for i in range(8):
        angle = i * 45
        r1, r2 = 12, 17
        x1 = cx + r1 * math.cos(math.radians(angle))
        y1 = cy + r1 * math.sin(math.radians(angle))
        x2 = cx + r2 * math.cos(math.radians(angle))
        y2 = cy + r2 * math.sin(math.radians(angle))
        dwg.add(dwg.line((x1, y1), (x2, y2), stroke=sun_color, stroke_width=1.5))


def draw_mgc(
    dwg,
    x,
    y,
    fill_color="#1e1b4b",
    stroke_color="#a78bfa",
    text_color="white",
):
    """
    Draw Microgrid Controller (MGC) symbol.
    
    Args:
        dwg: svgwrite Drawing object
        x, y: Top-left position of MGC box
        fill_color: MGC outer box fill color
        stroke_color: MGC outline and pin color
        text_color: MGC label text color
    """
    size = 100
    dwg.add(dwg.rect(insert=(x, y), size=(size, size), fill=fill_color, 
                     stroke=stroke_color, stroke_width=3, rx=8))
    dwg.add(dwg.rect(insert=(x + 15, y + 15), size=(70, 70), fill="none", 
                     stroke=stroke_color, stroke_width=2))
    
    pin_len = 12
    spacing = size / 7
    
    for i in range(1, 7):
        pos = i * spacing
        dwg.add(dwg.line((x + pos, y - pin_len), (x + pos, y), 
                         stroke=stroke_color, stroke_width=2.5))
        dwg.add(dwg.line((x + pos, y + size), (x + pos, y + size + pin_len), 
                         stroke=stroke_color, stroke_width=2.5))
        dwg.add(dwg.line((x - pin_len, y + pos), (x, y + pos), 
                         stroke=stroke_color, stroke_width=2.5))
        dwg.add(dwg.line((x + size, y + pos), (x + size + pin_len, y + pos), 
                         stroke=stroke_color, stroke_width=2.5))
    
    dwg.add(dwg.text("MGC", insert=(x + size / 2, y + size / 2 + 8), 
                     font_size=20, fill=text_color, font_weight="bold", text_anchor="middle"))


def draw_bess(
    dwg,
    x,
    y,
    theme_text="#e2e8f0",
    fill_color="#1e293b",
    bess_highlight_color="#10b981",
):
    """
    Draw Battery Energy Storage System (BESS) symbol.
    
    Args:
        dwg: svgwrite Drawing object
        x, y: Base coordinate center for BESS (corresponding to y_sources)
        theme_text: Line and text color
        fill_color: Battery enclosure fill color
        bess_highlight_color: Battery level indicators fill color
    """
    # Enclosure body
    dwg.add(dwg.rect(insert=(x - 18, y - 22), size=(36, 45), fill=fill_color, 
                     stroke=theme_text, stroke_width=2, rx=3))
    # Battery positive terminal cap
    dwg.add(dwg.rect(insert=(x - 7, y - 28), size=(14, 6), fill=theme_text, 
                     stroke=theme_text, stroke_width=1, rx=1))
    
    # 3 horizontal bars showing charge level
    dwg.add(dwg.rect(insert=(x - 12, y + 11), size=(24, 8), fill=bess_highlight_color, rx=1))
    dwg.add(dwg.rect(insert=(x - 12, y - 1), size=(24, 8), fill=bess_highlight_color, rx=1))
    dwg.add(dwg.rect(insert=(x - 12, y - 13), size=(24, 8), fill=bess_highlight_color, rx=1))
