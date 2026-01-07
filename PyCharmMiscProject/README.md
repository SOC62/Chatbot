# 🧮 Chatbot AI Math 

Project ini adalah Chatbot Matematika cerdas yang dibangun menggunakan Python dan Streamlit. Bot ini menggunakan model **Google Gemini 2.5 Flash** untuk menyelesaikan soal matematika, memberikan langkah-langkah penyelesaian, serta saran pedagogi (petunjuk & kesalahan umum).

Keunggulan utama bot ini adalah output-nya yang **Strictly Typed (Ketat)** sesuai standar `schema.json`, divalidasi menggunakan Pydantic.

## 🚀 Main Feature
- **Step-by-Step Solution:** Menampilkan langkah penyelesaian yang terstruktur.
- **Pedagogical Engine:** Memberikan "Hints" (Petunjuk) dan "Common Mistakes" (Kesalahan Umum).
- **Schema Compliant:** Output AI divalidasi secara otomatis agar sesuai format JSON pendidikan.
- **Auto-Model Detection:** Menggunakan model Gemini terbaru (2.5 Flash / 2.0 Flash) yang tersedia di akun.

## 🛠️ Requirement
- Python 3.8 atau lebih baru.
- Koneksi Internet (untuk akses API).

## 📦 Instalation

1. **Clone/Download** folder project.
2. Buka terminal di folder project, lalu install library yang dibutuhkan:

```bash

pip install streamlit google-generativeai pydantic

%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#ffecd2', 'edgeLabelBackground':'#ffffff', 'tertiaryColor': '#f6f6f6'}}}%%
graph TD
    %% --- STYLING ---
    classDef user fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b,rx:10,ry:10;
    classDef frontend fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#f57f17,rx:5,ry:5;
    classDef controller fill:#dcedc8,stroke:#7cb342,stroke-width:2px,color:#33691e,rx:5,ry:5;
    classDef db fill:#e1bee7,stroke:#8e24aa,stroke-width:2px,color:#4a148c,shape:cyl;
    classDef ai fill:#ffccbc,stroke:#ff5722,stroke-width:2px,color:#bf360c,rx:5,ry:5;
    classDef process fill:#cfd8dc,stroke:#607d8b,stroke-width:1px,rx:5,ry:5;
    classDef output fill:#c8e6c9,stroke:#388e3c,stroke-width:2px,color:#1b5e20,rx:10,ry:10;

    %% --- MAIN FLOW ---
    User((🧑‍🎓 Siswa/User)):::user -->|1. Input Teks, Suara, atau Gambar| UI[📱 Streamlit Frontend UI\n(Responsive Mobile/Desktop)]:::frontend

    subgraph "CONTROLLER LAYER (app.py)"
        UI -->|2. Kirim Data| Controller{⚙️ Main Controller Logic\nSession State & Lazy Loading}:::controller
        
        %% --- RAG SECTION ---
        Controller --"3. Cek Soal Mirip?"--> DB[(🗄️ SQLite Memory DB\n'math_premium.db')]:::db
        DB --"Ada (Hit)"--> Context[📄 Ambil Jawaban Lama\nsebagai Konteks (RAG)]:::process
        DB --"Tidak Ada (Miss)"--> NoContext[∅ Tanpa Konteks]:::process
        
        Context --> PromptPrep[📝 Siapkan Prompt Final\n(System + RAG + User Input + Vision)]:::process
        NoContext --> PromptPrep
    end

    %% --- AI CORE SECTION (FALLBACK SYSTEM) ---
    subgraph "AI BRAIN LAYER (Triple Fallback)"
        PromptPrep --> AI_Try1{🚀 Coba Model 1\nGemini 2.0 Flash Lite}:::ai
        
        AI_Try1 --"✅ Sukses"--> RawResp[📃 Raw AI Response\n(Teks/JSON)]:::process
        AI_Try1 --"❌ Sibuk/Limit (429)"--> AI_Try2{⚠️ Coba Model 2\nGemini 2.0 Flash}:::ai
        
        AI_Try2 --"✅ Sukses"--> RawResp
        AI_Try2 --"❌ Sibuk/Limit (429)"--> AI_Try3{🛡️ Coba Model 3\nGemini 1.5 Flash (Stabil)}:::ai
        
        AI_Try3 --"✅ Sukses"--> RawResp
        AI_Try3 --"❌ Semua Gagal"--> ErrorResp[⛔ Pesan Error Server Sibuk]:::output
    end

    %% --- POST-PROCESSING SECTION ---
    subgraph "BACKEND PROCESSING LAYER"
        RawResp --> Parser{🔍 JSON Parser & Cleaner\n(Regex & Error Handling)}:::controller
        
        Parser --"✅ JSON Valid"--> AssetGen[🛠️ Generator Aset\n(Matplotlib, FPDF, gTTS)]:::process
        AssetGen --> SaveDB[(💾 Simpan ke Memory DB)]:::db
        
        Parser --"⚠️ JSON Rusak (LaTeX Issue)"--> FallbackText[📄 Gunakan Jawaban Mentah]:::process
    end

    %% --- OUTPUT ---
    SaveDB --> FinalOutput[✨ Tampilan Jawaban Akhir\n(Teks, Langkah, Grafik, PDF, Audio)]:::output
    FallbackText --> FinalOutput
    FinalOutput -->|Update Layar| UI
