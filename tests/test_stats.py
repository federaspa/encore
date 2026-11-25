import os, sqlite3, sys, tempfile, unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.fixtures import make_db
import stats

UTC = timezone.utc
TZ = 'Europe/Berlin'
ZONE = ZoneInfo(TZ)


def utc(y, m, d, h=12, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC)


def local(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=ZONE)


def song(when, title='Song', artist='Artist', album='Album', dur=200, year=2000, genres=None):
    return (when, title, artist, album, dur, year, genres or [])


class StatsTest(unittest.TestCase):
    def db(self, plays):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'nd.db')
        make_db(path, plays)
        return path

    def oct(self, plays, **kw):
        return stats.month_stats(self.db(plays), 2026, 10, **{'tz': TZ, **kw})

    def test_counts_and_hours(self):
        s = self.oct([song(utc(2026, 10, 2))] * 3 + [song(utc(2026, 10, 3), title='Other', dur=160)])
        self.assertEqual(s['plays'], 4)
        self.assertEqual(s['hours'], 0.2)
        self.assertEqual(s['song_count'], 2)
        self.assertEqual(s['top_songs'][0]['plays'], 3)
        self.assertEqual(s['label'], 'October 2026')
        self.assertFalse(s['so_far'])

    def test_local_month_boundary(self):
        path = self.db([song(utc(2026, 9, 30, 22, 30))])
        s = stats.month_stats(path, 2026, 10, tz=TZ)
        self.assertEqual(s['plays'], 1)
        self.assertEqual(s['by_hour'][0], 1)
        self.assertIsNone(stats.month_stats(path, 2026, 9, tz=TZ))

    def test_missing_media_file_dropped(self):
        path = self.db([song(utc(2026, 10, 2))])
        c = sqlite3.connect(path)
        c.execute("insert into scrobbles(media_file_id, user_id, submission_time) values ('gone','u1',?)",
                  (int(utc(2026, 10, 3).timestamp()),))
        c.commit()
        self.assertEqual(stats.month_stats(path, 2026, 10, tz=TZ)['plays'], 1)

    def test_missing_flag_still_counted(self):
        path = self.db([song(utc(2026, 10, 2))])
        c = sqlite3.connect(path)
        c.execute('update media_file set missing = 1')
        c.commit()
        self.assertEqual(stats.month_stats(path, 2026, 10, tz=TZ)['plays'], 1)

    def test_genres_from_tags_multi(self):
        path = self.db([song(utc(2026, 10, 2), genres=['Rock', 'Folk'])] * 2 + [song(utc(2026, 10, 2), title='B')])
        c = sqlite3.connect(path)
        c.execute("update media_file set genre='Pop; Indie' where title='B'")
        c.commit()
        s = stats.month_stats(path, 2026, 10, tz=TZ)
        g = {x['name']: x['plays'] for x in s['genres']}
        self.assertEqual(g, {'Rock': 2, 'Folk': 2, 'Pop': 1, 'Indie': 1})
        self.assertEqual(s['genre_count'], 4)

    def test_streak_and_biggest_day(self):
        s = self.oct([song(utc(2026, 10, d)) for d in (3, 4, 5, 9, 9)])
        self.assertEqual(s['longest_streak'], {'days': 3, 'start': '2026-10-03', 'end': '2026-10-05'})
        self.assertEqual(s['biggest_day']['date'], '2026-10-09')
        self.assertEqual(s['biggest_day']['plays'], 2)
        self.assertEqual(s['biggest_day']['top_artist'], 'Artist')

    def test_clock_labels(self):
        def label(hours):
            return self.oct([song(local(2026, 10, 5 + i % 20, h), title=f't{i}') for i, h in enumerate(hours)])['clock_label']
        self.assertEqual(label([23] * 3 + [14] * 7), 'Night Owl')
        self.assertEqual(label([6] * 3 + [14] * 7), 'Early Bird')
        self.assertEqual(label([14] * 10), '9-to-5 Listener')
        self.assertEqual(label([19] * 10), 'Evening Unwinder')

    def test_years(self):
        s = self.oct([song(utc(2026, 10, 2), title='a', year=1970), song(utc(2026, 10, 2), title='b', year=1980),
                      song(utc(2026, 10, 2), title='c', year=0)])
        self.assertEqual(s['avg_year'], 1975)
        self.assertEqual(s['oldest']['year'], 1970)
        self.assertEqual(s['newest']['year'], 1980)

    def test_prev_and_obsession(self):
        plays = [song(utc(2026, 9, 10), artist='A')] + [song(utc(2026, 10, 2), artist='A')] * 5 \
            + [song(utc(2026, 10, 3), artist='B', title='x')] * 2
        s = self.oct(plays)
        self.assertEqual(s['prev']['plays'], 1)
        self.assertEqual(s['obsession'], {'name': 'A', 'delta': 4})
        self.assertEqual(s['new_artists'], ['B'])

    def test_no_prev(self):
        s = self.oct([song(utc(2026, 10, 2))])
        self.assertIsNone(s['prev'])
        self.assertEqual(s['new_artists'], [])
        self.assertIsNone(s['obsession'])

    def test_until_cuts_month(self):
        s = self.oct([song(utc(2026, 10, 2)), song(utc(2026, 10, 20))], until=local(2026, 10, 17, 18))
        self.assertEqual(s['plays'], 1)
        self.assertEqual(len(s['by_day']), 17)
        self.assertTrue(s['so_far'])

    def test_empty_artist_ignored(self):
        s = self.oct([song(utc(2026, 10, 2), artist='', title='x')] * 8 + [song(utc(2026, 10, 3), artist='Real')] * 4)
        self.assertEqual(s['top_artists'][0]['name'], 'Real')
        self.assertEqual(s['artist_count'], 1)
        self.assertIn('Real', s['personality']['roast'])
        self.assertEqual(s['plays'], 12)

    def test_only_empty_artists_still_renders_name(self):
        s = self.oct([song(utc(2026, 10, 2), artist='')])
        self.assertEqual(s['top_artists'][0]['name'], 'Unknown artist')

    def test_month_kind(self):
        self.assertEqual(self.oct([song(utc(2026, 10, 2))])['kind'], 'month')

    def year(self, plays, **kw):
        return stats.year_stats(self.db(plays), 2026, **{'tz': TZ, **kw})

    def test_year_basic(self):
        s = self.year([song(utc(2026, 1, 5), artist='A'), song(utc(2026, 3, 2), artist='B', title='b'),
                       song(utc(2026, 3, 2), artist='B', title='b'), song(utc(2026, 12, 31, 20), artist='A')])
        self.assertEqual((s['kind'], s['month'], s['label'], s['plays']), ('year', '2026', '2026', 4))
        self.assertEqual(s['by_month'], [1, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(s['top_artist_by_month'], [{'month': 'January', 'name': 'A', 'plays': 1},
                                                    {'month': 'March', 'name': 'B', 'plays': 2},
                                                    {'month': 'December', 'name': 'A', 'plays': 1}])
        self.assertEqual((s['days_listened'], s['days_total']), (3, 365))
        self.assertEqual(s['busiest_month'], {'month': 'March', 'plays': 2})
        self.assertIsNone(s['prev'])

    def test_year_boundary_local(self):
        path = self.db([song(utc(2026, 12, 31, 23, 30))])  # 00:30 on Jan 1 in Berlin
        self.assertIsNone(stats.year_stats(path, 2026, tz=TZ))
        self.assertEqual(stats.year_stats(path, 2027, tz=TZ)['plays'], 1)

    def test_year_prev_year(self):
        s = self.year([song(utc(2025, 6, 1), artist='A')] + [song(utc(2026, 6, 1), artist='A')] * 3)
        self.assertEqual(s['prev']['plays'], 1)
        self.assertEqual(s['obsession'], {'name': 'A', 'delta': 2})

    def test_year_until(self):
        s = self.year([song(utc(2026, 11, 30)), song(utc(2026, 12, 2))], until=local(2026, 12, 1, 0))
        self.assertEqual(s['plays'], 1)
        self.assertTrue(s['so_far'])
        self.assertEqual(s['days_total'], 334)

    def test_empty_month_returns_none(self):
        self.assertIsNone(self.oct([song(utc(2026, 8, 2))]))

    def test_personality(self):
        loyal = self.oct([song(utc(2026, 10, 2, 14), year=2020)] * 5 + [song(utc(2026, 10, 2, 14), artist='Z', title='z')])
        self.assertTrue(loyal['personality']['title'].startswith('The Loyal'))
        self.assertTrue(loyal['personality']['title'].endswith('9-to-5 Listener'))
        self.assertIn('Artist', loyal['personality']['roast'])
        nost = self.oct([song(utc(2026, 10, 2, 14), artist=f'a{i}', title=f't{i}', year=1975) for i in range(10)])
        self.assertTrue(nost['personality']['title'].startswith('The Nostalgic'))


if __name__ == '__main__':
    unittest.main()
