import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"ID: {m.name}, Display: {m.display_name}")
    else:
        print(f"SKIP: {m.name} (Methods: {m.supported_generation_methods})")
