# 🧮 SkoolNow AI Math Tutor (Gemini 2.5 Edition)

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