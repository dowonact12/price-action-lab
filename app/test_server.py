import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
from server import Handler


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_home_and_scan(self):
        with urllib.request.urlopen(self.url) as response:
            self.assertIn(b'Price Action Lab', response.read())
        document = json.loads(Path(__file__).with_name('example-data.json').read_text(encoding='utf-8-sig'))
        request = urllib.request.Request(self.url + '/api/scan', data=json.dumps({'document': document}).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        self.assertEqual(len(result['results']), len(document['symbols']))
        self.assertTrue(all(row['status'] == 'ok' for row in result['results']))

    def test_bad_input_and_external_origin(self):
        for data, headers, expected in [(b'bad', {}, 400), (b'{}', {'Origin': 'https://external.example'}, 403)]:
            request = urllib.request.Request(self.url + '/api/scan', data=data, headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, expected)

    def test_no_arbitrary_file_access(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url + '/engine.py')
        self.assertEqual(caught.exception.code, 404)
