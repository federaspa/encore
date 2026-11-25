# Encore 🎶

Your year in music, encore included. A "Spotify Wrapped" for your self-hosted [Navidrome](https://www.navidrome.org/) server:
monthly and yearly recaps of what you listened to, as swipeable story slides plus a full stats page.

- Top artists, songs, albums and genres, with album covers
- Listening clock, longest streak, busiest days, comparison with the previous period, a "listening personality"
- Yearly recap with month-by-month charts
- Static pages: no JavaScript or CSS libraries, no external requests, works offline on your LAN
- Python 3 standard library only (tested on 3.13), no dependencies

## How it works

`generate.py` reads Navidrome's SQLite database (read-only) for the scrobbles of a month or year,
downloads the album covers it needs through Navidrome's Subsonic API, and writes static HTML into `site/`.
Any web server can serve `site/`; `compose.yaml` runs nginx on port 8090.

```
site/
  index.html          archive: one card per month / year
  2026-10/            a month's Wrapped (index.html, summary.json, covers/)
  2026/               a year's Wrapped
  latest.json         headline numbers of the newest month (for dashboards)
  assets/             shared CSS and JS
```

## Setup

1. Clone the repo next to (or anywhere that can read) your Navidrome data folder.
2. `cp wrapped.env.example wrapped.env && chmod 600 wrapped.env`, then fill it in.
   The Subsonic token is `md5(password + salt)`:
   `python3 -c "import hashlib; print(hashlib.md5(b'PASSWORD' b'SALT').hexdigest())"`
3. Build something: `python3 generate.py --current`
4. Serve it: `docker compose up -d`, then open `http://<host>:8090`.

The database is opened read-only, so it is safe to run while Navidrome is up.
Navidrome must have scrobbling to its own database enabled (the default), since that is where plays are counted.

## Usage

```
python3 generate.py             the previous month
python3 generate.py 2026-10     a given month (re-running overwrites it)
python3 generate.py --current   this month so far
python3 generate.py 2026        a given year (the current year: so far)
python3 generate.py --year      in January the full previous year, otherwise this year up to last month
```

Each run also rebuilds `site/index.html` and `site/latest.json`.
Direct links: `<month>/#stats` opens the stats page, `<month>/#slide-3` a given slide.

### Cron

```cron
# Last month, on the 1st
0 6 1 * * /usr/bin/python3 /path/to/wrapped/generate.py >> /path/to/wrapped/generate.log 2>&1
# Yearly: Dec 1 = Jan–Nov so far, Jan 1 = the full previous year
30 6 1 12,1 * /usr/bin/python3 /path/to/wrapped/generate.py --year >> /path/to/wrapped/generate.log 2>&1
```

### Homepage widget (optional)

`latest.json` works with [Homepage](https://gethomepage.dev/)'s `customapi` widget:

```yaml
- Wrapped:
    href: http://<host>:8090
    description: Monthly music recap
    icon: mdi-music-box-multiple
    widget:
      type: customapi
      url: http://<host>:8090/latest.json
      mappings:
        - field: month
          label: Month
        - field: top_artist
          label: Top artist
        - field: hours
          label: Hours
```

## Tests

```
python3 -m unittest discover -s tests -t .
```

## License

[MIT](LICENSE)
