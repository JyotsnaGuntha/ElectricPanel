"""
Desktop entry point for the pywebview application.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from api.bridge import MicrogridBridge


def resource_path(*parts: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path.joinpath(*parts)


def _get_window_bounds() -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    screen_width = int(user32.GetSystemMetrics(0))
    screen_height = int(user32.GetSystemMetrics(1))

    width = min(1400, max(1120, screen_width - 80))
    height = min(900, max(720, screen_height - 80))
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    return width, height, x, y


def main():
    os.environ.setdefault("QT_API", "pyside6")

    import webview

    bridge = MicrogridBridge()
    ui_path = resource_path("ui", "index.html")
    icon_path = resource_path("assets", "microgrid-panel-icon.ico")
    width, height, x, y = _get_window_bounds()
    webview.create_window(
        "Microgrid Panel Designer",
        ui_path.as_uri(),
        js_api=bridge,
        width=width,
        height=height,
        x=x,
        y=y,
        min_size=(1024, 720),
        icon=str(icon_path),
        background_color="#0f172a",
    )
    webview.start(gui="qt", debug=False)

if __name__ == "__main__":
    main()