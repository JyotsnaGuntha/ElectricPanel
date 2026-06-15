"""
Bill of Materials generation and export helpers.
"""

import base64
import datetime
import io
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from svglib.svglib import svg2rlg

from src.bom.generator import BOMItem, generate_bom_items
from src.utils import get_mccb_dims


def _resolve_logo_path() -> str | None:
    """Return an absolute path to the footer logo for source and frozen runs."""
    logo_name = "Kirloskar Oil Engine Logo.png"
    candidates = []

    # PyInstaller one-file/one-dir extraction root.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / logo_name)
        candidates.append(Path(meipass) / "ui" / logo_name)

    # Location beside executable (useful for one-dir bundles).
    executable_dir = Path(sys.executable).resolve().parent
    candidates.append(executable_dir / logo_name)
    candidates.append(executable_dir / "ui" / logo_name)

    # Project root when running from source: core/bom.py -> ../
    candidates.append(Path(__file__).resolve().parents[1] / logo_name)
    candidates.append(Path(__file__).resolve().parents[1] / "ui" / logo_name)

    # Current working directory fallback.
    candidates.append(Path.cwd() / logo_name)
    candidates.append(Path.cwd() / "ui" / logo_name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _draw_logo(canvas_obj, logo_x, logo_y, logo_w, logo_h):
    """Draw logo safely in both source and frozen runtimes."""
    logo_path = _resolve_logo_path()
    if not logo_path:
        return

    try:
        canvas_obj.drawImage(
            logo_path,
            logo_x,
            logo_y,
            width=logo_w,
            height=logo_h,
            preserveAspectRatio=True,
            mask="auto",
        )
        return
    except Exception:
        pass

    # Fallback: read bytes and render through ImageReader.
    try:
        with open(logo_path, "rb") as file_handle:
            image_reader = ImageReader(io.BytesIO(file_handle.read()))
        canvas_obj.drawImage(
            image_reader,
            logo_x,
            logo_y,
            width=logo_w,
            height=logo_h,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:
        pass


class NumberedCanvas(canvas.Canvas):
    """PDF canvas with page numbering and footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_footer(self, page_count):
        self.saveState()
        logo_w, logo_h = 100, 35
        _draw_logo(self, A4[0] - 45 - logo_w, A4[1] - 30 - logo_h, logo_w, logo_h)

        self.setFont("Helvetica", 8)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(45, 50, A4[0] - 45, 50)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(45, 35, "Kirloskar Oil Engines Ltd.")
        now = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        self.drawCentredString(A4[0] / 2.0, 35, f"Report Generated: {now}")
        self.drawRightString(A4[0] - 45, 35, f"Page {self.getPageNumber()} of {page_count}")
        self.restoreState()


class GACanvas(canvas.Canvas):
    """PDF canvas for GA drawings with a footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_footer(self, page_count):
        self.saveState()
        page_size = landscape(A4)
        _draw_logo(self, page_size[0] - 40 - 90, page_size[1] - 25 - 32, 90, 32)

        self.setFont("Helvetica", 8)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(30, 45, page_size[0] - 30, 45)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(30, 32, "Kirloskar Oil Engines Ltd.")
        now = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        self.drawCentredString(page_size[0] / 2.0, 32, f"Report Generated: {now}")
        self.drawRightString(page_size[0] - 30, 32, f"Page {self.getPageNumber()} of {page_count}")
        self.restoreState()


def _build_schedule_rows(incomer_list, mccb_outputs, mccb_db, num_poles):
    schedule = [["Tag", "Description", "Rating (A)", "Poles", "H × W × D (mm)", "Frame"]]
    for index, rating in enumerate(incomer_list):
        dims = get_mccb_dims(rating, mccb_db)
        schedule.append([
            f"I/C {index + 1}",
            "Incomer MCCB",
            f"{rating}A",
            f"{num_poles}P",
            f"{dims['h']}×{dims['w']}×{dims['d']}",
            dims["frame"],
        ])
    for index, rating in enumerate(mccb_outputs):
        dims = get_mccb_dims(rating, mccb_db)
        schedule.append([
            f"O/G {index + 1}",
            "Outgoing MCCB",
            f"{rating}A",
            f"{num_poles}P",
            f"{dims['h']}×{dims['w']}×{dims['d']}",
            dims["frame"],
        ])
    return schedule


def generate_pdf_report(
    sld_svg,
    sld_svg_width,
    sld_svg_height,
    ga_svg_str,
    ga_svg_w,
    ga_svg_h,
    incomer_list,
    mccb_outputs,
    bom_items,
    solar_kw,
    grid_kw,
    num_dg,
    num_outputs,
    total_busbar_current,
    total_outgoing_rating,
    busbar_spec,
    panel_w,
    panel_h,
    panel_d,
    num_poles,
    mccb_db,
    warning_flag=False,
    bess_kwh=None,
    bess_kw=None,
    bess_hours=None,
):
    """Generate the technical report PDF used by the desktop UI."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.fontSize = 22
    title_style.textColor = colors.HexColor("#c37c5a")
    title_style.alignment = 1

    h2_style = styles["Heading2"]
    h2_style.fontSize = 16
    h2_style.textColor = colors.HexColor("#19988b")
    h2_style.spaceBefore = 12
    h2_style.spaceAfter = 8

    normal_style = styles["Normal"]
    normal_style.fontSize = 10
    normal_style.leading = 13
    normal_style.alignment = 4

    story = []
    story.append(Paragraph("Microgrid Panel Technical Report", title_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. System Overview", h2_style))
    grid_txt = f"<b>{grid_kw} kW</b> Grid supply, " if grid_kw > 0 else ""
    solar_txt = f"and <b>{solar_kw} kWp</b> Solar PV" if solar_kw > 0 else ""
    bess_txt = f", and a <b>{round(bess_kwh)} kWh</b> Battery Energy Storage System (BESS)" if (bess_kwh is not None and bess_kwh > 0) else ""
    story.append(Paragraph(
        f"This report details the configuration and material requirements for a customized Microgrid Panel. "
        f"The system handles <b>{int(num_dg)} DG(s)</b>, {grid_txt}{solar_txt}{bess_txt}. "
        f"Managed via a centralized Microgrid Controller (MGC).",
        normal_style,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. System Specifications", h2_style))
    specs = (
        f"<b>Total Busbar Current Rating:</b> {total_busbar_current:.2f}A<br/>"
        f"<b>Total Outgoing Capacity:</b> {total_outgoing_rating:.0f}A<br/>"
        f"<b>Recommended Busbar:</b> {busbar_spec}<br/>"
        f"<b>Panel Dimensions (Computed):</b> {panel_w}W × {panel_h}H × {panel_d}D mm<br/>"
        f"<b>System Configuration:</b> {int(num_poles)}-Phase, {int(num_outputs)} Outgoing Feeders<br/>"
    )
    if bess_kwh is not None and bess_kwh > 0:
        bess_kw_val = bess_kw if bess_kw is not None else (bess_kwh / (bess_hours or 8))
        specs += (
            f"<b>BESS Capacity:</b> {round(bess_kw_val)} kW / {round(bess_kwh)} kWh (Backup Duration: {round(bess_hours or 8)} Hrs)<br/>"
        )
    if warning_flag:
        specs += "<br/><font color='red'><b>WARNING:</b> Total busbar current exceeds total outgoing rating. Review configuration.</font>"
    story.append(Paragraph(specs, normal_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("3. Single Line Diagram (SLD)", h2_style))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False, encoding="utf-8") as handle:
        handle.write(sld_svg)
        temp_sld = handle.name

    try:
        drawing = svg2rlg(temp_sld)
        if drawing:
            scale = 505.0 / sld_svg_width
            drawing.scale(scale, scale)
            drawing.width = sld_svg_width * scale
            drawing.height = sld_svg_height * scale
            sld_table = Table([[drawing]], colWidths=[505])
            sld_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(sld_table)
    except Exception as error:
        story.append(Paragraph(f"[Error rendering SLD: {error}]", normal_style))
    finally:
        try:
            os.unlink(temp_sld)
        except Exception:
            pass

    story.append(Spacer(1, 10))
    story.append(Paragraph("<i>Note: Diagram illustrates electrical topology and power flow.</i>", normal_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("4. General Arrangement (GA) Drawing", h2_style))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False, encoding="utf-8") as handle:
        handle.write(ga_svg_str)
        temp_ga = handle.name

    try:
        ga_rlg = svg2rlg(temp_ga)
        if ga_rlg:
            scale_ga = 505.0 / ga_svg_w
            ga_rlg.scale(scale_ga, scale_ga)
            ga_rlg.width = ga_svg_w * scale_ga
            ga_rlg.height = ga_svg_h * scale_ga
            ga_table = Table([[ga_rlg]], colWidths=[505])
            ga_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(ga_table)
    except Exception as error:
        story.append(Paragraph(f"[Error rendering GA: {error}]", normal_style))
    finally:
        try:
            os.unlink(temp_ga)
        except Exception:
            pass

    story.append(Spacer(1, 10))
    story.append(Paragraph("<i>Internal layout and dimensional overview.</i>", normal_style))
    story.append(Spacer(1, 15))

    story.append(Paragraph("4.1 MCCB Schedule (from Database)", h2_style))
    sched_data = _build_schedule_rows(incomer_list, mccb_outputs, mccb_db, num_poles)
    sched_table = Table(sched_data, colWidths=[40, 130, 60, 40, 115, 120])
    sched_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19988b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(sched_table)
    story.append(PageBreak())

    story.append(Paragraph("5. Bill Of Material (BOM)", h2_style))
    story.append(Spacer(1, 8))

    table_data = [["Sr", "Component / Description", "Rating", "Qty", "UOM"]]
    for index, item in enumerate(bom_items, 1):
        table_data.append([str(index), item.description, item.rating, str(item.qty), item.uom])

    table = Table(table_data, colWidths=[25, 305, 75, 55, 55])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19988b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("6. Notes & Remarks", h2_style))
    story.append(Paragraph(
        "• This BOM is subject to final design review.<br/>"
        "• All MCCB ratings include a 1.25× safety factor.<br/>"
        "• Busbar sizing considers thermal conductivity and current density limits.<br/>"
        "• Panel dimensions are computed dynamically from MCCB database.<br/>"
        "• All components per relevant Indian Standards and IEC guidelines.",
        normal_style,
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generate_ga_pdf(ga_svg_str, ga_svg_w, ga_svg_h, incomer_list, mccb_outputs, panel_w, panel_h, panel_d, num_poles, mccb_db):
    """Generate standalone GA drawing PDF (landscape)."""

    buffer = io.BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(buffer, pagesize=page_size, rightMargin=30, leftMargin=30, topMargin=35, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.fontSize = 18
    title_style.textColor = colors.HexColor("#c37c5a")
    title_style.alignment = 1

    h2_style = styles["Heading2"]
    h2_style.fontSize = 13
    h2_style.textColor = colors.HexColor("#19988b")

    normal_style = styles["Normal"]
    normal_style.fontSize = 9
    normal_style.leading = 12

    story = []
    story.append(Paragraph("Microgrid Panel — Internal General Arrangement (GA)", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Panel Dimensions (Computed):</b> {panel_w}W × {panel_h}H × {panel_d}D mm",
        normal_style,
    ))
    story.append(Spacer(1, 8))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False, encoding="utf-8") as handle:
        handle.write(ga_svg_str)
        temp_ga = handle.name

    try:
        ga_drw = svg2rlg(temp_ga)
        if ga_drw:
            avail_w = page_size[0] - 60
            avail_h = page_size[1] - 160
            scale_g = min(avail_w / ga_svg_w, avail_h / ga_svg_h)
            ga_drw.scale(scale_g, scale_g)
            ga_drw.width = ga_svg_w * scale_g
            ga_drw.height = ga_svg_h * scale_g
            ga_table = Table([[ga_drw]], colWidths=[avail_w])
            ga_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(ga_table)
    except Exception as error:
        story.append(Paragraph(f"[Error rendering GA: {error}]", normal_style))
    finally:
        try:
            os.unlink(temp_ga)
        except Exception:
            pass

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<i>{len(incomer_list)} incomer(s) | {len(mccb_outputs)} outgoing feeder(s). All dimensions in mm.</i>",
        normal_style,
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph("MCCB Schedule (from Database)", h2_style))
    sched_data = _build_schedule_rows(incomer_list, mccb_outputs, mccb_db, num_poles)
    sched_table = Table(sched_data, colWidths=[50, 130, 70, 45, 120, 90])
    sched_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19988b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(sched_table)

    doc.build(story, canvasmaker=GACanvas)
    buffer.seek(0)
    return buffer


def generate_excel_bom(bom_items):
    """Generate the BOM as an Excel workbook."""

    bom_dicts = []
    for index, item in enumerate(bom_items, 1):
        row = item.to_dict()
        row["Sr No"] = index
        bom_dicts.append(row)

    frame = pd.DataFrame(bom_dicts)
    if "Sr No" in frame.columns:
        columns = ["Sr No"] + [column for column in frame.columns if column != "Sr No"]
        frame = frame[columns]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="BOM")
    output.seek(0)
    return output.getvalue()


def encode_file_response(data_bytes, filename, mime_type):
    """Return a JSON-safe download response."""

    return {
        "filename": filename,
        "mime_type": mime_type,
        "data_base64": base64.b64encode(data_bytes).decode("ascii"),
    }


__all__ = [
    "BOMItem",
    "generate_bom_items",
    "generate_pdf_report",
    "generate_ga_pdf",
    "generate_excel_bom",
    "encode_file_response",
]
