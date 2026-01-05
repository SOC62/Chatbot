import google.generativeai as genai

# === MASUKKAN API KEY ANDA DI SINI ===
API_KEY = "AIzaSyCdnrVDnT6WuCHSHcu0HNP7dF2epWtNKms"

genai.configure(api_key=API_KEY)

print("Sedang mengecek model yang tersedia...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- Ditemukan: {m.name}")
except Exception as e:
    print(f"Eror: {e}")

print("Selesai.")