"""
Bridge between the JavaScript frontend and the Python design engine.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from api.design_service import DesignService
from src.utils import load_mccb_dimensions_from_file


class MicrogridBridge:
    """Stateful API exposed to the pywebview frontend."""

    def __init__(self):
        self.theme = "dark"
        self.mccb_db = {}
        try:
            local_db_path = Path("Circuit Breaker Dimensions.xlsx")
            if local_db_path.exists():
                from core.utils import load_mccb_dimensions_from_file
                self.mccb_db = load_mccb_dimensions_from_file(path=str(local_db_path))
        except Exception as e:
            print(f"Error auto-loading local MCCB DB: {e}")
        self.last_payload = self._default_payload()
        self.design_service = DesignService(theme=self.theme, mccb_db=self.mccb_db)

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
        return self.design_service._active_db()

    def get_state(self):
        payload = dict(self.last_payload)
        payload["theme"] = self.theme
        return payload

    def set_theme(self, theme):
        if theme in ("dark", "light"):
            self.theme = theme
            self.design_service.set_theme(theme)
        return {"ok": True, "theme": self.theme}

    def generate(self, payload=None):
        try:
            self.design_service.set_theme(self.theme)
            self.design_service.set_mccb_db(self.mccb_db)
            design = self.design_service.compute_design(payload or self.last_payload)
            self.last_payload = dict(design["inputs"])
            self.last_payload["theme"] = self.theme
            response = dict(design)
            response["bom_objects"] = design["bom_rows"]
            return response
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def analyze_bills(self, payload=None):
        try:
            payload = payload or {}
            files = payload.get("files") or []
            analysis = self.design_service.analyze_bills(files)
            return {
                "ok": True,
                "recommended_kw": analysis["recommended_kw"],
                "recommended_bess_kwh": analysis["recommended_bess_kwh"],
                "average_monthly_op_units": analysis["average_monthly_op_units"],
                "average_hourly_op_units": analysis["average_hourly_op_units"],
                "months": analysis["months"],
                "bill_data": analysis.get("bill_data", []),
            }
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def pick_bill_files(self):
        try:
            import webview

            if not webview.windows:
                return {"ok": False, "error": "Application window is not available."}

            dialog_result = webview.windows[0].create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=True,
                file_types=("PDF Files (*.pdf)",),
            )
            if not dialog_result:
                return {"ok": False, "cancelled": True}

            files = []
            for file_path in dialog_result:
                path = Path(file_path)
                if path.suffix.lower() != ".pdf" or not path.exists():
                    continue
                files.append({
                    "name": path.name,
                    "size": path.stat().st_size,
                    "type": "application/pdf",
                    "content": base64.b64encode(path.read_bytes()).decode("ascii"),
                })

            if not files:
                return {"ok": False, "error": "No PDF files were selected."}

            return {"ok": True, "files": files}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def export_pdf(self, payload=None):
        try:
            self.design_service.set_theme(self.theme)
            self.design_service.set_mccb_db(self.mccb_db)
            pdf_buffer = self.design_service.build_pdf_report(payload or self.last_payload)
            return self._save_export_file(
                pdf_buffer.getvalue(),
                "microgrid_panel_report.pdf",
                ("PDF Files (*.pdf)",),
            )
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def export_ga_pdf(self, payload=None):
        try:
            self.design_service.set_theme(self.theme)
            self.design_service.set_mccb_db(self.mccb_db)
            pdf_buffer = self.design_service.build_ga_pdf(payload or self.last_payload)
            return self._save_export_file(
                pdf_buffer.getvalue(),
                "microgrid_panel_ga.pdf",
                ("PDF Files (*.pdf)",),
            )
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def export_excel(self, payload=None):
        try:
            self.design_service.set_theme(self.theme)
            self.design_service.set_mccb_db(self.mccb_db)
            excel_bytes = self.design_service.build_excel_bom(payload or self.last_payload)
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

