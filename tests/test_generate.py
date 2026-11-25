import json, os, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.fixtures import make_db
import generate

UTC = timezone.utc


def p(d, m=10, artist='Artist', title='Song'):
    return (datetime(2026, m, d, 12, tzinfo=UTC), title, artist, 'Album', 200, 2000, ['Rock'])


class GenerateTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.site = self.dir / 'site'
        self.db = self.dir / 'nd.db'
        make_db(str(self.db), [p(d) for d in range(1, 13)] + [p(5, m=9, artist='Old')] * 12)
        self.env = self.dir / 'w.env'
        self.env.write_text(f'ND_DB={self.db}\nND_TOKEN=SECRET123\n')
        patcher = mock.patch('generate.fetch_covers', return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, argv, now=None):
        return generate.main(argv, env_path=str(self.env), site=self.site, now=now)

    def test_builds_month_and_index(self):
        self.assertEqual(self.run_main(['2026-10']), 0)
        page = (self.site / '2026-10' / 'index.html').read_text()
        self.assertIn('October 2026', page)
        self.assertNotIn('SECRET123', page)
        self.assertTrue((self.site / 'assets' / 'wrapped.css').exists())
        self.assertIn('href="2026-10/"', (self.site / 'index.html').read_text())
        self.assertEqual(json.loads((self.site / '2026-10' / 'summary.json').read_text())['plays'], 12)

    def test_default_is_previous_month(self):
        self.run_main([], now=datetime(2026, 11, 1, 6, tzinfo=UTC))
        self.assertTrue((self.site / '2026-10' / 'index.html').exists())

    def test_current_is_so_far(self):
        self.run_main(['--current'], now=datetime(2026, 10, 7, 12, tzinfo=UTC))
        sm = json.loads((self.site / '2026-10' / 'summary.json').read_text())
        self.assertTrue(sm['so_far'])
        self.assertEqual(sm['plays'], 6)

    def test_explicit_current_month_is_so_far(self):
        self.run_main(['2026-10'], now=datetime(2026, 10, 7, 12, tzinfo=UTC))
        sm = json.loads((self.site / '2026-10' / 'summary.json').read_text())
        self.assertTrue(sm['so_far'])
        self.assertEqual(sm['plays'], 6)

    def test_no_plays_writes_nothing(self):
        self.assertEqual(self.run_main(['2026-08']), 0)
        self.assertFalse((self.site / '2026-08').exists())

    def test_missing_db_returns_1_and_keeps_site(self):
        self.run_main(['2026-10'])
        before = (self.site / '2026-10' / 'index.html').read_text()
        self.env.write_text('ND_DB=/nonexistent/nd.db\n')
        self.assertEqual(self.run_main(['2026-10']), 1)
        self.assertEqual((self.site / '2026-10' / 'index.html').read_text(), before)

    def test_render_error_keeps_old_month(self):
        self.run_main(['2026-10'])
        before = (self.site / '2026-10' / 'index.html').read_text()
        with mock.patch('generate.render_month', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.run_main(['2026-10'])
        self.assertEqual((self.site / '2026-10' / 'index.html').read_text(), before)
        self.assertEqual([x.name for x in self.site.iterdir() if x.name.startswith('.tmp')], [])

    def test_latest_is_newest(self):
        nov = datetime(2026, 11, 2, tzinfo=UTC)
        self.run_main(['2026-10'], now=nov)
        self.run_main(['2026-09'], now=nov)
        latest = json.loads((self.site / 'latest.json').read_text())
        self.assertEqual(latest['month'], 'October 2026')
        self.assertLess((self.site / 'index.html').read_text().index('October'),
                        (self.site / 'index.html').read_text().index('September'))

    def test_year_explicit_past(self):
        self.run_main(['2026'], now=datetime(2027, 1, 5, tzinfo=UTC))
        sm = json.loads((self.site / '2026' / 'summary.json').read_text())
        self.assertEqual((sm['kind'], sm['so_far'], sm['plays']), ('year', False, 24))
        self.assertIn('href="2026/"', (self.site / 'index.html').read_text())

    def test_year_flag_in_december_is_jan_to_nov(self):
        make_db(str(self.dir / 'nd2.db'), [p(5, m=11), p(1, m=12)])
        self.env.write_text(f'ND_DB={self.dir / "nd2.db"}\n')
        self.run_main(['--year'], now=datetime(2026, 12, 1, 6, tzinfo=UTC))
        sm = json.loads((self.site / '2026' / 'summary.json').read_text())
        self.assertEqual((sm['so_far'], sm['plays']), (True, 1))

    def test_year_flag_in_january_is_full_previous_year(self):
        self.run_main(['--year'], now=datetime(2027, 1, 1, 6, tzinfo=UTC))
        sm = json.loads((self.site / '2026' / 'summary.json').read_text())
        self.assertEqual((sm['so_far'], sm['plays']), (False, 24))

    def test_latest_stays_monthly(self):
        nov = datetime(2026, 11, 2, tzinfo=UTC)
        self.run_main(['2026-10'], now=nov)
        self.run_main(['2026'], now=nov)
        self.assertEqual(json.loads((self.site / 'latest.json').read_text())['month'], 'October 2026')

    def test_bad_argument(self):
        self.assertEqual(self.run_main(['20266']), 2)
        self.assertEqual(self.run_main(['october']), 2)


if __name__ == '__main__':
    unittest.main()
