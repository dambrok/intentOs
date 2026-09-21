import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

models = genai.list_models()

print("\nAVAILABLE MODELS FOR YOUR API KEY:\n")

for m in models:
    print("Model name:", m.name)
    print("  Supported methods:", m.supported_generation_methods)
    print("-" * 60)
