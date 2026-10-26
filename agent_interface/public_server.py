"""Password-protected loopback gateway for the public HTTPS tunnel."""
import base64
import hmac
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

PASSWORD = os.environ['PHOTON_PUBLIC_PASSWORD']
if len(PASSWORD) < 24:
    raise RuntimeError('Public access requires a strong password')
EXPECTED = 'Basic ' + base64.b64encode(('researcher:' + PASSWORD).encode()).decode()

class Gateway(BaseHTTPRequestHandler):
    def forward(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), EXPECTED):
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Darknight Research", charset="UTF-8"')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if not self.path.startswith('/') or self.path.startswith('//'):
            self.send_error(400)
            return
        data = None
        if self.command == 'POST':
            origin = self.headers.get('Origin')
            if origin and origin != 'https://' + self.headers.get('Host', ''):
                self.send_error(403)
                return
            try: size = int(self.headers.get('Content-Length', '0'))
            except ValueError: size = 0
            if not 0 < size <= 20000:
                self.send_error(400)
                return
            data = self.rfile.read(size)
        # Only forward to the existing local service. Credentials never leave this gateway.
        request = Request('http://127.0.0.1:8765' + self.path, data=data,
                          headers={'Content-Type':'application/json'}, method=self.command)
        try:
            try: response = urlopen(request, timeout=30)
            except HTTPError as exc: response = exc
            with response:
                body = response.read()
                self.send_response(response.status)
                self.send_header('Content-Type', response.headers.get('Content-Type', 'application/octet-stream'))
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('X-Frame-Options', 'DENY')
                self.end_headers()
                self.wfile.write(body)
        except (OSError, TimeoutError):
            self.send_error(502, 'Dashboard unavailable')
    do_GET = forward
    do_POST = forward

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8766), Gateway).serve_forever()
