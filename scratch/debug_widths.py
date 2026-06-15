from api.bridge import MicrogridBridge
from core.utils import get_mccb_dims

bridge = MicrogridBridge()
db = bridge.mccb_db

incomer_list = [500, 500, 630, 630]
mccb_outputs = [250, 250]
all_mccbs = incomer_list + mccb_outputs

for r in all_mccbs:
    w = get_mccb_dims(r, db)['w']
    print(f"Rating {r}A: width = {w}")

total_mccb_width = sum(get_mccb_dims(r, db)['w'] for r in all_mccbs)
print("Sum of widths:", total_mccb_width)
gaps = len(all_mccbs) - 1
print("Gaps:", gaps)
panel_w = 90 + total_mccb_width + 150 * gaps + 90
print("Calculated panel_w:", panel_w)
