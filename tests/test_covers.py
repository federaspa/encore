import os, sys, tempfile, unittest, urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import covers

CFG = {'ND_URL': 'http://nd:4533', 'ND_USER': 'u', 'ND_TOKEN': 't', 'ND_SALT': 's'}


class FakeResp:
    def __init__(self, ctype, body=b'\xff\xd8jpeg'):
        self.headers = {'Content-Type': ctype}
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class CoversTest(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        self.urls = []

    def opener(self, ctype='image/jpeg', exc=None):
        def fn(url, timeout=None):
            self.urls.append(url)
            if exc:
                raise exc
            return FakeResp(ctype)
        return fn

    def test_saves_jpeg(self):
        got = covers.fetch_covers(['al1'], self.out, CFG, opener=self.opener())
        self.assertEqual(got, {'al1': 'covers/al1.jpg'})
        self.assertTrue((self.out / 'covers' / 'al1.jpg').exists())
        self.assertIn('id=al1', self.urls[0])
        self.assertIn('size=300', self.urls[0])
        self.assertTrue(self.urls[0].startswith('http://nd:4533/rest/getCoverArt?'))

    def test_error_skipped(self):
        got = covers.fetch_covers(['al1'], self.out, CFG, opener=self.opener(exc=urllib.error.URLError('down')))
        self.assertEqual(got, {})
        self.assertFalse((self.out / 'covers' / 'al1.jpg').exists())

    def test_incomplete_read_skipped(self):
        import http.client
        got = covers.fetch_covers(['al1'], self.out, CFG, opener=self.opener(exc=http.client.IncompleteRead(b'')))
        self.assertEqual(got, {})

    def test_non_image_skipped(self):
        self.assertEqual(covers.fetch_covers(['al1'], self.out, CFG, opener=self.opener('text/xml')), {})

    def test_dedup(self):
        covers.fetch_covers(['al1', 'al1', None], self.out, CFG, opener=self.opener())
        self.assertEqual(len(self.urls), 1)

    def test_load_env_defaults(self):
        p = self.out / 'w.env'
        p.write_text('# comment\nND_USER=alice\n\nND_URL = http://x \n')
        cfg = covers.load_env(str(p))
        self.assertEqual(cfg['ND_USER'], 'alice')
        self.assertEqual(cfg['ND_URL'], 'http://x')
        self.assertEqual(cfg['TZ'], 'UTC')
        self.assertEqual(cfg['ND_DB'], '/var/lib/navidrome/navidrome.db')
