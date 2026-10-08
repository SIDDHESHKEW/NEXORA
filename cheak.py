import os
from dotenv import load_dotenv
    
load_dotenv()

print("GEMINI_API_KEY_1 exists:", bool(os.getenv("GEMINI_API_KEY_1")))
print("GEMINI_API_KEY_1 length:", len(os.getenv("GEMINI_API_KEY_1", "")))