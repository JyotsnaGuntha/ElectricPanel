from api.bridge import MicrogridBridge
bridge = MicrogridBridge()
payload = {
    "solar_kw": 250,
    "grid_kw": 250,
    "num_dg": 2,
    "dg_ratings": [250, 250],
    "num_outputs": 2,
    "outgoing_ratings": [250, 250],
    "busbar_material": "Aluminium",
    "num_poles": 3
}
res = bridge.generate(payload)
if res.get("ok"):
    svg_str = res["ga"]["svg"]
    with open("scratch/ga_drawing.svg", "w", encoding="utf-8") as f:
        f.write(svg_str)
    print("GA Drawing SVG saved successfully!")
else:
    print("Error:", res.get("error"))
