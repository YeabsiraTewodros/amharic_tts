import os, json, requests, sys
from urllib.parse import urljoin

BASE = 'http://127.0.0.1:5001'
errors = []
report = []

def fetch(path):
    url = urljoin(BASE, path)
    try:
        r = requests.get(url, timeout=5)
        return r
    except Exception as e:
        errors.append(f'Failed to fetch {path}: {e}')
        return None

# 1. Check /ui
r = fetch('/ui')
if not r or r.status_code != 200:
    errors.append('/ui not reachable or returned non-200')
else:
    report.append('/ui reachable (200)')

# 2. Manifest
r = fetch('/static/manifest.json')
if not r:
    errors.append('manifest.json not reachable')
else:
    try:
        m = r.json()
        report.append('manifest parsed')
        # check for required fields
        for f in ['name','short_name','start_url','display','icons']:
            if f not in m:
                errors.append(f'manifest missing {f}')
        # icons exist
        icons = m.get('icons') or []
        ok_icons = 0
        for ic in icons:
            src = ic.get('src')
            if not src:
                errors.append('manifest icon missing src')
                continue
            rr = fetch(src)
            if rr and rr.status_code == 200:
                ok_icons += 1
        report.append(f'manifest icons reachable: {ok_icons}/{len(icons)}')
    except Exception as e:
        errors.append(f'Failed to parse manifest.json: {e}')

# 3. Service worker
r = fetch('/static/sw.js')
if not r:
    errors.append('sw.js not reachable')
else:
    sw_text = r.text
    if 'addEventListener' in sw_text and 'fetch' in sw_text:
        report.append('service worker appears to handle fetch events')
    else:
        errors.append('service worker may not handle fetch events')

# 4. Check UI JS for service worker registration and beforeinstallprompt
r = fetch('/static/ui.js')
if r and 'serviceWorker.register' in r.text:
    report.append('ui.js registers service worker')
else:
    errors.append('ui.js does not register service worker')
if r and 'beforeinstallprompt' in r.text:
    report.append('ui.js listens for beforeinstallprompt')
else:
    errors.append('ui.js does not listen for beforeinstallprompt')

# 5. Final report
print('\nPWA Audit Report')
print('==================')
for line in report:
    print('- OK:', line)
if errors:
    print('\nIssues found:')
    for e in errors:
        print('-', e)
    sys.exit(2)
else:
    print('\nNo critical issues found (basic checks).')
