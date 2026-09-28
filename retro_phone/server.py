"""An on-demand loopback console; audio and prompts are not persisted."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import argparse
import json
import os
import queue
import secrets
import shutil
import tempfile
import threading
import time
import webbrowser

from .buttons import PhoneButtons
from .core import AgentRunner, ButtonGesture, Job, Transcriber, redact_home

MAX_AUDIO = 12 * 1024 * 1024


class Console:
    def __init__(self, model, cache=None, offline=False, double_tap=.42):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.state = dict(status='Ready', busy=False, transcript='', reply='', error='',
                          voice_ready=False, buttons_status='Off', test_buttons=True,
                          observed_keys=[], agents={a: bool(shutil.which(a)) for a in ('codex', 'claude')})
        self.events = queue.Queue()
        self.gesture = ButtonGesture(double_tap)
        self.transcriber = Transcriber(model, cache, offline)
        self.runner = AgentRunner()
        self.buttons = PhoneButtons(self.on_key, self.on_buttons_status)
        self.browser_seen = 0.
        self.task = None

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def snapshot(self):
        with self.lock:
            return dict(self.state, buttons_on=self.buttons.running)

    def on_buttons_status(self, text):
        self.update(buttons_status=redact_home(text))

    def on_key(self, key):
        with self.lock:
            seen = list(self.state['observed_keys'])
            if key not in seen:
                seen.append(key)
            self.state['observed_keys'] = seen
            if self.state['test_buttons']:
                return
            # A closed/suspended console must not run a command or keep consuming media keys.
            if not self.browser_seen or time.monotonic() - self.browser_seen > 4:
                return
            action = self.gesture.press(key)
            if action:
                self.events.put(action)

    def launch(self, title, work):
        with self.lock:
            if self.state['busy']:
                raise ValueError('Finish the current operation first.')
            self.state.update(busy=True, status=title, error='')
        def run():
            try:
                work()
            except Exception as error:
                self.update(error=redact_home(error), status='Needs attention')
            finally:
                self.update(busy=False)
        self.task = threading.Thread(target=run, daemon=True)
        self.task.start()

    def close(self):
        self.buttons.stop()
        self.runner.cancel()


def handler(console, root):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',
                                               f'localhost:{self.server.server_port}')

        def send(self, value, code=200):
            data = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.valid_host():
                return self.send({'error': 'Invalid host'}, 403)
            path = urlparse(self.path).path
            if path.startswith('/api/'):
                if not secrets.compare_digest(self.headers.get('X-Retro-Token', ''), console.token):
                    return self.send({'error': 'Open the local console first.'}, 403)
                if path == '/api/status':
                    console.browser_seen = time.monotonic()
                    if console.events.empty():
                        actions = []
                    else:
                        actions = []
                        while not console.events.empty():
                            actions.append(console.events.get_nowait())
                    return self.send(dict(console.snapshot(), actions=actions))
                return self.send({'error': 'Not found'}, 404)
            files = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
                     '/app.js': ('app.js', 'text/javascript')}
            if path not in files:
                return self.send({'error': 'Not found'}, 404)
            name, mime = files[path]
            data = (root / name).read_bytes()
            if path == '/':
                data = data.replace(b'RETRO_TOKEN_PLACEHOLDER', console.token.encode())
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; media-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            origin = self.headers.get('Origin')
            allowed = [f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}']
            if not self.valid_host() or (origin and origin not in allowed) or not secrets.compare_digest(self.headers.get('X-Retro-Token', ''), console.token):
                return self.send({'error': 'This action must come from the local console.'}, 403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                path = urlparse(self.path).path
                limit = MAX_AUDIO if path == '/api/audio' else 64000
                if not 0 < size <= limit:
                    return self.send({'error': 'Payload size is invalid. Keep audio below two minutes.'}, 413)
                body = self.rfile.read(size)
                if path == '/api/audio':
                    if not body.startswith(b'RIFF') or body[8:12] != b'WAVE':
                        raise ValueError('Import a WAV recording or use the record button.')
                    # A uniquely named temporary recording is removed after transcription.
                    def transcribe():
                        with tempfile.TemporaryDirectory(prefix='retro-phone-') as folder:
                            audio = Path(folder) / 'recording.wav'; audio.write_bytes(body)
                            text = console.transcriber.transcribe(audio)
                            if not text:
                                raise ValueError('No speech detected. Check the selected microphone and try again.')
                            console.update(transcript=text, voice_ready=True, status='Prompt ready')
                    console.launch('Transcribing', transcribe)
                else:
                    values = json.loads(body)
                    if path == '/api/prepare':
                        def prepare():
                            console.transcriber.prepare()
                            console.update(voice_ready=True, status='Voice ready')
                        console.launch('Preparing voice', prepare)
                    elif path == '/api/send':
                        job = Job(values['agent'], values['workspace'], values['prompt'], bool(values.get('allow_edits')))
                        agent_command_check(job)
                        def dispatch():
                            console.update(reply=console.runner.run(job), status='Reply ready')
                        console.launch(f'{job.agent.title()} is working', dispatch)
                    elif path == '/api/clear':
                        if console.snapshot()['busy']:
                            raise ValueError('Stop the current operation before clearing.')
                        console.update(transcript='', reply='', error='', status='Ready')
                    elif path == '/api/cancel':
                        console.runner.cancel()
                    elif path == '/api/buttons':
                        if values.get('enabled'):
                            console.update(test_buttons=bool(values.get('test', True)))
                            console.browser_seen = time.monotonic()
                            console.buttons.start()
                        else:
                            console.buttons.stop(); console.update(buttons_status='Off')
                        console.gesture.last_tap = None
                    elif path == '/api/button-mode':
                        console.update(test_buttons=bool(values.get('test', True)))
                        console.gesture.last_tap = None
                    else:
                        return self.send({'error': 'Not found'}, 404)
                self.send({'ok': True})
            except (ValueError, KeyError, TypeError) as error:
                self.send({'error': redact_home(error)}, 400)
    return Handler


def agent_command_check(job):
    from .core import agent_command
    agent_command(job)


def main():
    parser = argparse.ArgumentParser(description='Retro Codex Phone: local voice console for Codex and Claude.')
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--model', default='base', help='Whisper model name or a downloaded model directory')
    parser.add_argument('--cache', default=str(Path.home() / '.cache/retro-codex-phone/models'))
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--double-tap-ms', type=int, default=420,
                        help='Adjust the double-tap timing for your handset (100-1000 ms)')
    args = parser.parse_args()
    if not 100 <= args.double_tap_ms <= 1000:
        parser.error('--double-tap-ms must be between 100 and 1000')
    console = Console(args.model, args.cache, args.offline, args.double_tap_ms / 1000)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(console, Path(__file__).parent / 'web'))
    print(f'Retro Codex Phone: http://127.0.0.1:{server.server_port}', flush=True)
    def watchdog():
        while True:
            time.sleep(2)
            if console.buttons.running and console.browser_seen and time.monotonic() - console.browser_seen > 8:
                console.buttons.stop(); console.update(buttons_status='Stopped because the console is closed or inactive.')
    threading.Thread(target=watchdog, daemon=True).start()
    if not args.no_browser:
        webbrowser.open(f'http://127.0.0.1:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        console.close(); server.server_close()
