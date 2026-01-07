import streamlit as st
import json
import sqlite3
import re
import io
import os
import time
from datetime import datetime
from typing import List, Optional

# --- LIBRARY INTI ---
import google.generativeai as genai
from PIL import Image
from pydantic import BaseModel

# Cek Library Mic
try:
    from streamlit_mic_recorder import speech_to_text
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False

# ==========================================
# 1. KONFIGURASI HALAMAN (SEO & MOBILE)
# ==========================================
st.set_page_config(
    page_title="SkoolMath AI 2.0",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': 'https://www.google.com',
        'About': "# SkoolMath AI\nAsisten matematika cerdas."
    }
)

# ==========================================
# 2. KONFIGURASI API (SAFE MODE)
# ==========================================
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    API_KEY = os.getenv("GOOGLE_API_KEY", "")

API_READY = False
if API_KEY and "MASUKKAN" not in API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        API_READY = True
    except Exception as e:
        st.error(f"⚠️ Konfigurasi API Gagal: {e}")

# ==========================================
# 3. DESIGN CSS (MOBILE OPTIMIZED)
# ==========================================
def set_design():
    st.markdown("""
    <style>
    /* DESKTOP STYLES */
    @keyframes gradient-animation {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .stApp {
        background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
        background-size: 400% 400%;
        animation: gradient-animation 15s ease infinite;
        color: #2c3e50;
    }
    div[data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        color: #111;
    }
    h1.title-glow { color: white; text-shadow: 0 0 10px rgba(0,0,0,0.3); }
    
    /* MOBILE OPTIMIZATION */
    @media only screen and (max-width: 600px) {
        .stApp {
            animation: none !important;
            background: #ffffff !important;
        }
        div[data-testid="stChatMessage"] {
            border: 1px solid #eee !important;
            box-shadow: none !important;
        }
        h1.title-glow { color: #333 !important; text-shadow: none !important; }
        .rainbow-line { display: none !important; }
    }
    
    .rainbow-line {
        height: 4px; border-radius: 10px; margin: 15px 0 25px 0;
        background: linear-gradient(90deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 200% auto; animation: slide 3s linear infinite;
    }
    @keyframes slide { to { background-position: 200% center; } }
    </style>
    """, unsafe_allow_html=True)

set_design()

# ==========================================
# 4. DATABASE
# ==========================================
def clean_json_output(text):
    # Hapus markdown block ```json ... ```
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    return text

def init_db():
    conn = sqlite3.connect('math_premium.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS memory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user_input TEXT, ai_json TEXT)''')
    conn.commit()
    conn.close()

def save_to_memory(user_input, ai_json_str):
    conn = sqlite3.connect('math_premium.db')
    c = conn.cursor()
    c.execute("INSERT INTO memory (timestamp, user_input, ai_json) VALUES (?, ?, ?)", 
              (datetime.now().isoformat(), user_input, ai_json_str))
    conn.commit()
    conn.close()

def search_memory(query_text):
    conn = sqlite3.connect('math_premium.db')
    c = conn.cursor()
    words = query_text.split() if query_text else []
    if not words: return None, None
    keyword = max(words, key=len) 
    c.execute("SELECT user_input, ai_json FROM memory WHERE user_input LIKE ? ORDER BY id DESC LIMIT 1", ('%' + keyword + '%',))
    result = c.fetchone()
    conn.close()
    return (result[0], result[1]) if result else (None, None)

init_db()

# ==========================================
# 5. PROMPT & SCHEMA (PERBAIKAN UTAMA DISINI)
# ==========================================
SYSTEM_PROMPT = """
INSTRUKSI: Anda adalah AI Math Tutor Genius. Selesaikan soal & Output JSON STRICT.

ATURAN KRUSIAL JSON (WAJIB PATUH):
1. Jangan gunakan markdown di dalam string JSON.
2. SANGAT PENTING: Jika menulis rumus LaTeX (seperti akar, pecahan, greek letters), GUNAKAN DOUBLE BACKSLASH (\\\\).
   - SALAH: "\sqrt{x}" atau "\pi" (Ini akan menyebabkan error JSON Invalid \escape)
   - BENAR: "\\sqrt{x}" atau "\\pi"
   - BENAR: "\\frac{1}{2}"
3. Pastikan string ditutup dengan benar.

FORMAT JSON TARGET:
{
  "answer": { "text": "Jawaban akhir...", "latex": "Rumus akhir...", "format": "numeric/text" },
  "solution": { 
      "steps": ["Langkah 1 (Gunakan LaTeX Double Backslash)", "Langkah 2..."], 
      "plot_expression": "None atau rumus numpy valid (misal: x**2)" 
  },
  "pedagogy": { "hints": ["..."], "common_mistakes": ["..."], "practice_problems": ["..."] },
  "metadata": { "created_at": "..." }
}
"""

class MathSchema(BaseModel):
    pass 

# ==========================================
# 6. FUNGSI GENERATOR
# ==========================================
def generate_pdf(data_dict, user_soal):
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Solusi SkoolMath AI", ln=True, align='C'); pdf.ln(10)
    pdf.multi_cell(0, 10, f"Soal: {user_soal[:200]}")
    pdf.ln(5)
    pdf.multi_cell(0, 10, f"Jawaban: {data_dict['answer']['text']}")
    pdf.ln(5); pdf.cell(0, 10, "Langkah:", ln=True)
    for i, step in enumerate(data_dict['solution']['steps']):
        clean = step.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, f"{i+1}. {clean}")
    return pdf.output(dest='S').encode('latin-1')

def generate_audio(text):
    from gtts import gTTS
    try:
        tts = gTTS(text=text, lang='id')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except: return None

# ==========================================
# 7. LOGIKA AI (TRIPLE FALLBACK)
# ==========================================
def get_ai_response(user_input, image_input=None):
    if not API_READY:
        return json.dumps({"error": "⚠️ API Key bermasalah."}), "Error API"

    soal_mirip, jawaban_mirip = search_memory(user_input) if user_input else (None, None)
    rag_context = ""
    debug_msg = "🧠 Logika"
    if soal_mirip:
        debug_msg = "📚 Memori"
        rag_context = f"[CONTOH LALU]\nSoal: {soal_mirip}\nJawab: {jawaban_mirip}\nTIRU FORMAT."

    final_prompt = f"{SYSTEM_PROMPT}\n{rag_context}\n\nUSER INPUT:\n{user_input}"

    model_list = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-flash-latest"]
    max_retries = 2

    for model_name in model_list:
        for attempt in range(max_retries):
            try:
                # Matikan safety filter agar soal biologi/anatomi/math tidak dianggap bahaya
                safe_config = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
                
                model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"}, safety_settings=safe_config)
                
                if image_input:
                    response = model.generate_content([final_prompt, image_input])
                else:
                    response = model.generate_content(final_prompt)
                
                return response.text, f"{debug_msg} ({model_name})"

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower() or "503" in error_str:
                    time.sleep(1 + attempt)
                    continue 
                else:
                    break 
    
    return json.dumps({"error": "⚠️ Server Sibuk. Coba 1 menit lagi."}), "Error 429"

# ==========================================
# 8. TAMPILAN UTAMA
# ==========================================
st.markdown('<h1 class="title-glow">🧠 SkoolMath AI | 2.0</h1>', unsafe_allow_html=True)
st.caption("Powered By: Gemini Flash")

if "messages" not in st.session_state: st.session_state.messages = []
if "last_uploaded_file" not in st.session_state: st.session_state.last_uploaded_file = None
if len(st.session_state.messages) > 8: st.session_state.messages = st.session_state.messages[-8:]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            try:
                data = json.loads(message["content"])
                if "error" in data: st.error(data["error"])
                else:
                    st.write(f"**Jawab:** {data['answer']['text']}")
                    with st.expander("📝 Langkah"):
                        for s in data['solution']['steps']: st.write(f"- {s}")
            except: 
                # Jika JSON gagal parsing, tampilkan raw text sebagai fallback
                st.warning("⚠️ Format data mentah (Non-JSON):")
                st.write(message["content"])
        else: st.write(message["content"])

st.markdown('<div class="rainbow-line"></div>', unsafe_allow_html=True)
c_tools, c_info = st.columns([1.5, 5]) 
image_data, uploaded_file, voice_text = None, None, None

with c_tools:
    with st.popover("📎 Input", use_container_width=True):
        uploaded_file = st.file_uploader("Upload Soal", type=["jpg","png"])
        if uploaded_file:
            image_data = Image.open(uploaded_file)
            st.image(image_data, caption="Preview")
        if MIC_AVAILABLE:
            st.divider(); st.write("🎙️ Suara")
            voice_text = speech_to_text(language='id', start_prompt="🔴 Rekam", stop_prompt="⏹️ Stop")
        st.divider()
        if st.button("🗑️ Reset"):
            st.session_state.messages = []
            st.session_state.last_uploaded_file = None
            st.rerun()

user_query = st.chat_input("Ketik soal...")
final_input = None

if voice_text: final_input = voice_text
elif user_query: final_input = user_query
elif uploaded_file and image_data:
    if st.session_state.last_uploaded_file != uploaded_file.name:
        final_input = "Selesaikan soal di gambar ini."
        st.session_state.last_uploaded_file = uploaded_file.name

if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    st.rerun()

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("⏳ Sedang berpikir..."):
            raw_res, debug_info = get_ai_response(st.session_state.messages[-1]["content"], image_data)
            cleaned_res = clean_json_output(raw_res)
            
            try:
                # COBA PARSING JSON
                data = json.loads(cleaned_res)
                
                if "error" in data: st.error(data['error'])
                else:
                    save_to_memory(st.session_state.messages[-1]["content"], cleaned_res)
                    st.caption(debug_info)
                    st.success(f"**Jawaban:** {data['answer']['text']}")
                    with st.expander("📝 Langkah Lengkap", expanded=True):
                        for step in data['solution']['steps']: st.write(f"- {step}")
                        expr = data['solution'].get('plot_expression')
                        if expr and expr != "None":
                            try:
                                import numpy as np; import matplotlib.pyplot as plt
                                x = np.linspace(-10, 10, 400)
                                context = {"x": x, "np": np, "sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}
                                y = eval(expr, context)
                                fig, ax = plt.subplots(); ax.plot(x, y); ax.grid(True)
                                st.pyplot(fig); plt.close(fig)
                            except: pass
                    
                    c1, c2 = st.columns(2)
                    with c1: 
                        pdf_bytes = generate_pdf(data, st.session_state.messages[-1]["content"])
                        st.download_button("📄 PDF", pdf_bytes, "solusi.pdf", "application/pdf")
                    with c2:
                        audio_fp = generate_audio(f"Jawabannya {data['answer']['text']}")
                        if audio_fp: audio_fp.seek(0); st.audio(audio_fp, format='audio/mp3')

                    st.session_state.messages.append({"role": "assistant", "content": json.dumps(data)})
                    st.rerun()

            except json.JSONDecodeError as e:
                # FALLBACK: Jika JSON Eror (Backslash Issue), Tampilkan Teks Mentah Saja
                # Ini fitur 'Anti-Crash' agar user tetap bisa baca jawaban meski tampilan tidak sempurna
                st.error(f"⚠️ JSON Format Error (LaTeX Issue). Menampilkan jawaban mentah:")
                st.write(cleaned_res) 
                
                # Simpan mentah agar history tidak hilang
                st.session_state.messages.append({"role": "assistant", "content": cleaned_res})
            
            except Exception as e: st.error(f"Error System: {e}")
