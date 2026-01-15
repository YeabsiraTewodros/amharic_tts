#!/usr/bin/env python3
"""
Small Flask audio receiver for Raspberry Pi.
Accepts POST /play (audio/mpeg body) and GET /play_url?url=...
Plays with `mpg123` and keeps CORS headers permissive for local network use.

Save as /home/pi/pi_player.py and run with `python3 pi_player.py` or create a systemd unit.
"""
import os
import tempfile
import subprocess
import threading
import time
import signal
from pathlib import Path

from flask import Flask, request, jsonify
import requests

APP_PORT = int(os.environ.get('PI_PLAYER_PORT', 5002))
KEEP_SECONDS = int(os.environ.get('PI_PLAYER_KEEP_SECONDS', 300))

app = Flask(__name__)
TEMP_DIR = Path(os.environ.get('PI_PLAYER_TMP', '/tmp/pi_player'))
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def play_file(path: str):
    # Use mpg123 for lightweight playback
    try:
        subprocess.Popen(['mpg123', '-q', path])
        app.logger.info('Started playback: %s', path)
    except Exception as e:
        app.logger.exception('Failed to play %s: %s', path, e)


@app.after_request
def add_cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


@app.route('/play', methods=['POST', 'OPTIONS'])
def play():
    if request.method == 'OPTIONS':
        return ('', 204)
    data = request.data
    if not data:
        return jsonify({'error': 'no audio provided'}), 400
    fd, tmp = tempfile.mkstemp(suffix='.mp3', dir=str(TEMP_DIR))
    os.close(fd)
    with open(tmp, 'wb') as f:
        f.write(data)
    play_file(tmp)
    return jsonify({'status': 'playing', 'path': tmp})


@app.route('/play_url', methods=['GET'])
def play_url():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'missing url'}), 400
    try:
        r = requests.get(url, stream=True, timeout=20)
    except Exception as e:
        app.logger.exception('fetch failed: %s', e)
        return jsonify({'error': 'fetch failed', 'detail': str(e)}), 502
    if r.status_code != 200:
        return jsonify({'error': 'fetch failed', 'status': r.status_code}), 502
    fd, tmp = tempfile.mkstemp(suffix='.mp3', dir=str(TEMP_DIR))
    os.close(fd)
    with open(tmp, 'wb') as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    play_file(tmp)
    return jsonify({'status': 'fetched_and_playing', 'path': tmp})


def cleanup_loop():
    while True:
        try:
            now = time.time()
            for p in TEMP_DIR.iterdir():
                try:
                    m = p.stat().st_mtime
                    if now - m > KEEP_SECONDS:
                        p.unlink()
                        app.logger.info('Removed old file %s', p)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(60)


def handle_sigterm(signum, frame):
    app.logger.info('Shutting down on signal %s', signum)
    raise SystemExit()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, handle_sigterm)
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    app.logger.info('pi_player starting on 0.0.0.0:%d, temp dir: %s', APP_PORT, TEMP_DIR)
    app.run(host='0.0.0.0', port=APP_PORT)
