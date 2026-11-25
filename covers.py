"""Settings file and album covers from Navidrome's Subsonic API."""
import http.client, urllib.error, urllib.parse, urllib.request
from pathlib import Path

DEFAULTS = {'TZ': 'UTC', 'ND_DB': '/var/lib/navidrome/navidrome.db'}


def load_env(path):
    cfg = dict(DEFAULTS)
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return cfg


def fetch_covers(album_ids, out_dir, cfg, opener=urllib.request.urlopen):
    """Download 300px covers into out_dir/covers/; returns {album_id: relative path} for the ones that worked."""
    got = {}
    for al in dict.fromkeys(a for a in album_ids if a):
        q = urllib.parse.urlencode({'id': al, 'size': 300, 'u': cfg.get('ND_USER', ''), 't': cfg.get('ND_TOKEN', ''),
                                    's': cfg.get('ND_SALT', ''), 'v': '1.16.1', 'c': 'wrapped'})
        try:
            with opener(f"{cfg.get('ND_URL', '').rstrip('/')}/rest/getCoverArt?{q}", timeout=10) as r:
                if not r.headers.get('Content-Type', '').startswith('image/'):
                    continue
                data = r.read()
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
            continue
        (Path(out_dir) / 'covers').mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / 'covers' / f'{al}.jpg').write_bytes(data)
        got[al] = f'covers/{al}.jpg'
    return got
