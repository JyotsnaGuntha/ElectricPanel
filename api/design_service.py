"""
Core design orchestration for the Microgrid desktop app.
"""

from __future__ import annotations

import datetime
import re

from core.bom import generate_bom_items, generate_excel_bom, generate_ga_pdf, generate_pdf_report
from core.constants import FALLBACK_MCCB_DB
from core.ga import generate_ga_svg
from core.sld import SystemCalculations, generate_sld
from core.solar.calculator import calculate_bill_recommendation
from core.solar.parser import parse_uploaded_bill_files
from core.utils import (
    generate_busbar_spec,
    get_busbar_chamber_height,
    get_busbar_thickness,
    get_mccb_dims,
    get_standard_rating,
    get_theme_colors,
)


def _as_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def _as_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _normalize_list(values, length, default):
    items = list(values or [])
    if len(items) < length:
        items.extend([default] * (length - len(items)))
    return items[:length]


class DesignService:
    """Owns input normalization, design calculation, and export composition."""

    def __init__(self, theme="dark", mccb_db=None):
        self.theme = theme
        self.mccb_db = mccb_db or {}

    def set_theme(self, theme):
        if theme in ("dark", "light"):
            self.theme = theme

    def set_mccb_db(self, mccb_db):
        self.mccb_db = mccb_db or {}

    def _active_db(self):
        return self.mccb_db or FALLBACK_MCCB_DB

    def analyze_bills(self, files):
        if not files:
            raise ValueError("Please upload at least one PDF bill.")

        parsed_rows = parse_uploaded_bill_files(files)
        analysis = calculate_bill_recommendation(parsed_rows)
        print("--------------------Bill analysis:", analysis)
        return {
            "recommended_kw": analysis["recommended_kw"],
            "recommended_bess_kwh": analysis["recommended_bess_kwh"],
            "average_monthly_op_units": analysis["average_monthly_op_units"],
            "average_hourly_op_units": analysis["average_hourly_op_units"],
            "months": analysis["months"],
            "bill_data": analysis.get("bill_data", []),
        }

    def compute_design(self, payload):
        theme = payload.get("theme", self.theme)
        solar_kw = _as_float(payload.get("solar_kw", 0))
        grid_kw = _as_float(payload.get("grid_kw", 0))
        num_dg = max(0, _as_int(payload.get("num_dg", 0)))
        num_outputs = max(0, _as_int(payload.get("num_outputs", 0)))
        num_poles = _as_int(payload.get("num_poles", 0), 0)
        busbar_material = str(payload.get("busbar_material") or "").strip()

        if busbar_material not in ("Copper", "Aluminium"):
            raise ValueError("Please select busbar material.")
        if num_poles not in (3, 4):
            raise ValueError("Please select system phases / poles.")
        if num_outputs < 1:
            raise ValueError("Outgoing feeders must be at least 1.")

        dg_ratings = _normalize_list(payload.get("dg_ratings", []), num_dg, 0)
        outgoing_ratings = _normalize_list(payload.get("outgoing_ratings", []), num_outputs, 0)

        active_db = self._active_db()

        dg_ratings = [_as_float(value, 0) for value in dg_ratings]
        outgoing_ratings = [_as_float(value, 0) for value in outgoing_ratings]

        mccb_outputs = [get_standard_rating(value, active_db) for value in outgoing_ratings]
        system_calcs = SystemCalculations(solar_kw=solar_kw, grid_kw=grid_kw, dg_ratings_kva=dg_ratings, mccb_db=active_db)

        incomer_list = list(system_calcs.dg_mccbs)
        if grid_kw > 0:
            incomer_list.append(system_calcs.mccb_grid)
        if solar_kw > 0:
            incomer_list.append(system_calcs.mccb_solar)

        total_busbar_current = system_calcs.total_busbar_current
        total_outgoing_rating = sum(mccb_outputs)
        if total_busbar_current < total_outgoing_rating:
            raise ValueError(
                "Generation blocked: Incoming current is less than outgoing capacity. "
                "Increase incoming source or reduce outgoing ratings."
            )

        warning_flag = False
        busbar_spec = generate_busbar_spec(total_busbar_current, busbar_material)

        active_db = self._active_db()
        ga_svg_str, ga_svg_w, ga_svg_h, panel_w, panel_h, panel_d = generate_ga_svg(
            incomer_list,
            mccb_outputs,
            total_busbar_current,
            busbar_spec,
            num_poles,
            busbar_material,
            active_db,
            theme=theme,
            include_spec_box=False,
        )

        theme_colors = get_theme_colors(theme)
        sld_svg, sld_svg_w, sld_svg_h = generate_sld(
            system_calcs,
            num_outputs,
            mccb_outputs,
            num_poles,
            num_dg,
            grid_kw,
            solar_kw,
            total_busbar_current,
            theme_colors["svg_bg"],
            theme_colors["text"],
            theme_colors["svg_stroke"],
            theme_colors["subtitle"],
        )

        bom_objects = generate_bom_items(
            solar_kw,
            grid_kw,
            num_dg,
            system_calcs.dg_mccbs,
            system_calcs.mccb_solar,
            system_calcs.mccb_grid,
            mccb_outputs,
            num_poles,
            busbar_spec,
            total_busbar_current,
            busbar_material,
            panel_h,
            panel_w,
            panel_d,
            active_db,
        )

        bom_rows = []
        for index, item in enumerate(bom_objects, 1):
            row = item.to_dict()
            row["Sr No"] = index
            bom_rows.append(row)

        schedule_rows = []
        for index, rating in enumerate(incomer_list, 1):
            dims = get_mccb_dims(rating, active_db)
            schedule_rows.append(
                {
                    "tag": f"I/C {index}",
                    "description": "Incomer MCCB",
                    "rating": f"{rating}A",
                    "poles": f"{num_poles}P",
                    "dimensions": f"{dims['h']}×{dims['w']}×{dims['d']}",
                    "frame": dims["frame"],
                }
            )
        for index, rating in enumerate(mccb_outputs, 1):
            dims = get_mccb_dims(rating, active_db)
            schedule_rows.append(
                {
                    "tag": f"O/G {index}",
                    "description": "Outgoing MCCB",
                    "rating": f"{rating}A",
                    "poles": f"{num_poles}P",
                    "dimensions": f"{dims['h']}×{dims['w']}×{dims['d']}",
                    "frame": dims["frame"],
                }
            )

        return {
            "ok": True,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "inputs": {
                "theme": theme,
                "solar_kw": solar_kw,
                "grid_kw": grid_kw,
                "num_dg": num_dg,
                "dg_ratings": dg_ratings,
                "num_outputs": num_outputs,
                "outgoing_ratings": outgoing_ratings,
                "busbar_material": busbar_material,
                "num_poles": num_poles,
            },
            "summary": {
                "i_solar": system_calcs.i_solar,
                "i_grid": system_calcs.i_grid,
                "dg_currents": system_calcs.dg_currents,
                "dg_mccbs": system_calcs.dg_mccbs,
                "mccb_solar": system_calcs.mccb_solar,
                "mccb_grid": system_calcs.mccb_grid,
                "total_busbar_current": total_busbar_current,
                "total_outgoing_rating": total_outgoing_rating,
                "busbar_spec": busbar_spec,
                "warning_flag": warning_flag,
                "busbar_chamber_height": get_busbar_chamber_height(total_busbar_current),
                "busbar_thickness": get_busbar_thickness(total_busbar_current),
            },
            "sld": {
                "svg": sld_svg,
                "width": sld_svg_w,
                "height": sld_svg_h,
            },
            "ga": {
                "svg": ga_svg_str,
                "width": ga_svg_w,
                "height": ga_svg_h,
                "panel_w": panel_w,
                "panel_h": panel_h,
                "panel_d": panel_d,
            },
            "incomer_list": incomer_list,
            "mccb_outputs": mccb_outputs,
            "bom_rows": bom_rows,
            "bom_objects": bom_objects,
            "schedule_rows": schedule_rows,
        }

    def build_pdf_report(self, payload):
        design = self.compute_design(payload)
        sld_svg_light, sld_w_light, sld_h_light = self._generate_sld_light(design)
        ga_svg_light, ga_w_light, ga_h_light = self._generate_ga_svg_light(design)

        return generate_pdf_report(
            sld_svg_light,
            sld_w_light,
            sld_h_light,
            ga_svg_light,
            ga_w_light,
            ga_h_light,
            design["incomer_list"],
            design["mccb_outputs"],
            design["bom_objects"],
            design["inputs"]["solar_kw"],
            design["inputs"]["grid_kw"],
            design["inputs"]["num_dg"],
            design["inputs"]["num_outputs"],
            design["summary"]["total_busbar_current"],
            design["summary"]["total_outgoing_rating"],
            design["summary"]["busbar_spec"],
            design["ga"]["panel_w"],
            design["ga"]["panel_h"],
            design["ga"]["panel_d"],
            design["inputs"]["num_poles"],
            self._active_db(),
            design["summary"]["warning_flag"],
        )

    def build_ga_pdf(self, payload):
        design = self.compute_design(payload)
        ga_svg_light, ga_w_light, ga_h_light = self._generate_ga_svg_light(design)

        return generate_ga_pdf(
            ga_svg_light,
            ga_w_light,
            ga_h_light,
            design["incomer_list"],
            design["mccb_outputs"],
            design["ga"]["panel_w"],
            design["ga"]["panel_h"],
            design["ga"]["panel_d"],
            design["inputs"]["num_poles"],
            self._active_db(),
        )

    def build_excel_bom(self, payload):
        design = self.compute_design(payload)
        return generate_excel_bom(design["bom_objects"])

    def _generate_sld_light(self, design):
        inputs = design["inputs"]
        summary = design["summary"]

        system_calcs = SystemCalculations(
            solar_kw=inputs["solar_kw"],
            grid_kw=inputs["grid_kw"],
            dg_ratings_kva=inputs.get("dg_ratings", []),
        )

        theme_colors = get_theme_colors("light")
        sld_svg, sld_w, sld_h = generate_sld(
            system_calcs,
            inputs["num_outputs"],
            design["mccb_outputs"],
            inputs["num_poles"],
            inputs["num_dg"],
            inputs["grid_kw"],
            inputs["solar_kw"],
            summary["total_busbar_current"],
            theme_colors["svg_bg"],
            theme_colors["text"],
            theme_colors["svg_stroke"],
            theme_colors["subtitle"],
        )
        return self._normalize_export_svg_light(sld_svg), sld_w, sld_h

    def _generate_ga_svg_light(self, design):
        inputs = design["inputs"]
        summary = design["summary"]

        ga_svg_str, ga_w, ga_h, _, _, _ = generate_ga_svg(
            design["incomer_list"],
            design["mccb_outputs"],
            summary["total_busbar_current"],
            summary["busbar_spec"],
            inputs["num_poles"],
            inputs["busbar_material"],
            self._active_db(),
            theme="light",
        )
        return self._normalize_export_svg_light(ga_svg_str), ga_w, ga_h

    def _normalize_export_svg_light(self, svg_text):
        replacements = {
            "#020617": "#ffffff",
            "#0a0f1e": "#ffffff",
            "#08121f": "#f1f5f9",
            "#0a1a2e": "#f8fafc",
            "#1a2e4a": "#e2e8f0",
            "#1e4080": "#cbd5e1",
            "#334155": "#cbd5e1",
            "#2563eb": "#94a3b8",
            "#94a3b8": "#64748b",
            "#6366f1": "#475569",
            "#a78bfa": "#7c3aed",
            "#c4b5fd": "#7c3aed",
        }

        normalized = svg_text
        for dark_color, light_color in replacements.items():
            normalized = re.sub(re.escape(dark_color), light_color, normalized, flags=re.IGNORECASE)
        return normalized