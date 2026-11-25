#!/usr/bin/env python3
"""Build the Navidrome Wrapped pages.

    generate.py              the previous calendar month (what cron runs on the 1st)
    generate.py 2026-10      that month
    generate.py --current    the current month so far
    generate.py 2026         that year (the current year: so far)
    generate.py --year       in January: last year, in full; otherwise this year up to the end
                             of last month (cron runs it on Dec 1 and Jan 1)
Every run also rebuilds site/index.html and site/latest.json.
"""
import json, os, re, shutil, sqlite3, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from covers import fetch_covers, load_env  # noqa: E402
from render import latest_json, render_index, render_month, summary  # noqa: E402
from stats import month_stats, year_stats  # noqa: E402


def _target(argv, now):
    """-> (kind, year, month, until) or None for a bad argument."""
    if not argv:
        return 'month', now.year - (now.month == 1), (now.month - 2) % 12 + 1, None
    if argv == ['--current']:
        return 'month', now.year, now.month, now
    if argv == ['--year']:
        if now.month == 1:
            return 'year', now.year - 1, None, None
        return 'year', now.year, None, now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if len(argv) != 1:
        return None
    if m := re.fullmatch(r'(\d{4})', argv[0]):
        year = int(m[1])
        return 'year', year, None, now if year == now.year else None
    m = re.fullmatch(r'(\d{4})-(\d{2})', argv[0])
    if not m or not 1 <= int(m[2]) <= 12:
        return None
    year, month = int(m[1]), int(m[2])
    return 'month', year, month, now if (year, month) == (now.year, now.month) else None


def _write_month(site, s, cfg):
    final = site / s['month']
    tmp = site / f'.tmp-{s["month"]}'
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        ids = [a['album_id'] for a in s['top_artists']] + [t['album_id'] for t in s['top_songs']] \
            + [a['album_id'] for a in s['top_albums']]
        covers = fetch_covers(ids, tmp, cfg)
        (tmp / 'index.html').write_text(render_month(s, covers))
        (tmp / 'summary.json').write_text(json.dumps(summary(s, covers), indent=1))
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    old = site / f'.old-{s["month"]}'
    if final.exists():
        shutil.rmtree(old, ignore_errors=True)
        final.rename(old)
    tmp.rename(final)
    shutil.rmtree(old, ignore_errors=True)


def _rebuild_index(site):
    sums = [json.loads(p.read_text()) for p in sorted(site.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9]/summary.json'))]
    years = [json.loads(p.read_text()) for p in sorted(site.glob('[0-9][0-9][0-9][0-9]/summary.json'))]
    (site / 'index.html').write_text(render_index(sums + years))
    if sums:  # Homepage shows the newest month
        newest = max(sums, key=lambda x: x['month'])
        (site / 'latest.json').write_text(json.dumps(latest_json(newest), indent=1))


def main(argv, env_path=str(HERE / 'wrapped.env'), site=HERE / 'site', now=None):
    cfg = load_env(env_path) if os.path.exists(env_path) else load_env(os.devnull)
    zone = ZoneInfo(cfg['TZ'])
    now = (now or datetime.now(zone)).astimezone(zone)
    target = _target(argv, now)
    if target is None:
        print(__doc__, file=sys.stderr)
        return 2
    kind, year, month, until = target
    if not os.path.exists(cfg['ND_DB']):
        print(f'Navidrome database not found: {cfg["ND_DB"]}', file=sys.stderr)
        return 1
    try:
        s = (year_stats(cfg['ND_DB'], year, cfg['TZ'], until) if kind == 'year'
             else month_stats(cfg['ND_DB'], year, month, cfg['TZ'], until))
    except sqlite3.Error as exc:
        print(f'Could not read {cfg["ND_DB"]}: {exc}', file=sys.stderr)
        return 1
    site = Path(site)
    site.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / 'assets', site / 'assets', dirs_exist_ok=True)
    if s is None:
        print(f'No plays in {year:04d}' + (f'-{month:02d}' if month else ''))
    else:
        _write_month(site, s, cfg)
        print(f'{now:%Y-%m-%d %H:%M} built {s["month"]}{" (so far)" if until else ""}: '
              f'{s["plays"]} plays, top artist {s["top_artists"][0]["name"]}')
    _rebuild_index(site)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
