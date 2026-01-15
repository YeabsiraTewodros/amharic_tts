import os
import sys
from pathlib import Path


def load_dotenv(dotenv_path: str):
    p = Path(dotenv_path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            v = os.path.expandvars(v)
            if k not in os.environ:
                os.environ[k] = v


if __name__ == '__main__':
    BASE = Path(__file__).parent
    load_dotenv(BASE / '.env')

    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'amharic_tts')

    print('Creating database:', DB_NAME, 'on', DB_HOST, DB_PORT, 'as', DB_USER)

    try:
        import psycopg2
        from psycopg2 import sql
    except Exception as e:
        print('psycopg2 not available:', e)
        sys.exit(1)

    try:
        conn = psycopg2.connect(dbname='postgres', user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DB_NAME)))
            print('Database created successfully.')
        except Exception as e:
            # check if already exists
            if 'already exists' in str(e):
                print('Database already exists.')
            else:
                print('Failed to create database:', e)
                raise
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print('Connection failed:', e)
        sys.exit(1)
