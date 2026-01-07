import streamlit as st
import json
import sqlite3
import re
import io
import os
from datetime import datetime
from typing import List, Optional

# --- LIBRARY PREMIUM ---
import google.generativeai as genai
from PIL import Image
from pydantic import BaseModel
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
from gtts import gTTS

# Cek Library Mic
try:
    from streamlit_mic_recorder import speech_to_text
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="SkoolMath AI", layout="wide", page_icon="🧠")

# ==========================================
# 2. KONFIGURASI API (SAFE MODE)
# ==========================================
# Prioritas: Ambil dari Secrets (Cloud). Jika tidak ada, cek Environment Variable.
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Validasi awal (jangan crash, simpan statusnya saja)
API_READY = False
if API_KEY and "MASUKKAN" not in API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        API_READY = True
    except Exception as e:
        st.error(f"⚠️ Konfigurasi API Gagal: {e}")

# ==========================================
# 3. DESIGN CSS (ANIMATED)
# ==========================================
def set_design():
    st.markdown("""
    <style>
    /* Background Bergerak */
    @keyframes gradient-animation {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .stApp {
        background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
        background-size: 400% 400%;
        animation: gradient-animation 15s ease infinite;
    }
    /* Kartu Chat Glassmorphism */
    div[data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(12px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.5);
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    /* Rainbow Line */
    .rainbow-line {
        height: 6px;
        border-radius: 10px;
        background: linear-gradient(90deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 200% auto;
        animation: slide 3s linear infinite;
        margin-top: 15px;
        margin-bottom: 25px;
    }
    @keyframes slide { to { background-position: 200% center; } }
    
    /* Tombol Popover */
    div[data-testid="stPopover"] > button {
        background-color: white !important;
        color: #333 !important;
        border: none !important;
        border-radius: 50px !important;
        font-weight: bold !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important;
        transition: transform 0.2s;
    }
    div[data-testid="stPopover"] > button:hover {
        transform: scale(1.05);
        color: #e73c7e !important;
    }
    /* Text Color Fix */
    p, span, div, h1, h2, h3 { color: #2c3e50; }
    h1 { color: white; text-shadow: 0 0 10px rgba(0,0,0,0.3); }
    </style>
    """, unsafe_allow_html=True)

set_design()

# ==========================================
# 4. DATABASE & UTILITY
# ==========================================
def clean_json_output(text):
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return text.strip()

def init_db():
    conn = sqlite3.connect('math_premium.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS memory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp TEXT, 
                  user_input TEXT, 
                  ai_json TEXT)''')
    conn.commit()
    conn.close()

def save_to_memory(user_input, ai_json_str):
    conn = sqlite3.connect('math_premium.db')
    c = conn.cursor()
    ts = datetime.now().isoformat()
    c.execute("INSERT INTO memory (timestamp, user_input, ai_json) VALUES (?, ?, ?)", 
              (ts, user_input, ai_json_str))
    conn.commit()
    conn.close()

def search_memory(query_text):
    conn = sqlite3.connect('math_premium.db')
    c = conn.cursor()
    words = query_text.split() if query_text else []
    if not words: return None, None
    keyword = max(words, key=len) 
    c.execute("SELECT user_input, ai_json FROM memory WHERE user_input LIKE ? ORDER BY id DESC LIMIT 1", 
              ('%' + keyword + '%',))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0], result[1]
    return None, None

init_db()

# ==========================================
# 5. SYSTEM PROMPT & SCHEMA
# ==========================================
SYSTEM_PROMPT = """
INSTRUKSI: Anda adalah AI Math Tutor. Selesaikan soal (Teks/Gambar) & Output JSON STRICT.
FITUR: Plot expression untuk fungsi, 3 soal latihan mirip, penjelasan Bahasa Indonesia.

FORMAT JSON:
{
  "answer": { "text": "...", "latex": "...", "format": "numeric" },
  "solution": { "steps": ["..."], "plot_expression": "None atau rumus numpy valid" },
  "pedagogy": { "hints": ["..."], "common_mistakes": ["..."], "practice_problems": ["..."] },
  "metadata": { "created_at": "..." }
}
"""

class Answer(BaseModel): text: Optional[str] = None; latex: Optional[str] = None; format: str
class Solution(BaseModel): steps: List[str]; plot_expression: Optional[str] = None
class Pedagogy(BaseModel): hints: List[str]; common_mistakes: List[str]; practice_problems: Optional[List[str]] = None
class Metadata(BaseModel): created_at: str
class MathSchema(BaseModel):
    answer: Answer; solution: Solution; pedagogy: Pedagogy; metadata: Metadata

# ==========================================
# 6. FUNGSI GENERATOR
# ==========================================
def generate_pdf(data_dict, user_soal):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Solusi SkoolMath AI", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', size=12)
    pdf.cell(0, 10, f"Soal: {user_soal[:100]}...", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, f"Jawaban: {data_dict['answer']['text']}")
    pdf.ln(5)
    pdf.set_font("Arial", 'B', size=12)
    pdf.cell(0, 10, "Langkah:", ln=True)
    pdf.set_font("Arial", size=11)
    for i, step in enumerate(data_dict['solution']['steps']):
        clean_step = step.replace("∫", "int").encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, f"{i+1}. {clean_step}")
    return pdf.output(dest='S').encode('latin-1')

def generate_audio(text):
    try:
        tts = gTTS(text=text, lang='id')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except: return None

# ==========================================
# 7. LOGIKA AI (ROBUST)
# ==========================================
def get_ai_response(user_input, image_input=None):
    # Cek Kesiapan API
    if not API_READY:
        return json.dumps({"error": "⚠️ API Key bermasalah/expired. Cek Secrets Streamlit."}), "Error API"

    # RAG Logic
    soal_mirip, jawaban_mirip = search_memory(user_input) if user_input else (None, None)
    rag_context = ""
    debug_msg = "🧠 Logika Baru"
    if soal_mirip:
        debug_msg = f"📚 Memori: Mirip '{soal_mirip[:15]}...'"
        rag_context = f"[CONTOH LALU]\nSoal: {soal_mirip}\nJawab: {jawaban_mirip}\nTIRU FORMAT."

    final_prompt = f"{SYSTEM_PROMPT}\n{rag_context}\n\nUSER INPUT:\n{user_input}"

    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
        if image_input:
            debug_msg += " + 👁️ Vision"
            response = model.generate_content([final_prompt, image_input])
        else:
            response = model.generate_content(final_prompt)
        return response.text, debug_msg
    except Exception as e:
        # Tangkap error detail dari Google
        return json.dumps({"error": f"Server Error: {str(e)}"}), "Error System"

# ==========================================
# 8. LAYOUT & LOGIKA UTAMA
# ==========================================
st.title("🧠 SkoolMath AI | 2.0")
st.caption("Powered By: Gemini Flash")

# Container Chat
chat_container = st.container()

# State Management
if "messages" not in st.session_state: st.session_state.messages = []
if "last_uploaded_file" not in st.session_state: st.session_state.last_uploaded_file = None

# Tampilkan Chat
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                try:
                    data = json.loads(message["content"])
                    if "error" in data: 
                        st.error(data["error"])
                    else:
                        st.write(f"**Jawab:** {data['answer']['text']}")
                        with st.expander("📝 Langkah"):
                             for s in data['solution']['steps']: st.write(f"- {s}")
                except: st.write(message["content"])
            else: st.write(message["content"])
    st.write(" ") 

# --- TOOLBAR ---
st.markdown('<div class="rainbow-line"></div>', unsafe_allow_html=True)
c_tools, c_info = st.columns([1.5, 5]) 

image_data = None  # Default value agar tidak error "undefined"
uploaded_file = None
voice_text = None

with c_tools:
    with st.popover("📎 Alat Input", use_container_width=True):
        st.write("### 📸 Upload & Suara")
        uploaded_file = st.file_uploader("Upload Soal", type=["jpg", "png", "jpeg"])
        
        if uploaded_file:
            image_data = Image.open(uploaded_file)
            st.success("Foto Oke!")
            st.image(image_data, caption="Preview", use_container_width=True)
        
        st.divider()
        if MIC_AVAILABLE:
            st.write("🎙️ **Rekam**")
            voice_text = speech_to_text(language='id', start_prompt="🔴 Rekam", stop_prompt="⏹️ Stop")
        
        st.divider()
        if st.button("🗑️ Reset Chat"):
            try:
                os.remove("math_premium.db"); init_db()
                st.session_state.messages = []
                st.session_state.last_uploaded_file = None
                st.rerun()
            except: pass

with c_info:
    if uploaded_file: st.info(f"📸 File: {uploaded_file.name}")
    elif voice_text: st.info(f"🎙️ Suara: '{voice_text}'")
    else: st.caption("Klik tombol '📎 Alat Input' untuk upload foto/rekam suara.")

# --- INPUT & EKSEKUSI ---
user_query = st.chat_input("Ketik soal matematika...")

final_input = None

# Prioritas Input
if voice_text: 
    final_input = voice_text
elif user_query: 
    final_input = user_query
elif uploaded_file and image_data:
    # Cek Loop
    if st.session_state.last_uploaded_file != uploaded_file.name:
        final_input = "Selesaikan soal di gambar ini."
        st.session_state.last_uploaded_file = uploaded_file.name
    else:
        final_input = None

if final_input:
    # Simpan user input
    st.session_state.messages.append({"role": "user", "content": final_input})
    st.rerun()

# Proses Jawaban (JIKA pesan terakhir dari USER)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_msg = st.session_state.messages[-1]["content"]
    
    with st.chat_message("assistant"):
        with st.spinner("⏳ Sedang berpikir..."):
            # PANGGIL FUNGSI UTAMA (Di sini error Anda sebelumnya)
            # image_data otomatis None jika tidak ada upload, jadi aman.
            raw_res, debug_info = get_ai_response(last_msg, image_data)
            
            cleaned_res = clean_json_output(raw_res)

            try:
                data = json.loads(cleaned_res)
                if "error" in data:
                    st.error(data['error']) # Tampilkan error API cantik
                else:
                    save_to_memory(last_msg, cleaned_res)
                    st.caption(debug_info)
                    st.success(f"**Jawaban:** {data['answer']['text']}")
                    
                    with st.expander("📝 Langkah Lengkap", expanded=True):
                        for step in data['solution']['steps']: st.write(f"- {step}")
                        expr = data['solution'].get('plot_expression')
                        if expr and expr != "None":
                            try:
                                x = np.linspace(-10, 10, 400)
                                context = {"x": x, "np": np, "sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}
                                y = eval(expr, context)
                                fig, ax = plt.subplots(); ax.plot(x, y); ax.grid(True)
                                st.pyplot(fig)
                            except: pass

                    c1, c2 = st.columns(2)
                    with c1: st.info("**Tips:**\n" + "\n".join([f"- {h}" for h in data['pedagogy']['hints']]))
                    with c2: st.warning("**Hati-hati:**\n" + "\n".join([f"- {m}" for m in data['pedagogy']['common_mistakes']]))
                    
                    # PDF & Audio
                    col_pdf, col_audio = st.columns(2)
                    with col_pdf:
                        try:
                            pdf_bytes = generate_pdf(data, last_msg)
                            st.download_button("📄 PDF", pdf_bytes, "solusi.pdf", "application/pdf")
                        except: pass
                    with col_audio:
                        audio_fp = generate_audio(f"Jawabannya {data['answer']['text']}")
                        if audio_fp: 
                            audio_fp.seek(0)
                            st.audio(audio_fp, format='audio/mp3')

                    # Simpan ke history
                    st.session_state.messages.append({"role": "assistant", "content": json.dumps(data)})
                    st.rerun()
            except Exception as e:
                st.error(f"Error Parsing: {e}\nRaw: {cleaned_res}")





