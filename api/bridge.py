"""
Bridge between the JavaScript frontend and the Python design engine.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from core.bom import encode_file_response, generate_bom_items, generate_excel_bom, generate_ga_pdf, generate_pdf_report
from core.constants import FALLBACK_MCCB_DB, STANDARD_MCCBS
from core.ga import compute_panel_dimensions, generate_ga_svg
from core.sld import SystemCalculations, generate_sld
from core.utils import (
    calculate_current_from_kva,
    calculate_current_from_power,
    get_busbar_chamber_height,
    get_busbar_thickness,
    get_mccb_dims,
    get_standard_rating,
    get_theme_colors,
    generate_busbar_spec,
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


class MicrogridBridge:
    """Stateful API exposed to the pywebview frontend."""

    def __init__(self):
        self.theme = "dark"
        self.mccb_db = {}
        self.last_payload = self._default_payload()

    def _default_payload(self):
        return {
            "solar_kw": None,
            "grid_kw": None,
            "num_dg": None,
            "dg_ratings": [],
            "num_outputs": None,
            "outgoing_ratings": [],
            "busbar_material": "",
            "num_poles": None,
        }

    def _active_db(self):
        return self.mccb_db or FALLBACK_MCCB_DB

    def get_state(self):
        payload = dict(self.last_payload)
        payload["theme"] = self.theme
        return payload

    def set_theme(self, theme):
        if theme in ("dark", "light"):
            self.theme = theme
        return {"ok": True, "theme": self.theme}

    def generate(self, payload=None):
        try:
            design = self._compute_design(payload or self.last_payload)
            self.last_payload = dict(design["inputs"])
            self.last_payload["theme"] = self.theme
            response = dict(design)
            response["bom_objects"] = design["bom_rows"]
            return response
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def export_pdf(self, payload=None):
        try:
            design = self._compute_design(payload or self.last_payload)
            # Regenerate SVGs with light theme for export
            sld_svg_light, sld_w_light, sld_h_light = self._generate_sld_light(design)
            ga_svg_light, ga_w_light, ga_h_light = self._generate_ga_svg_light(design)
            
            pdf_buffer = generate_pdf_report(
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
            return self._save_export_file(
                pdf_buffer.getvalue(),
                "microgrid_panel_report.pdf",
                ("PDF Files (*.pdf)",),
            )
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def export_ga_pdf(self, payload=None):
        try:
            design = self._compute_design(payload or self.last_payload)
            # Regenerate GA SVG with light theme for export
            ga_svg_light, ga_w_light, ga_h_light = self._generate_ga_svg_light(design)
            
            pdf_buffer = generate_ga_pdf(
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
            return self._save_export_file(
                pdf_buffer.getvalue(),
                "microgrid_panel_ga.pdf",
                ("PDF Files (*.pdf)",),
            )
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def export_excel(self, payload=None):
        try:
            design = self._compute_design(payload or self.last_payload)
            excel_bytes = generate_excel_bom(design["bom_objects"])
            return self._save_export_file(
                excel_bytes,
                "microgrid_panel_bom.xlsx",
                ("Excel Workbook (*.xlsx)",),
            )
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def _save_export_file(self, data_bytes, default_filename, file_types):
        try:
            import webview

            if not webview.windows:
                return {"ok": False, "error": "Application window is not available."}

            dialog_result = webview.windows[0].create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=default_filename,
                file_types=file_types,
            )
            if not dialog_result:
                return {"ok": False, "error": "Save cancelled."}

            target_path = Path(dialog_result[0])
            target_path.write_bytes(data_bytes)
            return {"ok": True, "filename": target_path.name, "path": str(target_path)}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def _generate_sld_light(self, design):
        """Generate SLD SVG with light theme colors for export."""
        inputs = design["inputs"]
        summary = design["summary"]
        
        # Reconstruct SystemCalculations for SLD generation
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
        """Generate GA SVG with light theme colors for export."""
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
        """Normalize known dark hardcoded SVG colors for export output."""
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

    def _compute_design(self, payload):
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

        dg_ratings = [_as_float(value, 0) for value in dg_ratings]
        outgoing_ratings = [_as_float(value, 0) for value in outgoing_ratings]

        mccb_outputs = [get_standard_rating(value) for value in outgoing_ratings]
        system_calcs = SystemCalculations(solar_kw=solar_kw, grid_kw=grid_kw, dg_ratings_kva=dg_ratings)

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
            "generated_at": datetime.now().isoformat(timespec="seconds"),
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
                "standard_mccbs": STANDARD_MCCBS,
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
