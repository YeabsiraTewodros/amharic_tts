import os
import time
import json
import base64
from urllib import request as urlreq


def load_env(path='.env'):
    p = os.path.join(os.path.dirname(__file__), path)
    if not os.path.exists(p):
        return
    with open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def post_json(url, obj, timeout=10):
    data = json.dumps(obj).encode('utf-8')
    req = urlreq.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urlreq.urlopen(req, timeout=timeout) as resp:
        return resp.getcode(), resp.read().decode('utf-8')


if __name__ == '__main__':
    load_env()
    base = 'http://127.0.0.1:5001'

    # wait for server
    for i in range(15):
        try:
            with urlreq.urlopen(base + '/', timeout=2) as r:
                if r.status == 200:
                    print('Server is up')
                    break
        except Exception:
            time.sleep(0.5)
    else:
        print('Server not reachable, aborting')
        raise SystemExit(1)

    # 1) send TTS (b64) request
    text = 'ሞክር ፈተና'
    b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
    try:
        code, body = post_json(base + '/tts_b64', {'b64': b64, 'slow': False})
        print('TTS request response code:', code)
    except Exception as e:
        print('TTS request failed:', e)

    time.sleep(1)

    # 2) send OCR (simple 1x1 PNG) as JSON b64
    png_b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
    try:
        code, body = post_json(base + '/ocr_upload', {'b64': png_b64})
        print('OCR request response code:', code, 'body:', body)
    except Exception as e:
        print('OCR request failed:', e)

    # 3) import server module to query DB
    try:
        import server
        if not getattr(server, 'SQLALCHEMY_AVAILABLE', False):
            print('SQLAlchemy not available in server module')
            raise SystemExit(1)
        sess = server.DB_Session()
        rows = sess.query(server.TTSLog).order_by(server.TTSLog.id.desc()).limit(10).all()
        print('\nRecent DB rows:')
        for r in rows:
            print(r.id, r.typed_text, r.ocr_text, r.image, r.audio_filename, r.voice, r.created_at)
        sess.close()
    except Exception as e:
        print('DB verification failed:', e)
        raise
