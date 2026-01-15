import os
from pathlib import Path

BASE = Path(__file__).parent
env = BASE / '.env'
if env.exists():
    with env.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

import server

if not getattr(server, 'SQLALCHEMY_AVAILABLE', False):
    print('SQLAlchemy not available in server module')
    raise SystemExit(1)

print('DB engine:', server.DATABASE_URL if hasattr(server, 'DATABASE_URL') else server.DB_ENGINE)

try:
    # insert a test record
    server.save_tts_log(typed_text='test typed', ocr_text='test ocr', image=None, audio_filename='test.mp3', voice='test', slow=False)
    sess = server.DB_Session()
    rows = sess.query(server.TTSLog).order_by(server.TTSLog.id.desc()).limit(5).all()
    print('Recent rows:')
    for r in rows:
        print(r.id, r.typed_text, r.ocr_text, r.image, r.audio_filename, r.voice, r.created_at)
    sess.close()
except Exception as e:
    print('Error during DB test:', e)
    raise
