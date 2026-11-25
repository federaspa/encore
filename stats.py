"""Monthly listening stats from Navidrome's database (read-only)."""
import calendar, json, re, sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NIGHT_HOURS = {22, 23, 0, 1, 2, 3}
EARLY_HOURS = {5, 6, 7, 8}
ROASTS = {
    'Loyal': '{top_artist} should start paying you rent.',
    'Nostalgic': 'Your music is old enough to remember {avg_year}. Probably fondly.',
    'Fresh': "You'd rather miss a meal than a new release.",
    'Eclectic': 'Your shuffle button is having an identity crisis.',
    'Curious': 'A little bit of everything, a lot of nothing in particular.',
}


def _month_bounds(year, month, tz):
    start = datetime(year, month, 1, tzinfo=tz)
    nxt = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=tz)
    return start, nxt


def _connect(db_path):
    return sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)


def _genres(tags, genre):
    try:
        found = [g['value'] for g in json.loads(tags or '{}').get('genre', []) if g.get('value')]
    except (ValueError, AttributeError):
        found = []
    if not found and genre:
        found = [g.strip() for g in re.split(r'[;,/]', genre) if g.strip()]
    return found


def _plays(con, start, end):
    cols = {r[1] for r in con.execute('pragma table_info(media_file)')}
    album_artist = 'm.album_artist' if 'album_artist' in cols else 'm.artist'
    rows = con.execute(f'''
        select s.submission_time, m.id, m.title, m.artist, m.album, m.album_id, m.duration,
               m.year, m.original_year, m.genre, m.tags, {album_artist}
        from scrobbles s join media_file m on m.id = s.media_file_id
        where s.submission_time >= ? and s.submission_time < ?
        order by s.submission_time''', (int(start.timestamp()), int(end.timestamp())))
    tz = start.tzinfo
    plays = []
    for t, mid, title, artist, album, album_id, dur, year, oyear, genre, tags, aartist in rows:
        y = oyear if (oyear or 0) > 0 else year if (year or 0) > 0 else None
        plays.append({'when': datetime.fromtimestamp(t, tz), 'id': mid, 'title': title or '?',
                      'artist': artist or '', 'album': album or '', 'album_id': album_id,
                      'album_artist': aartist or artist or '', 'dur': dur or 0, 'year': y,
                      'genres': _genres(tags, genre)})
    return plays


def _top(counter, n=10):
    return sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))[:n]


def _clock_label(by_hour, total):
    night = sum(by_hour[h] for h in NIGHT_HOURS)
    early = sum(by_hour[h] for h in EARLY_HOURS)
    peak = max(range(24), key=lambda h: (by_hour[h], -h))
    if night >= 0.25 * total:
        return peak, 'Night Owl'
    if early >= 0.25 * total:
        return peak, 'Early Bird'
    return peak, '9-to-5 Listener' if 9 <= peak <= 17 else 'Evening Unwinder'


def _longest_streak(days):
    best, run_start, prev = None, None, None
    for d in sorted(days):
        if prev is None or d != prev + timedelta(days=1):
            run_start = d
        length = (d - run_start).days + 1
        if best is None or length > best[0]:
            best = (length, run_start, d)
        prev = d
    return {'days': best[0], 'start': best[1].isoformat(), 'end': best[2].isoformat()}


def _personality(top_artist, top_share, avg_year, genre_count, clock_label):
    if top_share > 0.30:
        adj = 'Loyal'
    elif avg_year and avg_year < 1990:
        adj = 'Nostalgic'
    elif avg_year and avg_year >= 2015:
        adj = 'Fresh'
    elif genre_count >= 10:
        adj = 'Eclectic'
    else:
        adj = 'Curious'
    return {'title': f'The {adj} {clock_label}',
            'roast': ROASTS[adj].format(top_artist=top_artist, avg_year=avg_year)}


def month_stats(db_path, year, month, tz='UTC', until=None):
    zone = ZoneInfo(tz)
    start, end = _month_bounds(year, month, zone)
    pstart, _ = _month_bounds(year - (month == 1), (month - 2) % 12 + 1, zone)
    return _period_stats(db_path, start, end, pstart, until, 'month',
                         f'{year:04d}-{month:02d}', f'{calendar.month_name[month]} {year}')


def year_stats(db_path, year, tz='UTC', until=None):
    zone = ZoneInfo(tz)
    start, end = datetime(year, 1, 1, tzinfo=zone), datetime(year + 1, 1, 1, tzinfo=zone)
    return _period_stats(db_path, start, end, datetime(year - 1, 1, 1, tzinfo=zone), until, 'year',
                         str(year), str(year))


def _year_extras(plays):
    by_month = [0] * 12
    month_artists = defaultdict(Counter)
    for p in plays:
        by_month[p['when'].month - 1] += 1
        if p['artist']:
            month_artists[p['when'].month][p['artist']] += 1
    top_by_month = []
    for m in sorted(month_artists):
        name, n = _top(month_artists[m], 1)[0]
        top_by_month.append({'month': calendar.month_name[m], 'name': name, 'plays': n})
    busiest = max(range(12), key=lambda m: (by_month[m], -m))
    return {'by_month': by_month, 'top_artist_by_month': top_by_month,
            'busiest_month': {'month': calendar.month_name[busiest + 1], 'plays': by_month[busiest]}}


def _period_stats(db_path, start, end, pstart, until, kind, period_key, label):
    """Stats for plays in [start, end) (cut off at `until`), compared with [pstart, start)."""
    if until is not None:
        end = min(end, until)
    con = _connect(db_path)
    try:
        plays = _plays(con, start, end)
        if not plays:
            return None
        prev_plays = _plays(con, pstart, start)
        seen_before = {r[0] for r in con.execute(
            'select distinct m.artist from scrobbles s join media_file m on m.id = s.media_file_id '
            'where s.submission_time < ?', (int(start.timestamp()),))}
    finally:
        con.close()

    total = len(plays)
    artists, artist_secs, songs, albums, genres = Counter(), Counter(), Counter(), Counter(), Counter()
    artist_albums, song_meta, album_meta = defaultdict(Counter), {}, {}
    by_hour, by_date = [0] * 24, Counter()
    song_days = defaultdict(Counter)
    day_artists, day_secs = defaultdict(Counter), Counter()
    for p in plays:
        a, key, d = p['artist'], (p['title'], p['artist']), p['when'].date()
        if a:  # plays with no artist are left out of the artist stats only
            artists[a] += 1
            artist_secs[a] += p['dur']
            artist_albums[a][p['album_id']] += 1
            day_artists[d][a] += 1
        songs[key] += 1
        song_meta[key] = p['album_id']
        song_days[key][d] += 1
        albums[p['album_id']] += 1
        album_meta[p['album_id']] = (p['album'], p['album_artist'])
        for g in p['genres']:
            genres[g] += 1
        by_hour[p['when'].hour] += 1
        by_date[d] += 1
        day_secs[d] += p['dur']

    if not artists:
        artists['Unknown artist'] = total
        artist_secs['Unknown artist'] = sum(p['dur'] for p in plays)
        artist_albums['Unknown artist'] = Counter(p['album_id'] for p in plays)
        for p in plays:
            day_artists[p['when'].date()]['Unknown artist'] += 1

    last_day = (end - timedelta(microseconds=1)).date()
    first_day = start.date()
    by_day = [{'date': (first_day + timedelta(days=i)).isoformat(),
               'plays': by_date[first_day + timedelta(days=i)]}
              for i in range((last_day - first_day).days + 1)]

    top_songs = []
    for (title, artist), n in _top(songs):
        bd, bn = _top(song_days[(title, artist)], 1)[0]
        top_songs.append({'title': title, 'artist': artist, 'plays': n, 'album_id': song_meta[(title, artist)],
                          'best_day': {'date': bd.isoformat(), 'plays': bn}})

    peak_hour, clock = _clock_label(by_hour, total)
    bdate, bplays = max(by_date.items(), key=lambda kv: (kv[1], -kv[0].toordinal()))
    dated = [p for p in plays if p['year']]
    avg_year = round(sum(p['year'] for p in dated) / len(dated)) if dated else None
    pick = lambda p: {'title': p['title'], 'artist': p['artist'], 'year': p['year']}

    prev = obsession = None
    new_artists = []
    if prev_plays:
        prev = {'plays': len(prev_plays), 'hours': round(sum(p['dur'] for p in prev_plays) / 3600, 1)}
        prev_artists = Counter(p['artist'] for p in prev_plays)
        new_artists = sorted(a for a in artists if a not in seen_before)
        deltas = Counter({a: n - prev_artists[a] for a, n in artists.items() if n > prev_artists[a]})
        if deltas:
            name, delta = _top(deltas, 1)[0]
            obsession = {'name': name, 'delta': delta}

    top_artist, top_n = _top(artists, 1)[0]
    genre_list = [{'name': g, 'plays': n} for g, n in _top(genres, len(genres))]
    out = {
        'kind': kind, 'month': period_key, 'label': label,
        'so_far': until is not None,
        'plays': total, 'hours': round(sum(p['dur'] for p in plays) / 3600, 1),
        'artist_count': len(artists), 'song_count': len(songs),
        'top_artists': [{'name': a, 'plays': n, 'minutes': round(artist_secs[a] / 60),
                         'album_id': _top(artist_albums[a], 1)[0][0]} for a, n in _top(artists)],
        'top_songs': top_songs,
        'top_albums': [{'name': album_meta[al][0], 'artist': album_meta[al][1], 'plays': n, 'album_id': al}
                       for al, n in _top(albums)],
        'genres': genre_list, 'genre_count': len(genres),
        'by_hour': by_hour, 'by_day': by_day,
        'peak_hour': peak_hour, 'clock_label': clock,
        'longest_streak': _longest_streak(by_date),
        'biggest_day': {'date': bdate.isoformat(), 'plays': bplays, 'hours': round(day_secs[bdate] / 3600, 1),
                        'top_artist': (_top(day_artists[bdate], 1) or [('various artists', 0)])[0][0]},
        'avg_year': avg_year,
        'oldest': pick(min(dated, key=lambda p: p['year'])) if dated else None,
        'newest': pick(max(dated, key=lambda p: p['year'])) if dated else None,
        'prev': prev, 'new_artists': new_artists, 'obsession': obsession,
        'personality': _personality(top_artist, top_n / total, avg_year, len(genres), clock),
        'days_listened': len(by_date), 'days_total': len(by_day),
    }
    if kind == 'year':
        out.update(_year_extras(plays))
    return out
