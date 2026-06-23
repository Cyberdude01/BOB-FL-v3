#!/usr/bin/env python3
"""
Phase 5 Dashboard Server (Minimal)
A tiny HTTP server exposing JSON endpoints for metrics.

Endpoints:
- /api/summary
- /api/executions
- /api/patterns
- /health

This is intentionally lightweight and dependency-free (stdlib only).
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse
import threading
from pathlib import Path

# Local in-memory cache (as a simple bridge to Phase5 store)
from phase5_data_store import MetricsStore

STORE = MetricsStore()


class Handler(BaseHTTPRequestHandler):
    def _send(self, data, code=200, content_type='application/json'):
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/health':
            self._send({'status': 'ok', 'timestamp': __import__('time').time()})
            return
        if parsed.path == '/api/summary':
            self._send(STORE.summary())
            return
        if parsed.path == '/api/executions':
            self._send({'recent_executions': STORE.recent_executions(50)})
            return
        if parsed.path == '/api/patterns':
            self._send({'recent_patterns': STORE.recent_patterns(50)})
            return
        self._send({'error': 'unknown_endpoint'}, code=404)


def run_server(host='0.0.0.0', port=8080):
    httpd = HTTPServer((host, port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print(f"Phase 5 Dashboard server running at http://{host}:{port}")
    return httpd, thread


if __name__ == '__main__':
    # Start server and keep process alive
    run_server()
    try:
        while True:
            __import__('time').sleep(1)
    except KeyboardInterrupt:
        print("Shutting down dashboard server...")
