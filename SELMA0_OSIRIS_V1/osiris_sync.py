"""Selma OSIRIS: read-only public Earth science synchronization."""
import argparse
import hashlib
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

SOURCES = {
    'eonet': 'https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100',
    'epic': 'https://epic.gsfc.nasa.gov/api/natural',
}
MAX_BYTES = 2_000_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(source):
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(SOURCES[source], headers={'Accept': 'application/json', 'User-Agent': 'Selma-OSIRIS/0.1'})
    with opener.open(req, timeout=15) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('response exceeds limit')
    return raw


def normalize(source, raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('response exceeds limit')
    data = json.loads(raw)
    rows = data['events'] if source == 'eonet' else data
    fields = ('id', 'title') if source == 'eonet' else ('identifier', 'image', 'date', 'caption')
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('invalid collection')
    if any(not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k] or len(row[k]) > 2000 for k in fields) for row in rows):
        raise ValueError('invalid record')
    return [{k: row[k] for k in fields} for row in rows]


def open_db(path):
    db = sqlite3.connect(path, timeout=5)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS snapshots(source TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL, checked INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS health(source TEXT PRIMARY KEY, ok INTEGER NOT NULL, checked INTEGER NOT NULL, error TEXT)')
    return db


def sync(db, loader=fetch, stop=lambda: False):
    for source in SOURCES:
        if stop():
            break
        now = int(time.time())
        try:
            raw = loader(source)
            payload = json.dumps(normalize(source, raw), sort_keys=True, separators=(',', ':'))
            digest = hashlib.sha256(payload.encode()).hexdigest()
            if stop():
                break
            with db:
                db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)', (source, digest, payload, now))
                db.execute('INSERT OR REPLACE INTO health VALUES(?,?,?,?)', (source, 1, now, None))
        except Exception as exc:
            with db:
                db.execute('INSERT OR REPLACE INTO health VALUES(?,?,?,?)', (source, 0, now, type(exc).__name__))


def status(db):
    out = {}
    for source in SOURCES:
        snap = db.execute('SELECT digest,checked FROM snapshots WHERE source=?', (source,)).fetchone()
        health = db.execute('SELECT ok,checked,error FROM health WHERE source=?', (source,)).fetchone()
        out[source] = {'snapshot': snap, 'health': health, 'stale': not snap or not health or not health[0] or time.time()-snap[1] > 21600}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['once', 'watch', 'status'])
    p.add_argument('--db', default='osiris.sqlite3')
    p.add_argument('--stop-file', default='OSIRIS.STOP')
    p.add_argument('--interval', type=int, default=3600)
    a = p.parse_args()
    if a.interval < 300:
        p.error('minimum interval is 300 seconds')
    stop = Path(a.stop_file).exists
    db = open_db(a.db)
    try:
        if a.mode == 'status':
            print(json.dumps(status(db), indent=2))
        else:
            while not stop():
                sync(db, stop=stop)
                print(json.dumps(status(db)), flush=True)
                if a.mode == 'once':
                    break
                for _ in range(a.interval):
                    if stop():
                        break
                    time.sleep(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
