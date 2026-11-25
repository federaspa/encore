import copy, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import render

BASE = {
    'month': '2026-10', 'label': 'October 2026', 'so_far': False, 'plays': 40, 'hours': 2.5,
    'artist_count': 3, 'song_count': 5,
    'top_artists': [{'name': 'Simon & Garfunkel <3', 'plays': 20, 'minutes': 80, 'album_id': 'al1'},
                    {'name': 'B', 'plays': 10, 'minutes': 30, 'album_id': 'al2'}],
    'top_songs': [{'title': 'The "Boxer"', 'artist': 'Simon & Garfunkel <3', 'plays': 6, 'album_id': 'al1',
                   'best_day': {'date': '2026-10-05', 'plays': 4}}],
    'top_albums': [{'name': 'Bridge', 'artist': 'Simon & Garfunkel <3', 'plays': 20, 'album_id': 'al1'}],
    'genres': [{'name': 'Folk', 'plays': 30}, {'name': 'Rock', 'plays': 10}], 'genre_count': 2,
    'by_hour': [1] * 24, 'by_day': [{'date': f'2026-10-{d:02d}', 'plays': 1} for d in range(1, 32)],
    'peak_hour': 20, 'clock_label': 'Night Owl',
    'longest_streak': {'days': 3, 'start': '2026-10-03', 'end': '2026-10-05'},
    'biggest_day': {'date': '2026-10-05', 'plays': 9, 'hours': 0.6, 'top_artist': 'B'},
    'avg_year': 1974, 'oldest': {'title': 'Old', 'artist': 'B', 'year': 1965},
    'newest': {'title': 'New', 'artist': 'B', 'year': 2020},
    'prev': {'plays': 20, 'hours': 1.0}, 'new_artists': ['B'], 'obsession': {'name': 'B', 'delta': 8},
    'personality': {'title': 'The Nostalgic Night Owl', 'roast': 'Old soul.'},
}


def stats(**kw):
    s = copy.deepcopy(BASE)
    s.update(kw)
    return s


class RenderTest(unittest.TestCase):
    def test_escapes_text(self):
        html = render.render_month(stats(), {})
        self.assertIn('Simon &amp; Garfunkel &lt;3', html)
        self.assertNotIn('Garfunkel <3', html)
        self.assertNotIn('The "Boxer"', html)

    def test_all_slides_present(self):
        html = render.render_month(stats(), {'al1': 'covers/al1.jpg'})
        for name in ('intro', 'artist', 'top-artists', 'song', 'genres', 'clock', 'streak', 'time', 'compare',
                     'personality', 'summary'):
            self.assertIn(f'data-slide="{name}"', html)
        self.assertIn('id="stats"', html)
        self.assertIn('src="covers/al1.jpg"', html)
        self.assertIn('../assets/wrapped.js', html)

    def test_skips_genre_and_compare(self):
        html = render.render_month(stats(genres=[], genre_count=0, prev=None, new_artists=[], obsession=None), {})
        self.assertNotIn('data-slide="genres"', html)
        self.assertNotIn('data-slide="compare"', html)
        self.assertIn('data-slide="summary"', html)

    def test_short_month(self):
        html = render.render_month(stats(plays=4), {})
        self.assertIn('data-slide="intro"', html)
        self.assertIn('data-slide="summary"', html)
        self.assertNotIn('data-slide="artist"', html)
        self.assertIn('id="stats"', html)

    def test_binge_line(self):
        self.assertIn('4 times on', render.render_month(stats(), {}))
        s = stats()
        s['top_songs'][0]['best_day']['plays'] = 2
        self.assertNotIn('times on', render.render_month(s, {}))

    def test_cover_placeholder(self):
        html = render.render_month(stats(), {})
        self.assertIn(' ph" style="--h:', html)
        self.assertIn('>SG<', html)

    def test_so_far_label(self):
        self.assertIn('so far', render.render_month(stats(so_far=True), {}))

    def test_index_newest_first(self):
        sept = render.summary(stats(month='2026-09', label='September 2026'))
        octo = render.summary(stats(so_far=True))
        html = render.render_index([sept, octo])
        self.assertLess(html.index('October 2026'), html.index('September 2026'))
        self.assertIn('so far', html)
        self.assertIn('href="2026-10/"', html)

    def test_summary_and_latest(self):
        sm = render.summary(stats())
        self.assertEqual(sm['top_artist'], 'Simon & Garfunkel <3')
        self.assertEqual(sm['top_genre'], 'Folk')
        lj = render.latest_json(render.summary(stats(so_far=True)))
        self.assertEqual(lj['month'], 'October 2026 (so far)')
        self.assertEqual(lj['hours'], '2.5 h')
        self.assertEqual(lj['top_artist'], 'Simon & Garfunkel <3')
        self.assertIsNone(render.summary(stats(genres=[]))['top_genre'])

    def test_year_page(self):
        y = stats(kind='year', month='2026', label='2026', by_month=[0] * 8 + [2, 38, 0, 0],
                  top_artist_by_month=[{'month': 'September', 'name': 'B', 'plays': 2},
                                       {'month': 'October', 'name': 'Simon & Garfunkel <3', 'plays': 20}],
                  busiest_month={'month': 'October', 'plays': 38}, days_listened=12, days_total=334)
        html = render.render_month(y, {})
        for name in ('months', 'monthly-artists', 'days'):
            self.assertIn(f'data-slide="{name}"', html)
        self.assertIn('Your 2026', html)
        self.assertIn('of 2026', html)
        self.assertIn('12 of 334 days', html)
        self.assertIn('Plays per month', html)
        self.assertNotIn('Plays per day', html)
        self.assertIn('Compared with last year', html)

    def test_month_page_has_no_year_slides(self):
        html = render.render_month(stats(), {})
        self.assertNotIn('data-slide="months"', html)
        self.assertIn('Compared with last month', html)

    def test_index_years_section(self):
        y = render.summary(stats(kind='year', month='2026', label='2026'))
        m = render.summary(stats())
        html = render.render_index([m, y])
        self.assertIn('href="2026/"', html)
        self.assertLess(html.index('Years'), html.index('Months'))

    def test_no_secrets(self):
        html = render.render_month(stats(), {})
        self.assertNotIn('ND_TOKEN', html)
        self.assertNotIn('6338b8df', html)


if __name__ == '__main__':
    unittest.main()
