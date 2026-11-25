"""HTML for the monthly Wrapped pages, the archive and latest.json."""
import calendar, hashlib
from datetime import date
from html import escape

ACCENTS = {
    'intro': '#1ed760', 'artist': '#ff4f9a', 'top-artists': '#ff8a3d', 'song': '#8b5cf6',
    'genres': '#22d3ee', 'clock': '#facc15', 'streak': '#f43f5e', 'time': '#f59e0b',
    'compare': '#34d399', 'personality': '#a78bfa', 'summary': '#1ed760',
    'months': '#60a5fa', 'monthly-artists': '#fb7185', 'days': '#4ade80',
}
SHORT_MONTH = 10  # fewer plays than this: only the intro and summary slides


def e(x):
    return escape(str(x), quote=True)


def _date(iso, weekday=True):
    d = date.fromisoformat(iso)
    return d.strftime('%A %-d %B') if weekday else d.strftime('%-d %B')


def _plural(n, word):
    return f'{n} {word}' + ('' if n == 1 else 's')


def _cover(album_id, covers, name, cls='cover'):
    if album_id in covers:
        return f'<img class="{cls}" src="{e(covers[album_id])}" alt="" loading="lazy">'
    hue = int(hashlib.md5(str(album_id).encode()).hexdigest()[:4], 16) % 360
    initials = ''.join([w[0] for w in str(name).split() if w[:1].isalnum()][:2]).upper() or '♪'
    return f'<div class="{cls} ph" style="--h:{hue}" aria-hidden="true">{e(initials)}</div>'


def _slide(name, body):
    return f'<section class="slide" data-slide="{name}" style="--accent:{ACCENTS[name]}">{body}</section>'


def _bars(values, labels, cls='bars'):
    top = max(values) or 1
    cols = ''.join(f'<div class="bar" style="--v:{v / top:.3f}" title="{e(l)}: {v}"><span>{e(l)}</span></div>'
                   for v, l in zip(values, labels))
    return f'<div class="{cls}">{cols}</div>'


def _hour_bars(by_hour):
    return _bars(by_hour, [f'{h:02d}' if h % 6 == 0 else '' for h in range(24)], 'bars hours')


def _slides(s, covers):
    is_year = s.get('kind') == 'year'
    when = s['label'] if is_year else s['label'].split()[0]   # "2026" or "October"
    unit = 'year' if is_year else 'month'
    of = f' of {s["label"]}' if is_year else ''
    so_far = ' <span class="badge">so far</span>' if s['so_far'] else ''
    out = [_slide('intro', f'''
        <p class="kicker">Your {e(when)}{so_far}</p>
        <h1 class="mega">Wrapped</h1>
        <div class="nums">
          <div><b>{s["plays"]}</b><span>plays</span></div>
          <div><b>{s["hours"]}</b><span>hours</span></div>
          <div><b>{s["artist_count"]}</b><span>artists</span></div>
          <div><b>{s["song_count"]}</b><span>songs</span></div>
        </div>
        <p class="hint">Tap to continue →</p>''')]

    if s['plays'] >= SHORT_MONTH and is_year:
        bm = s['busiest_month']
        out.append(_slide('months', f'''
            <p class="kicker">Your year, month by month</p><h2 class="name">{e(bm["month"])}</h2>
            {_bars(s["by_month"], [calendar.month_abbr[m][0] for m in range(1, 13)], "bars months")}
            <p class="sub">was your busiest month: {_plural(bm["plays"], "play")}.</p>'''))

    if s['plays'] >= SHORT_MONTH:
        a = s['top_artists'][0]
        out.append(_slide('artist', f'''
            <p class="kicker">Your #1 artist{e(of)} was</p>
            {_cover(a["album_id"], covers, a["name"], "cover big")}
            <h2 class="name">{e(a["name"])}</h2>
            <p class="sub">{_plural(a["plays"], "play")} · {a["minutes"]} minutes together</p>'''))
        rows = ''.join(f'<li><span class="rank">{i}</span>{_cover(x["album_id"], covers, x["name"], "cover sm")}'
                       f'<span class="t">{e(x["name"])}</span><span class="n">{x["plays"]}</span></li>'
                       for i, x in enumerate(s['top_artists'][:5], 1))
        out.append(_slide('top-artists', f'<p class="kicker">Your top artists</p><ol class="top">{rows}</ol>'))
        if is_year:
            rows = ''.join(f'<li><span class="rank">{e(x["month"][:3])}</span><span class="t">{e(x["name"])}</span>'
                           f'<span class="n">{x["plays"]}</span></li>' for x in s['top_artist_by_month'])
            out.append(_slide('monthly-artists', f'''
                <p class="kicker">Your phases: top artist each month</p><ol class="top months">{rows}</ol>'''))

        t = s['top_songs'][0]
        binge = ''
        if t['best_day']['plays'] >= 3:
            binge = (f'<p class="aside">Including {t["best_day"]["plays"]} times on '
                     f'{e(_date(t["best_day"]["date"]))}. We\'re not judging.</p>')
        out.append(_slide('song', f'''
            <p class="kicker">Your song{e(of) if is_year else ' of the month'}</p>
            {_cover(t["album_id"], covers, t["title"], "cover big")}
            <h2 class="name">{e(t["title"])}</h2>
            <p class="sub">{e(t["artist"])} · {_plural(t["plays"], "play")}</p>{binge}'''))

        if s['genres']:
            g5 = s['genres'][:5]
            top = g5[0]['plays']
            rows = ''.join(f'<li><span class="t">{e(g["name"])}</span>'
                           f'<span class="meter" style="--v:{g["plays"] / top:.3f}"></span></li>' for g in g5)
            explored = (f'You explored {s["genre_count"]} genres.' if s['genre_count'] > 1
                        else 'One genre. Commitment.')
            out.append(_slide('genres', f'''
                <p class="kicker">Your top genre</p><h2 class="name">{e(g5[0]["name"])}</h2>
                <ul class="meters">{rows}</ul><p class="sub">{explored}</p>'''))

        clock_line = {
            'Night Owl': 'The best music happens after dark, apparently.',
            'Early Bird': 'Music before coffee. Respect.',
            '9-to-5 Listener': 'Your boss thinks you are working.',
            'Evening Unwinder': 'Home, shoes off, music on.',
        }[s['clock_label']]
        out.append(_slide('clock', f'''
            <p class="kicker">Your prime time</p><h2 class="name">{s["peak_hour"]:02d}:00</h2>
            {_hour_bars(s["by_hour"])}
            <p class="sub"><b>{e(s["clock_label"])}</b>. {clock_line}</p>'''))

        st, bd = s['longest_streak'], s['biggest_day']
        streak = (f'{st["days"]} days in a row' if st['days'] > 1 else 'One day at a time')
        span = (f'{e(_date(st["start"], False))} to {e(_date(st["end"], False))}' if st['days'] > 1
                else 'No streak yet. Next month?')
        out.append(_slide('streak', f'''
            <p class="kicker">Your longest streak</p><h2 class="name">{streak}</h2><p class="sub">{span}</p>
            <div class="card"><p class="kicker">Biggest day</p>
            <p><b>{e(_date(bd["date"]))}</b>: {_plural(bd["plays"], "play")}, {bd["hours"]} h,
            mostly {e(bd["top_artist"])}.</p></div>'''))

        if is_year:
            share = s['days_listened'] / s['days_total']
            quip = ('Music is basically your oxygen.' if share >= 0.8 else
                    'Most days come with a soundtrack.' if share >= 0.5 else
                    'Quality over quantity, right?')
            out.append(_slide('days', f'''
                <p class="kicker">Days with music</p><h2 class="mega">{s["days_listened"]}</h2>
                <p class="sub">You listened on {s["days_listened"]} of {s["days_total"]} days. {quip}</p>'''))

        if s['avg_year']:
            o, n = s['oldest'], s['newest']
            out.append(_slide('time', f'''
                <p class="kicker">On average you listened like it's</p><h2 class="mega">{s["avg_year"]}</h2>
                <p class="sub">Oldest: <b>{e(o["title"])}</b> by {e(o["artist"])} ({o["year"]})</p>
                <p class="sub">Newest: <b>{e(n["title"])}</b> by {e(n["artist"])} ({n["year"]})</p>'''))

        if s['prev']:
            p = s['prev']
            diff = s['hours'] - p['hours']
            change = (f'{diff:+.1f} hours compared with last {unit}' if abs(diff) >= 0.1
                      else f'Exactly as much as last {unit}. Consistent.')
            obs = ''
            if s['obsession']:
                obs = (f'<div class="card"><p class="kicker">Obsession of the {unit}</p>'
                       f'<p><b>{e(s["obsession"]["name"])}</b>: +{_plural(s["obsession"]["delta"], "play")}'
                       f' compared with last {unit}.</p></div>')
            new = s['new_artists']
            new_line = (f'<p class="sub">{_plural(len(new), "new artist")} discovered, like '
                        f'{", ".join(e(x) for x in new[:3])}.</p>' if new else '')
            out.append(_slide('compare', f'''
                <p class="kicker">Compared with last {unit}</p><h2 class="name">{e(change)}</h2>
                {new_line}{obs}'''))

        pers = s['personality']
        out.append(_slide('personality', f'''
            <p class="kicker">Your listening personality</p><h2 class="name">{e(pers["title"])}</h2>
            <p class="sub">{e(pers["roast"])}</p>'''))

    top3 = lambda xs, f: ''.join(f'<li>{f(x)}</li>' for x in xs[:3])
    genre = f'<div><span>Top genre</span><b>{e(s["genres"][0]["name"])}</b></div>' if s['genres'] else ''
    out.append(_slide('summary', f'''
        <p class="kicker">{e(s["label"])}{so_far}</p>
        <div class="summary">
          <div><span>Top artists</span><ol>{top3(s["top_artists"], lambda x: e(x["name"]))}</ol></div>
          <div><span>Top songs</span><ol>{top3(s["top_songs"], lambda x: e(x["title"]))}</ol></div>
          <div><span>Listening time</span><b>{s["hours"]} h</b></div>{genre}
          <div class="wide"><span>Personality</span><b>{e(s["personality"]["title"])}</b></div>
        </div>
        <div class="actions"><button class="btn" data-action="stats">See all stats</button>
        <button class="btn ghost" data-action="replay">Replay</button></div>'''))
    return out


def _table(rows, cols):
    head = ''.join(f'<th>{c}</th>' for c in cols)
    return f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _stats_page(s, covers):
    days = [d['plays'] for d in s['by_day']]
    day_labels = [d['date'][-2:].lstrip('0') if i % 5 == 0 else '' for i, d in enumerate(s['by_day'])]
    artists = [f'<tr><td>{i}</td><td class="who">{_cover(a["album_id"], covers, a["name"], "cover xs")}'
               f'{e(a["name"])}</td><td>{a["plays"]}</td><td>{a["minutes"]} min</td></tr>'
               for i, a in enumerate(s['top_artists'], 1)]
    songs = [f'<tr><td>{i}</td><td class="who">{_cover(t["album_id"], covers, t["title"], "cover xs")}'
             f'<span>{e(t["title"])}<small>{e(t["artist"])}</small></span></td><td>{t["plays"]}</td></tr>'
             for i, t in enumerate(s['top_songs'], 1)]
    albums = [f'<tr><td>{i}</td><td class="who">{_cover(a["album_id"], covers, a["name"], "cover xs")}'
              f'<span>{e(a["name"])}<small>{e(a["artist"])}</small></span></td><td>{a["plays"]}</td></tr>'
              for i, a in enumerate(s['top_albums'], 1)]
    parts = [
        f'<header><a href="../" class="back">← All Wrapped</a><h1>{e(s["label"])}'
        f'{" <span class=badge>so far</span>" if s["so_far"] else ""}</h1>'
        f'<p>{s["plays"]} plays · {s["hours"]} hours · {s["artist_count"]} artists · {s["song_count"]} songs</p>'
        f'<button class="btn ghost" data-action="replay">▶ Play the story</button></header>',
        (f'<div class="panel"><h2>Plays per month</h2>'
         f'{_bars(s["by_month"], [calendar.month_abbr[m] for m in range(1, 13)], "bars months")}</div>'
         if s.get('kind') == 'year' else
         f'<div class="panel"><h2>Plays per day</h2>{_bars(days, day_labels, "bars days")}</div>'),
        f'<div class="panel"><h2>Plays per hour</h2>{_hour_bars(s["by_hour"])}'
        f'<p class="muted">Peak at {s["peak_hour"]:02d}:00 · {e(s["clock_label"])}</p></div>',
        f'<div class="panel"><h2>Top artists</h2>{_table(artists, ["#", "Artist", "Plays", "Time"])}</div>',
        f'<div class="panel"><h2>Top songs</h2>{_table(songs, ["#", "Song", "Plays"])}</div>',
        f'<div class="panel"><h2>Top albums</h2>{_table(albums, ["#", "Album", "Plays"])}</div>',
    ]
    if s['genres']:
        top = s['genres'][0]['plays']
        rows = ''.join(f'<li><span class="t">{e(g["name"])}</span><span class="meter" style="--v:{g["plays"] / top:.3f}">'
                       f'</span><span class="n">{g["plays"]}</span></li>' for g in s['genres'][:15])
        parts.append(f'<div class="panel"><h2>Genres ({s["genre_count"]})</h2><ul class="meters">{rows}</ul></div>')
    if s['prev']:
        p = s['prev']
        unit = 'year' if s.get('kind') == 'year' else 'month'
        rows = [f'<tr><td>Plays</td><td>{p["plays"]}</td><td>{s["plays"]}</td></tr>',
                f'<tr><td>Hours</td><td>{p["hours"]}</td><td>{s["hours"]}</td></tr>',
                f'<tr><td>New artists</td><td></td><td>{len(s["new_artists"])}</td></tr>']
        new = ''.join(f'<li>{e(a)}</li>' for a in s['new_artists'])
        parts.append(f'<div class="panel"><h2>Compared with last {unit}</h2>'
                     f'{_table(rows, ["", f"Last {unit}", f"This {unit}"])}'
                     + (f'<h3>New artists</h3><ul class="chips">{new}</ul>' if new else '') + '</div>')
    return f'<section id="stats" class="stats" hidden>{"".join(parts)}</section>'


def _doc(title, body, extra_head=''):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0b0f">
<title>{e(title)}</title>{extra_head}</head>
<body>{body}</body></html>
'''


def render_month(s, covers):
    slides = ''.join(_slides(s, covers))
    body = f'''<main class="story" aria-label="{e(s["label"])} Wrapped">
  <div class="progress"></div>
  <button class="close" data-action="stats" aria-label="Skip to all stats">✕</button>
  {slides}
</main>
{_stats_page(s, covers)}
<script src="../assets/wrapped.js"></script>'''
    title = f'{s["label"]} Wrapped' + (' (so far)' if s['so_far'] else '')
    return _doc(title, body, '<link rel="stylesheet" href="../assets/wrapped.css">')


def summary(s, covers=None):
    a = s['top_artists'][0]
    t = s['top_songs'][0]
    cover = (covers or {}).get(a['album_id'])
    return {'kind': s.get('kind', 'month'), 'month': s['month'], 'label': s['label'], 'so_far': s['so_far'],
            'plays': s['plays'],
            'hours': s['hours'], 'top_artist': a['name'], 'top_artist_album': a['album_id'],
            'cover': f'{s["month"]}/{cover}' if cover else None,
            'top_song': f'{t["title"]} – {t["artist"]}',
            'top_genre': s['genres'][0]['name'] if s['genres'] else None,
            'personality': s['personality']['title']}


def latest_json(sm):
    return {'month': sm['label'] + (' (so far)' if sm['so_far'] else ''), 'top_artist': sm['top_artist'],
            'top_song': sm['top_song'], 'top_genre': sm['top_genre'] or '–', 'plays': sm['plays'],
            'hours': f'{sm["hours"]} h', 'personality': sm['personality']}


def _cards(summaries):
    cards = []
    for sm in sorted(summaries, key=lambda x: x['month'], reverse=True):
        badge = ' <span class="badge">so far</span>' if sm['so_far'] else ''
        art = (f'<img class="cover" src="{e(sm["cover"])}" alt="" loading="lazy">' if sm.get('cover')
               else _cover(sm['top_artist_album'], {}, sm['top_artist']))
        cards.append(f'''<a class="month" href="{e(sm["month"])}/">{art}
  <div><h2>{e(sm["label"])}{badge}</h2>
  <p>{e(sm["top_artist"])} · {sm["plays"]} plays · {sm["hours"]} h</p>
  <p class="muted">{e(sm["personality"])}</p></div></a>''')
    return ''.join(cards)


def render_index(summaries):
    years = [sm for sm in summaries if sm.get('kind') == 'year']
    months = [sm for sm in summaries if sm.get('kind', 'month') == 'month']
    sections = ''
    if years:
        sections += f'<h2 class="section">Years</h2>{_cards(years)}'
    if months:
        sections += f'<h2 class="section">Months</h2>{_cards(months)}'
    body = f'''<main class="archive"><h1>Wrapped</h1><p class="muted">Your Navidrome listening, month by month.</p>
{sections or '<p>Nothing yet. Play some music!</p>'}</main>'''
    return _doc('Wrapped', body, '<link rel="stylesheet" href="assets/wrapped.css">')
