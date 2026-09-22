"""Loopback-only research screener. Run: python server.py"""
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from engine import evaluate_document
from updater import read_saved, serve_updates
import threading
import re
from updater import DATA

ROOT = Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, payload, content_type='application/json; charset=utf-8'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/':
            self.reply(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        elif self.path in ('/charts.js', '/dashboard.js', '/research.js', '/live.js'):
            self.reply(200, (ROOT / self.path[1:]).read_bytes(), 'text/javascript; charset=utf-8')
        elif self.path == '/style.css':
            self.reply(200, (ROOT / 'style.css').read_bytes(), 'text/css; charset=utf-8')
        elif re.fullmatch(r'/data/charts/[a-f0-9]{64}\.json\.gz', self.path):
            path = DATA / 'charts' / self.path.rsplit('/', 1)[-1]
            self.reply(200, path.read_bytes(), 'application/gzip') if path.exists() else self.reply(404, {'error':'Chart not available'})
        elif self.path in ('/api/latest', '/api/intraday', '/api/update-status', '/api/history'):
            name = {'/api/latest': 'latest.json', '/api/intraday': 'intraday.json', '/api/update-status': 'update-status.json', '/api/history': 'history.json'}[self.path]
            payload = read_saved(name)
            self.reply(200 if payload else 503, payload or {'error': '첫 데이터 수집 중입니다.'})
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/api/scan':
            return self.reply(404, {'error': 'Not found'})
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8768', 'http://localhost:8768'):
            return self.reply(403, {'error': 'Origin rejected'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 50_000_000:
                return self.reply(413, {'error': 'JSON 파일은 50 MB 이하로 입력하세요.'})
            request = json.loads(self.rfile.read(size))
            result = evaluate_document(request['document'], min_turnover=float(request.get('min_turnover', 10_000_000)), min_adr=float(request.get('min_adr', 3)))
            self.reply(200, result)
        except (ValueError, TypeError, KeyError) as error:
            self.reply(400, {'error': str(error)})

if __name__ == '__main__':
    import os
    if os.environ.get('PA_DISABLE_UPDATER') != '1':
        threading.Thread(target=serve_updates, daemon=True).start()
    print('US price-action screener: http://127.0.0.1:8768', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8768), Handler).serve_forever()
