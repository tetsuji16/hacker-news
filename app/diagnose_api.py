import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

log_path = "output/diagnose_v2.log"
with open(log_path, "w", encoding="utf-8") as f:
    f.write(f"API Key: {API_KEY[:5]}...{API_KEY[-5:]}\n")

    try:
        f.write("\nTesting ALL available models...\n")
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        for m_name in models:
            try:
                f.write(f"Testing {m_name}...")
                model = genai.GenerativeModel(m_name)
                response = model.generate_content("Say 'OK'")
                f.write(f" SUCCESS: {response.text.strip()}\n")
                # If success, we found a working model!
                f.write(f"!!! FOUND WORKING MODEL: {m_name} !!!\n")
            except Exception as e:
                f.write(f" FAILED: {str(e)[:100]}...\n")
            time.sleep(1) # Sleep to avoid rate limit
                
    except Exception as e:
        f.write(f"Error in diagnostic script: {e}\n")
