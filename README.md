# Microgrid Panel Designer

Microgrid Panel Designer is a desktop application for electrical panel design and export generation.

Core capabilities:
- Generate SLD (Single Line Diagram)
- Generate GA (General Arrangement)
- Generate BOM (Bill of Materials)
- Export Report PDF, GA PDF, and BOM Excel

## High-Level Architecture

The system is organized into five layers:
1. Desktop host (`main.py`)
2. API bridge (`api/bridge.py`)
3. Core adapters (`core/`)
4. Domain logic (`src/`)
5. Frontend UI (`ui/`)

For full internal structure, data flow, module responsibilities, and extension points, see:
- `architecture.md`

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

## Usage

1. Fill in design inputs.
2. Click `Generate`.
3. Review outputs.
4. Export required files.

## Notes

- UI supports light/dark theme.
- Export rendering is normalized for light-style readability.
- Build artifacts should remain excluded from source control.
