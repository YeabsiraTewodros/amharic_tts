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
            # simple env expansion
            v = os.path.expandvars(v)
            if k not in os.environ:
                os.environ[k] = v


if __name__ == '__main__':
    BASE = Path(__file__).parent
    dotenv = BASE / '.env'
    load_dotenv(str(dotenv))

    DATABASE_URL = os.environ.get('DATABASE_URL')
    print('Using DATABASE_URL:', DATABASE_URL)

    try:
        import server
    except Exception as e:
        print('Failed to import server module (this will still initialize DB models):', e)
        sys.exit(1)

    try:
        if getattr(server, 'Base', None) is not None and getattr(server, 'DB_ENGINE', None) is not None:
            server.Base.metadata.create_all(server.DB_ENGINE)
            print('Tables created/ensured successfully.')
        else:
            print('SQLAlchemy not available or DB engine not configured in server.py; no tables created.')
    except Exception as e:
        print('Error while creating tables:', e)
        sys.exit(1)