"""Loopback-only interface for the local converter."""
import json
import pathlib
import secrets
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from converter import convert
from platform_tools import downloads_dir, open_folder, open_browser

MAX_FILE = 100 * 1024 * 1024

def make_server(destination=None):
    destination = pathlib.Path(destination or downloads_dir()).resolve()
    token = secrets.token_urlsafe(24)
    prefix = '/' + token + '/'
    page = pathlib.Path(__file__).with_name('index.html').read_bytes()
    lock = threading.Lock()


    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, data, mime='application/json'):
            if not isinstance(data, bytes):
                data = json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            expected = '127.0.0.1:' + str(self.server.server_port)
            return self.headers.get('Host') == expected and self.headers.get('Origin', 'http://' + expected) == 'http://' + expected

        def do_GET(self):
            if not self.allowed() or self.path != prefix:
                return self.reply(404, {'error': 'Page not found.'})
            self.reply(200, page, 'text/html; charset=utf-8')

        def do_POST(self):
            path = urlsplit(self.path)
            if not self.allowed() or not path.path.startswith(prefix):
                return self.reply(403, {'error': 'Request not allowed.'})
            endpoint = path.path[len(prefix):]
            if endpoint == 'open-downloads':
                destination.mkdir(parents=True, exist_ok=True)
                open_folder(destination)
                return self.reply(200, {'ok': True})
            if endpoint != 'convert':
                return self.reply(404, {'error': 'Page not found.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_FILE:
                    return self.reply(413, {'error': 'Please choose a file smaller than 100 MB.'})
                filename = parse_qs(path.query).get('name', [''])[0]
                if not filename or any(c in filename for c in '/\\:<>"|?*') or any(ord(c) < 32 for c in filename) or filename.endswith((' ', '.')):
                    raise ValueError('Invalid filename.')
                if pathlib.Path(filename).suffix.lower() not in ('.vsdx', '.vsd', '.sor', '.trc'):
                    raise ValueError('Please choose a .vsdx, .vsd, .sor, or EXFO .trc file.')
                self.connection.settimeout(180)
                content = self.rfile.read(length)
                if len(content) != length:
                    raise ValueError('The file transfer was interrupted. Please try again.')
                with tempfile.TemporaryDirectory(prefix='visio-upload-') as temp:
                    source = pathlib.Path(temp) / filename
                    source.write_bytes(content)
                    with lock:
                        result = convert(source, destination)
                self.reply(200, {'filename': result.name, 'folder': str(destination)})
            except Exception as error:
                self.reply(400, {'error': str(error)})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    return server, 'http://127.0.0.1:' + str(server.server_port) + prefix

def main(launch_browser=True):
    server, url = make_server()
    print('Team PDF Converter is running.', flush=True)
    print('Keep this window open while converting. Close it to stop.', flush=True)
    print('If the browser does not open, paste this address into Edge or Chrome:', flush=True)
    print(url, flush=True)
    print('PDFs save to: ' + str(downloads_dir()), flush=True)
    if launch_browser:
        open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
