"""Loopback-only local viewer, no external dependencies or network services."""
import argparse
import json
import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from geometry import geometry
import pstairs

ROOT = Path(__file__).resolve().parent
ASSETS = {'/': ('index.html','text/html; charset=utf-8'),
          '/room-layout.js': ('room-layout.js','text/javascript; charset=utf-8'),
          '/app.js': ('app.js','text/javascript; charset=utf-8'),
          '/style.css': ('style.css','text/css; charset=utf-8')}
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path == '/api/health':
                self.respond(200, b'{"app":"penrose-atrium","version":2}', 'application/json')
            elif url.path == '/api/catalog':
                selected = []
                for n in range(1, 201):
                    p = pstairs.PenroseStaircase(n)
                    if .5 <= p.c / p.d <= 2 and 8 <= p.a+p.b+p.c+p.d-3 <= 32:
                        selected.append(n)
                self.respond(200, json.dumps(selected).encode(), 'application/json')
            elif url.path == '/api/staircase':
                n = int(parse_qs(url.query).get('n',['25'])[0])
                self.respond(200, json.dumps(geometry(n), allow_nan=False).encode(), 'application/json')
            elif url.path in ASSETS:
                name, content_type = ASSETS[url.path]
                self.respond(200, (ROOT/name).read_bytes(), content_type)
            elif url.path == '/favicon.ico':
                self.respond(204, b'', 'image/x-icon')
            else:
                self.respond(404, b'Not found', 'text/plain')
        except (ValueError, OverflowError) as error:
            self.respond(400, json.dumps({'error': str(error)}).encode(), 'application/json')
        except Exception:
            logging.exception('Request failed')
            self.respond(500, b'{"error":"Unable to generate staircase"}', 'application/json')
    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
