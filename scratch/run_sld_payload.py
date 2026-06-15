from api.bridge import MicrogridBridge
from src.ga.dimensions import compute_panel_dimensions
from core.utils import get_mccb_dims

bridge = MicrogridBridge()
db = bridge.mccb_db

incomer_list = [500, 500, 630, 630]
mccb_outputs = [250, 250]

print("Individual widths from get_mccb_dims:")
for r in incomer_list + mccb_outputs:
    print(f"Rating {r}A: {get_mccb_dims(r, db)}")

dims = compute_panel_dimensions(incomer_list, mccb_outputs, db, busbar_current_A=1565.1)
print("\nDirect call to compute_panel_dimensions:")
for k, v in dims.items():
    print(f"  {k}: {v}")
