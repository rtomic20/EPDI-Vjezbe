from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import markdown
import google.generativeai as genai
import os, tempfile, chardet, json
from PyPDF2 import PdfReader
import docx
from dotenv import load_dotenv

# ---------------------------------------------
# Inicijalizacija
# ---------------------------------------------
load_dotenv("env")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY nije postavljen (provjeri .env)")

genai.configure(api_key=API_KEY)

app = Flask(__name__)
CORS(app)

# ---------------------------------------------
# Učitavanje osnovnog konteksta
# ---------------------------------------------
with open("architecture_context.md", "r", encoding="utf-8") as f:
    ARCHITECTURE_CONTEXT = f.read()

# ---------------------------------------------
# Upload postavke
# ---------------------------------------------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED = {"pdf", "docx", "txt"}
SESSION_CONTEXTS = {}  # pohranjuje tekst po sesiji

def extract_text_from_file(path, ext):
    """Ekstrakcija teksta iz PDF, DOCX, TXT datoteka"""
    ext = ext.lower()
    if ext == "pdf":
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == "docx":
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    else:
        raw = open(path, "rb").read()
        enc = chardet.detect(raw)["encoding"] or "utf-8"
        return raw.decode(enc, errors="ignore")

# ---------------------------------------------
# Upload endpoint
# ---------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    session_id = request.form.get("session_id", "default")

    if not f or f.filename == "":
        return jsonify({"ok": False, "error": "Nema datoteke"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return jsonify({"ok": False, "error": "Nepodržan tip datoteke"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix="."+ext) as tmp:
        f.save(tmp.name)
        text = extract_text_from_file(tmp.name, ext)

    prev = SESSION_CONTEXTS.get(session_id, "")
    SESSION_CONTEXTS[session_id] = (prev + "\n\n" + text).strip()

    return jsonify({"ok": True, "chars": len(text)})

# ---------------------------------------------
# Chat endpoint
# ---------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    session_id = request.json.get("session_id", "default")

    # Dohvati tekst iz učitanog dokumenta ako postoji
    session_context = SESSION_CONTEXTS.get(session_id, "")

    # Ako postoji učitani dokument, koristi njega — inače MD
    if session_context.strip():
        full_context = session_context
    else:
        full_context = ARCHITECTURE_CONTEXT

    model = genai.GenerativeModel("gemini-2.5-flash")

    # Prompt koji forsira JSON izlaz (short + detailed)
    prompt = f"""
Odgovaraj kao arhitektonski savjetnik.
Uvijek vrati isključivo JSON objekt sa sljedećim ključevima:
- "short": kratki odgovor (2–3 rečenice, jednostavan sažetak)
- "detailed": detaljno objašnjenje (više odlomaka, točaka i primjera)

Koristi informacije iz dokumenta ako je učitan, inače iz osnovnog konteksta.

Kontekst:
{full_context}

Korisničko pitanje: {user_message}

Primjer formata:
{{
  "short": "Ovo je kratki odgovor.",
  "detailed": "Ovo je dulji, detaljniji odgovor s objašnjenjima."
}}
"""

    response = model.generate_content(prompt)
    reply_text = response.text.strip()

    # Ako model doda riječ "json" ispred ili koristi trostruke navodnike — očisti
    cleaned = reply_text
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    # Parsiraj JSON
    try:
        data = json.loads(cleaned)
    except Exception as e:
        print("JSON parse error:", e)
        print("Raw odgovor:", reply_text[:500])
        data = {"short": reply_text, "detailed": reply_text}

    # Pretvori Markdown u HTML
    short_html = markdown.markdown(data.get("short", ""))
    detailed_html = markdown.markdown(data.get("detailed", ""))

    return jsonify({"short": short_html, "detailed": detailed_html})

# ---------------------------------------------
# Frontend
# ---------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static", "chatbot.html")

# ---------------------------------------------
# Pokretanje
# ---------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
