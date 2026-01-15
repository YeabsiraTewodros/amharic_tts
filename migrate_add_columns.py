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

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASE_URL = os.path.expandvars(DATABASE_URL)

print('Using DATABASE_URL:', DATABASE_URL)

try:
    import psycopg2
    from psycopg2 import sql
except Exception as e:
    print('psycopg2 missing:', e)
    raise

conn = None
try:
    # connect to target database
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Add columns if they don't exist
    alterations = [
        "ALTER TABLE tts_logs ADD COLUMN IF NOT EXISTS typed_text text",
        "ALTER TABLE tts_logs ADD COLUMN IF NOT EXISTS ocr_text text",
        "ALTER TABLE tts_logs ADD COLUMN IF NOT EXISTS image varchar(512)",
        "ALTER TABLE tts_logs ADD COLUMN IF NOT EXISTS audio_filename varchar(512)",
    ]
    for stmt in alterations:
        print('Executing:', stmt)
        cur.execute(stmt)

    # Copy old values into new columns for backward compatibility
    try:
        cur.execute("UPDATE tts_logs SET typed_text = text WHERE typed_text IS NULL AND text IS NOT NULL")
        cur.execute("UPDATE tts_logs SET audio_filename = filename WHERE audio_filename IS NULL AND filename IS NOT NULL")
        print('Backfilled typed_text/audio_filename from existing columns')
    except Exception as e:
        print('Backfill failed (maybe old columns absent):', e)

    cur.close()
    print('Migration completed')
except Exception as e:
    print('Migration error:', e)
    raise
finally:
    if conn:
        conn.close()
