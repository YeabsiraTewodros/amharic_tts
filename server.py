from flask import Flask, request, send_file, jsonify
import io
from gtts import gTTS
import os
import uuid
import traceback
import urllib.parse
import base64
import shutil
from datetime import datetime

# Optional DB support (SQLAlchemy + PostgreSQL). If DATABASE_URL is set in env,
# we'll connect to it. Otherwise fall back to a local sqlite file so the app
# still runs without Postgres during development.
try:
    from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    SQLALCHEMY_AVAILABLE = True
except Exception:
    SQLALCHEMY_AVAILABLE = False

app = Flask(__name__)

# helper to parse boolean-like values
def _parse_bool(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).lower()
    return s in ('1', 'true', 'yes', 'on')

# Low-level WSGI middleware to log every incoming request (even if routing fails)
orig_wsgi = app.wsgi_app
def _wsgi_logger(environ, start_response):
    try:
        m = environ.get('REQUEST_METHOD')
        p = environ.get('PATH_INFO')
        ct = environ.get('CONTENT_TYPE')
        cl = environ.get('CONTENT_LENGTH')
        print("WSGI ->", m, p, "CT=", ct, "CL=", cl)
    except Exception:
        pass
    return orig_wsgi(environ, start_response)
app.wsgi_app = _wsgi_logger

# Check whether the system `tesseract` binary is available
TESSERACT_CMD = shutil.which('tesseract')
TESSERACT_AVAILABLE = bool(TESSERACT_CMD)
print("Tesseract binary:", TESSERACT_CMD)

# Lightweight CORS handling without external dependency
@app.before_request
def _handle_options():
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        headers = resp.headers
        headers['Access-Control-Allow-Origin'] = '*'
        headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return resp


@app.before_request
def _log_every_request():
    try:
        print("--> REQUEST", request.method, request.path)
    except Exception:
        pass


@app.after_request
def _add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# track the latest generated file for easy ESP32 fetch
LATEST_FILE = None

# --- Database init ---
DB_ENGINE = None
DB_Session = None
Base = None
if SQLALCHEMY_AVAILABLE:
    try:
        Base = declarative_base()
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL:
            # allow ${VAR} expansion in DATABASE_URL when users store components in .env
            DATABASE_URL = os.path.expandvars(DATABASE_URL)
        if not DATABASE_URL:
            # default to sqlite file in project folder for convenience
            DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'amharic_tts.db')}"
        DB_ENGINE = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {})
        DB_Session = sessionmaker(bind=DB_ENGINE)

        class TTSLog(Base):
            __tablename__ = 'tts_logs'
            id = Column(Integer, primary_key=True)
            # original typed text (if user typed/pasted text)
            typed_text = Column(Text, nullable=True)
            # OCR-extracted text from an uploaded/captured image
            ocr_text = Column(Text, nullable=True)
            # path to saved uploaded image (if any)
            image = Column(String(512), nullable=True)
            # path to generated audio file (if any)
            audio_filename = Column(String(512), nullable=True)
            voice = Column(String(64), nullable=True)
            slow = Column(Boolean, default=False)
            created_at = Column(DateTime, default=datetime.utcnow)

        class Setting(Base):
            __tablename__ = 'settings'
            id = Column(Integer, primary_key=True)
            key = Column(String(128), unique=True, index=True)
            value = Column(Text)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow)

        # create tables if not exist
        try:
            Base.metadata.create_all(DB_ENGINE)
            print('Database initialized:', DATABASE_URL)
        except Exception as e:
            print('Failed to initialize database:', e)
    except Exception as e:
        print('SQLAlchemy present but DB init failed:', e)
        SQLALCHEMY_AVAILABLE = False

def save_tts_log(typed_text=None, ocr_text=None, image=None, audio_filename=None, voice=None, slow=False):
    """Save a TTS/OCR log record. Pass whichever fields are applicable."""
    if not SQLALCHEMY_AVAILABLE:
        return
    try:
        sess = DB_Session()
        rec = TTSLog(typed_text=typed_text, ocr_text=ocr_text, image=image,
                     audio_filename=audio_filename, voice=voice, slow=bool(slow))
        sess.add(rec)
        sess.commit()
        sess.close()
    except Exception as e:
        print('Failed to save TTS log:', e)

def upsert_setting(key, value):
    if not SQLALCHEMY_AVAILABLE:
        return
    try:
        sess = DB_Session()
        existing = sess.query(Setting).filter(Setting.key == key).one_or_none()
        now = datetime.utcnow()
        if existing:
            existing.value = value
            existing.updated_at = now
        else:
            existing = Setting(key=key, value=value, created_at=now, updated_at=now)
            sess.add(existing)
        sess.commit()
        sess.close()
    except Exception as e:
        print('Failed to upsert setting:', e)

def get_all_settings():
    if not SQLALCHEMY_AVAILABLE:
        return {}
    try:
        sess = DB_Session()
        rows = sess.query(Setting).all()
        out = {r.key: r.value for r in rows}
        sess.close()
        return out
    except Exception as e:
        print('Failed to fetch settings:', e)
        return {}


@app.route("/tts", methods=["POST"])
def text_to_speech():
    try:
        print("\n📥 NEW REQUEST")

        print("Headers:", dict(request.headers))
        print("Raw data:", request.data)
        print("Form:", request.form)
        print("JSON:", request.get_json(silent=True))

        text = None

        # 1️⃣ JSON
        if request.is_json:
            data = request.get_json(silent=True)
            if data:
                text = data.get("text")

        # 2️⃣ Form-data
        if not text and request.form:
            text = request.form.get("text")
            # If the client sent a raw body without '=' (e.g. curl --data-raw "..."),
            # some parsers convert it into a form where the text becomes the key
            # and the value is empty. Handle that case by treating a single
            # empty-valued key as the payload.
            if not text:
                for k, v in request.form.items():
                    if k and (v is None or v == ""):
                        text = k
                        break

        # 3️⃣ Raw body (ESP32 / curl)
        # If raw bytes are present in the request body, prefer them over form-derived
        # keys because some clients send `application/x-www-form-urlencoded` with
        # a raw payload that Flask parses into a single empty-valued key.
        raw = request.get_data(cache=True)
        if raw:
            raw_text = raw.decode("utf-8", errors="replace").strip()
            if raw_text:
                text = raw_text

        # If Content-Type is form-urlencoded and the client sent percent-encoded
        # data (or the form parsed badly), attempt to parse/unquote the raw body
        # as a fallback so percent-encoded payloads are accepted automatically.
        try:
            ct = request.content_type or ""
            if "application/x-www-form-urlencoded" in ct and raw:
                s = raw.decode("latin-1")
                if "%" in s or "+" in s:
                    qs = urllib.parse.parse_qs(s, keep_blank_values=True, encoding="utf-8", errors="replace")
                    if not text:
                        if "text" in qs and qs["text"]:
                            text = qs["text"][0]
                        else:
                            # If parse_qs fails to find a key-value pair, try unquoting
                            decoded = urllib.parse.unquote_plus(s)
                            if decoded:
                                text = decoded
        except Exception:
            pass

        # If text still looks malformed (many replacement chars or question marks),
        # try a best-effort re-decode using the raw bytes.
        def looks_malformed(s: str) -> bool:
            if s is None:
                return True
            # heuristic: many replacement or question marks suggest decoding issues
            return s.count("\ufffd") > 0 or s.count("?") >= max(1, len(s) // 4)

        if looks_malformed(text):
            try:
                raw = request.get_data(cache=True)
                if raw:
                    # Attempt 1: strict utf-8 decode of raw bytes
                    try:
                        attempt = raw.decode("utf-8")
                        if attempt:
                            text = attempt
                    except Exception:
                        # Attempt 2: decode as latin-1 to preserve raw bytes,
                        # unquote_plus to handle percent-encoding, then re-decode as utf-8.
                        try:
                            s = raw.decode("latin-1")
                            s = urllib.parse.unquote_plus(s)
                            recovered = s.encode("latin-1")
                            text = recovered.decode("utf-8")
                        except Exception:
                            pass
            except Exception:
                pass

        if not text:
            return jsonify({"error": "No text to send to TTS API"}), 400

        # read slow flag from JSON/form/query
        slow = False
        try:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                slow = _parse_bool(data.get('slow'))
            if not slow and request.form:
                slow = _parse_bool(request.form.get('slow'))
            if not slow:
                slow = _parse_bool(request.args.get('slow'))
        except Exception:
            slow = False

        print("✅ TEXT RECEIVED:", text)
        print("✅ TEXT REPR:", repr(text), "len:", 0 if text is None else len(text))

        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        tts = gTTS(text=text, lang="am", slow=slow)
        tts.save(filepath)

        # update latest file
        global LATEST_FILE
        LATEST_FILE = filepath

        # save log to DB if available (record typed text and audio path)
        try:
            save_tts_log(typed_text=text, audio_filename=filepath, voice=('server_slow' if slow else 'server'), slow=slow)
        except Exception:
            pass

        print("🔊 Audio saved:", filepath)

        return send_file(filepath, mimetype="audio/mpeg")

    except Exception as e:
        print("❌ INTERNAL SERVER ERROR")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/ocr_upload', methods=['POST'])
def ocr_upload():
    try:
        # Accept multipart form file 'image' or JSON/base64 body
        print("\n📥 OCR UPLOAD REQUEST")
        print("Headers:", dict(request.headers))
        try:
            print("Files:", list(request.files.keys()))
        except Exception:
            pass
        print("Content-Length:", request.content_length)
        if not TESSERACT_AVAILABLE:
            return jsonify({'error': 'Tesseract OCR binary not found on server. Install tesseract (system package) and restart the server.'}), 503
        img_bytes = None
        if request.files and 'image' in request.files:
            f = request.files['image']
            img_bytes = f.read()
        else:
            # JSON with {"b64": "..."}
            if request.is_json:
                data = request.get_json(silent=True)
                if data and data.get('b64'):
                    try:
                        img_bytes = base64.b64decode(data.get('b64'))
                    except Exception:
                        img_bytes = None
            if not img_bytes:
                raw = request.get_data(cache=True)
                if raw:
                    s = raw.decode('utf-8', errors='ignore').strip()
                    try:
                        img_bytes = base64.b64decode(s)
                    except Exception:
                        img_bytes = None

        if not img_bytes:
            return jsonify({'error': 'No image provided (field "image" or JSON {"b64":"..."})'}), 400

        try:
            from PIL import Image
            import pytesseract
        except Exception as e:
            return jsonify({'error': 'Server OCR not available. Install Pillow and pytesseract with system Tesseract. ' + str(e)}), 500

        try:
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        except Exception as e:
            return jsonify({'error': 'Failed to parse image: ' + str(e)}), 400

        # Try Amharic language first, fall back to English or default
        text = ''
        try:
            text = pytesseract.image_to_string(img, lang='amh')
        except Exception:
            try:
                text = pytesseract.image_to_string(img, lang='eng')
            except Exception:
                text = pytesseract.image_to_string(img)

        text = (text or '').strip()
        # save uploaded image to `uploads/` and optionally log OCR results
        image_path = None
        try:
            image_filename = f"{uuid.uuid4()}.png"
            image_path = os.path.join(UPLOADS_DIR, image_filename)
            with open(image_path, 'wb') as fh:
                fh.write(img_bytes)
        except Exception:
            image_path = None

        try:
            if SQLALCHEMY_AVAILABLE:
                save_tts_log(ocr_text=text, image=image_path, audio_filename=None, voice='ocr', slow=False)
        except Exception:
            pass
        return jsonify({'text': text})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/")
def index():
    return "Amharic TTS server running"


@app.errorhandler(404)
def log_404(e):
    try:
        print("--- 404 handler ---")
        print("Method:", request.method)
        print("Path:", request.path)
        print("Full Path:", request.full_path)
        print("Headers:", dict(request.headers))
        # Useful WSGI/env keys
        env = request.environ
        for k in ('RAW_URI','REQUEST_URI','PATH_INFO','QUERY_STRING','SCRIPT_NAME'):
            if k in env:
                print(f"ENV {k}:", env.get(k))
    except Exception:
        pass
    return e, 404


@app.route('/ui')
def ui():
    path = os.path.join(BASE_DIR, 'static', 'ui.html')
    print("Serving UI from:", path, "exists:", os.path.exists(path))
    return send_file(path)


@app.route('/latest.mp3')
def latest_mp3():
    if LATEST_FILE and os.path.exists(LATEST_FILE):
        return send_file(LATEST_FILE, mimetype='audio/mpeg')
    return jsonify({'error': 'no latest file'}), 404


@app.route("/tts_b64", methods=["POST"])
def text_to_speech_b64():
    try:
        print("\n📥 NEW B64 REQUEST")
        print("Headers:", dict(request.headers))
        raw = request.get_data(cache=True)
        print("Raw data:", raw)

        b64 = None
        # JSON body with {"b64": "..."}
        if request.is_json:
            data = request.get_json(silent=True)
            if data:
                b64 = data.get("b64")

        # Form-data
        if not b64 and request.form:
            b64 = request.form.get("b64")

        # Raw body: treat as plain base64 string
        if not b64 and raw:
            try:
                b64 = raw.decode("utf-8").strip()
            except Exception:
                b64 = None

        if not b64:
            return jsonify({"error": "No base64 payload provided (field 'b64')"}), 400

        # Decode base64 to UTF-8 text
        try:
            decoded_bytes = base64.b64decode(b64)
            text = decoded_bytes.decode("utf-8")
        except Exception as e:
            print("Failed to decode base64:", e)
            return jsonify({"error": "Failed to decode base64 payload"}), 400

        # detect slow flag if provided in JSON body
        slow = False
        try:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                slow = _parse_bool(data.get('slow'))
            if not slow and request.form:
                slow = _parse_bool(request.form.get('slow'))
        except Exception:
            slow = False

        print("✅ TEXT RECEIVED (from b64):", text, "slow:", slow)

        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        tts = gTTS(text=text, lang="am", slow=slow)
        tts.save(filepath)

        print("🔊 Audio saved:", filepath)

        # update latest file
        global LATEST_FILE
        LATEST_FILE = filepath

        # save log to DB if available (record typed text and audio path)
        try:
            save_tts_log(typed_text=text, audio_filename=filepath, voice=('server_slow' if slow else 'server'), slow=slow)
        except Exception:
            pass

        return send_file(filepath, mimetype="audio/mpeg")


    except Exception as e:
        print("❌ INTERNAL SERVER ERROR (b64)")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/tts_b64_get", methods=["GET"])
def text_to_speech_b64_get():
    try:
        b64 = request.args.get("b64")
        if not b64:
            return jsonify({"error": "Missing 'b64' query parameter"}), 400

        # Accept URL-safe base64 as well
        try:
            # Normalize padding
            padding = len(b64) % 4
            if padding:
                b64 += "=" * (4 - padding)
            decoded_bytes = base64.urlsafe_b64decode(b64)
            text = decoded_bytes.decode("utf-8")
        except Exception:
            return jsonify({"error": "Failed to decode base64 query parameter"}), 400

        # read slow flag from query
        slow = _parse_bool(request.args.get('slow'))
        print("✅ TEXT RECEIVED (from b64 GET):", text, "slow:", slow)

        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        tts = gTTS(text=text, lang="am", slow=slow)
        tts.save(filepath)

        print("🔊 Audio saved:", filepath)
        # update latest file
        global LATEST_FILE
        LATEST_FILE = filepath

        return send_file(filepath, mimetype="audio/mpeg")

    except Exception as e:
        print("❌ INTERNAL SERVER ERROR (b64_get)")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    try:
        mtime = os.path.getmtime(__file__)
    except Exception:
        mtime = None
    print("🚀 Starting Amharic TTS server...")
    print("Server file:", __file__, "mtime:", mtime)
    # print available routes to help debugging 404s
    try:
        print("Registered routes:")
        for rule in app.url_map.iter_rules():
            methods = ','.join(sorted(rule.methods))
            print(f"  {rule.rule} -> {methods}")
    except Exception:
        pass
    app.run(host="0.0.0.0", port=5001)
