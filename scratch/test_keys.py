import os
from dotenv import load_dotenv
load_dotenv()
print("Llama key:", os.getenv("LLAMA_CLOUD_API_KEY"))
print("Gemini key:", os.getenv("GEMINI_KEY"))

try:
    from llama_parse import LlamaParse
    parser = LlamaParse(api_key=os.getenv("LLAMA_CLOUD_API_KEY"), result_type="markdown")
    print("LlamaParse initialized successfully")
except Exception as e:
    print("LlamaParse init failed:", e)

try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")
    print("Gemini initialized successfully")
    response = model.generate_content("Hello")
    print("Gemini response:", response.text)
except Exception as e:
    print("Gemini failed:", e)
