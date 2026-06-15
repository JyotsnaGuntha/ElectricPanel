from api.bridge import MicrogridBridge
bridge = MicrogridBridge()
payload = {
    "solar_kw": 100,
    "grid_kw": 120,
    "num_dg": 2,
    "dg_ratings": [250, 250],
    "num_outputs": 3,
    "outgoing_ratings": [400, 400, 250],
    "busbar_material": "Aluminium",
    "num_poles": 4
}
res = bridge.generate(payload)
print("Is ok:", res.get("ok"))
if res.get("ok"):
    ga = res.get("ga", {})
    print("Panel width (panel_w):", ga.get("panel_w"))
    print("Panel height (panel_h):", ga.get("panel_h"))
    print("Panel depth (panel_d):", ga.get("panel_d"))
