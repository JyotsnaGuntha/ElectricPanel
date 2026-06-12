Right now it is heavily dependent on pdfplumber + regex patterns + table extraction.

switching from pdfplumber to LlamaParse because:

- Different DISCOMs use different PDF layouts.
- Some PDFs are scanned images.
- Tables are often misaligned.
- LlamaParse uses AI-based document understanding rather than just extracting text coordinates.

User Uploads PDF
       ↓
Frontend (index.html)
       ↓
Backend API
       ↓
LlamaParse
       ↓
Extract MP/NH/EP/OP/Total
       ↓
calculate_bill_recommendation()
       ↓
Return recommended_kw and recommended_bess_kwh
       ↓
Auto-fill Solar field

