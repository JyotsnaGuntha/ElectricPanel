# Architecture - Microgrid Panel Designer

## 1. System Overview

Microgrid Panel Designer is a desktop engineering tool that combines:
- Python backend for calculations, SVG generation, and exports
- pywebview bridge layer for frontend-backend communication
- HTML/CSS/JavaScript frontend for user interaction

Core outputs:
- SLD (Single Line Diagram)
- GA (General Arrangement)
- BOM (Bill of Materials)
- Export files: Report PDF, GA PDF, BOM Excel

## 2. Layered Architecture

### Layer A: Desktop Host
- `main.py`: creates the desktop window and wires the JS API bridge.
- `app.py`, `run_app.py`: compatibility launchers forwarding to `main.py`.

Responsibilities:
- Startup
- Window sizing/placement
- UI file loading (`ui/index.html`)
- pywebview event loop startup

### Layer B: Integration/API Bridge
- `api/bridge.py`

Responsibilities:
- Receives payloads from frontend
- Maintains app state (`last_payload`, theme, MCCB DB)
- Orchestrates design generation via domain layer
- Handles export actions and native save dialog
- Enforces light-style rendering in exports while preserving UI theming

Public bridge methods used by frontend:
- `get_state()`
- `set_theme(theme)`
- `generate(payload)`
- `export_pdf(payload)`
- `export_ga_pdf(payload)`
- `export_excel(payload)`

### Layer C: Core Adapters
- `core/bom.py`
- `core/ga.py`
- `core/sld.py`
- `core/utils.py`
- `core/constants.py`

Responsibilities:
- Compatibility wrappers re-exporting implementations from `src/`
- Stable import surface for bridge layer

### Layer D: Domain/Engineering Logic
- `src/constants.py`: standards, ratings, geometry constants, theme palettes
- `src/utils.py`: shared numeric/util helpers, theme/color utility functions
- `src/sld/*`: SLD-specific calculations and SVG rendering
- `src/ga/*`: GA dimension calculations, styles, SVG rendering
- `src/bom/*`: BOM item generation and export rendering utilities

Responsibilities:
- Electrical calculations
- Mechanical/layout calculations
- Diagram generation
- BOM generation and file exports

### Layer E: Frontend UI
- `ui/index.html`: static structure and control IDs
- `ui/style.css`: layout, themes, responsive behavior
- `ui/app.js`: state management, event binding, API calls, rendering

Responsibilities:
- Collect user inputs
- Trigger generation/export actions
- Render summary metrics + SLD/GA previews
- Theme toggle UX

## 3. Data Flow

### 3.1 Generation Flow
1. User updates input fields in UI.
2. `ui/app.js` builds payload and calls `window.pywebview.api.generate(payload)`.
3. `api/bridge.py` validates/normalizes payload.
4. Bridge invokes domain logic from `core/*`/`src/*`.
5. Domain returns computed values, SVG strings, BOM rows, schedules.
6. Frontend renders returned summary and diagrams.

### 3.2 Export Flow
1. User clicks export action in UI.
2. `ui/app.js` calls matching bridge export method.
3. Bridge computes/collects design data.
4. Bridge prepares export output (PDF/Excel).
5. Bridge opens native save dialog and writes selected file path.

## 4. Theme Behavior Model

- UI theme is user-controlled (light/dark).
- Export outputs are normalized to light-style visuals for print/readability.
- Theme state is retained in bridge and synchronized with frontend.

## 5. Files and Responsibilities

### Top-level runtime files
- `main.py`: primary entry point
- `app.py`: launcher alias
- `run_app.py`: launcher alias
- `requirements.txt`: dependency list

### Packaging/build files
- `main.spec`, `app.spec`, `run_app.spec`: PyInstaller specs

### Assets
- `Kirloskar Oil Engine Logo.png`
- `Kirloskar Oil Engine Logo_1.png`

## 6. Key Design Decisions

1. pywebview chosen for desktop UI with web frontend flexibility.
2. Domain logic isolated under `src/` for maintainability.
3. `core/` wrappers preserve compatibility and clean imports.
4. Bridge acts as a strict orchestration boundary.
5. Export rendering forced to light-style for consistent documents.

## 7. Operational Notes

### Local Run
```bash
python main.py
```

### Optional Packaging
```bash
pyinstaller --noconfirm --clean main.spec
```

### Repository Hygiene
- Keep generated artifacts out of source control:
  - `__pycache__/`
  - `*.pyc`
  - `build/`
  - `dist/`
  - temporary export files

## 8. Extension Points

- Add new export type: implement bridge method + backend generator + UI button.
- Add new input parameter: update `ui/index.html`, `ui/app.js`, and bridge normalization.
- Add new engineering rule: update `src/constants.py` + relevant `src/*` module.

## 9. Risks and Constraints

- Tight coupling between UI element IDs and JS event bindings.
- pywebview backend behavior depends on installed GUI backend.
- Export quality depends on SVG rendering pipeline and color normalization.

## 10. Quick Map

- Start here: `main.py`
- Runtime orchestration: `api/bridge.py`
- Engineering logic: `src/`
- UI behavior: `ui/app.js`
- UI layout/style: `ui/index.html`, `ui/style.css`
