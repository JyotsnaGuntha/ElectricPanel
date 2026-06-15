from api.bridge import MicrogridBridge
import os

def test():
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
    
    print("Testing generate...")
    res = bridge.generate(payload)
    print("Generate ok:", res.get("ok"))
    if not res.get("ok"):
        print("error:", res.get("error"))
        return
        
    print("Testing export_excel...")
    # Mock _save_export_file to just return the bytes
    bridge._save_export_file = lambda data, filename, file_types: {"ok": True, "bytes_len": len(data)}
    
    excel_res = bridge.export_excel(payload)
    print("Excel export ok:", excel_res.get("ok"), "Bytes:", excel_res.get("bytes_len"))
    
    print("Testing export_pdf...")
    pdf_res = bridge.export_pdf(payload)
    print("PDF export ok:", pdf_res.get("ok"), "Bytes:", pdf_res.get("bytes_len"))
    
    print("Testing export_ga_pdf...")
    ga_pdf_res = bridge.export_ga_pdf(payload)
    print("GA PDF export ok:", ga_pdf_res.get("ok"), "Bytes:", ga_pdf_res.get("bytes_len"))

if __name__ == "__main__":
    test()
