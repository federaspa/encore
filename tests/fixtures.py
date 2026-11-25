"""Build a minimal navidrome-like SQLite DB for tests."""
import json, sqlite3


def make_db(path, plays):
    """plays: list of (utc_datetime, title, artist, album, duration_s, year, genres_list)."""
    c = sqlite3.connect(path)
    c.executescript('''
        create table media_file(id text primary key, title text, artist text, album text,
            album_id text, duration real, year int, original_year int, genre text,
            tags text, missing bool default false);
        create table scrobbles(id integer primary key, media_file_id text, user_id text,
            submission_time int);
    ''')
    ids = {}
    for i, (when, title, artist, album, dur, year, genres) in enumerate(plays):
        key = (title, artist)
        if key not in ids:
            ids[key] = f'mf{len(ids)}'
            tags = {'genre': [{'id': 'x', 'value': g} for g in genres]} if genres else {}
            c.execute('insert into media_file values (?,?,?,?,?,?,?,?,?,?,0)',
                      (ids[key], title, artist, album, f'al-{album}', dur, year, 0, '', json.dumps(tags)))
        c.execute('insert into scrobbles(media_file_id, user_id, submission_time) values (?,?,?)',
                  (ids[key], 'u1', int(when.timestamp())))
    c.commit()
    c.close()
