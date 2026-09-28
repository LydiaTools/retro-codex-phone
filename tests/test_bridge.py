import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from retro_phone.core import AgentRunner, ButtonGesture, Job, agent_command
from retro_phone.server import Console, handler


class Gestures(unittest.TestCase):
    def test_double_tap_and_expiry(self):
        g = ButtonGesture()
        self.assertIsNone(g.press('play', 1))
        self.assertEqual(g.press('play', 1.3), 'record')
        self.assertIsNone(g.press('play', 2))
        self.assertIsNone(g.press('play', 3))
        self.assertEqual(g.press('play', 3.2), 'record')

    def test_send_backspace_and_unknown_keys(self):
        g = ButtonGesture()
        self.assertEqual(g.press('up'), 'send')
        self.assertEqual(g.press('down'), 'clear')
        self.assertIsNone(g.press('mute'))


class Routing(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def test_codex_and_claude_default_to_review(self):
        a, cwd = agent_command(Job('codex', self.folder.name, 'hello'), lambda _: 'codex')
        self.assertEqual(a[-1], '-')
        self.assertIn('read-only', a)
        self.assertEqual(cwd, str(Path(self.folder.name).resolve()))
        a, _ = agent_command(Job('claude', self.folder.name, 'hello'), lambda _: 'claude')
        self.assertIn('plan', a)
        self.assertNotIn('--dangerously-skip-permissions', a)

    def test_editing_requires_explicit_job_flag(self):
        a, _ = agent_command(Job('codex', self.folder.name, 'hello', True), lambda _: 'codex')
        self.assertIn('workspace-write', a)
        a, _ = agent_command(Job('claude', self.folder.name, 'hello', True), lambda _: 'claude')
        self.assertIn('acceptEdits', a)

    def test_missing_binary_bad_folder_and_empty_prompt(self):
        for job, resolver in [(Job('other', self.folder.name, 'hi'), lambda _: 'x'),
                              (Job('codex', self.folder.name, ''), lambda _: 'x'),
                              (Job('codex', '', 'hi'), lambda _: 'x'),
                              (Job('codex', '/no-such-retro-project', 'hi'), lambda _: 'x'),
                              (Job('codex', self.folder.name, 'hi'), lambda _: None)]:
            with self.assertRaises(ValueError):
                agent_command(job, resolver)

    def test_real_subprocess_receives_prompt_as_data(self):
        # Execute a process that only echoes stdin. Shell syntax must stay inert.
        prompt = "--dangerous ; $(touch must-not-exist)\nbackticks `exit`"
        command = [sys.executable, '-c', 'import sys; print(sys.stdin.read())']
        with patch('retro_phone.core.agent_command', return_value=(command, self.folder.name)):
            result = AgentRunner().run(Job('codex', self.folder.name, prompt))
        self.assertEqual(result, prompt)
        self.assertFalse((Path(self.folder.name) / 'must-not-exist').exists())

    def test_timeout_releases_the_runner(self):
        command = [sys.executable, '-c', 'import time; time.sleep(2)']
        runner = AgentRunner()
        with patch('retro_phone.core.agent_command', return_value=(command, self.folder.name)):
            with self.assertRaises(ValueError):
                runner.run(Job('codex', self.folder.name, 'x'), timeout=.1)
        self.assertIsNone(runner.process)


class LocalConsole(unittest.TestCase):
    def setUp(self):
        self.console = Console('tiny')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.console, Path('retro_phone/web')))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, token=True, origin=None, host=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {}
        if token:
            headers['X-Retro-Token'] = self.console.token
        if origin:
            headers['Origin'] = origin
        if host:
            headers['Host'] = host
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read(); status = response.status; connection.close()
        return status, data

    def test_unauthorized_api_and_other_origins_rejected(self):
        self.assertEqual(self.request('GET', '/api/status', token=False)[0], 403)
        self.assertEqual(self.request('POST', '/api/clear', '{}', origin='https://attacker.example')[0], 403)
        self.assertEqual(self.request('GET', '/', host='attacker.example')[0], 403)

    def test_no_path_traversal_and_audio_must_be_wav(self):
        self.assertEqual(self.request('GET', '/../../LICENSE')[0], 404)
        self.assertEqual(self.request('POST', '/api/audio', b'not audio')[0], 400)

    def test_button_diagnostics_never_send(self):
        self.console.on_key('up')
        self.assertTrue(self.console.events.empty())
        self.assertEqual(self.console.snapshot()['observed_keys'], ['up'])
        self.console.update(test_buttons=False)
        self.console.on_key('up')
        self.assertTrue(self.console.events.empty())
        self.console.browser_seen = time.monotonic()
        self.console.on_key('up')
        self.assertEqual(self.console.events.get_nowait(), 'send')

    def test_transcription_error_releases_busy_flag(self):
        self.console.launch('Test', lambda: (_ for _ in ()).throw(ValueError('Wrong microphone')))
        self.console.task.join(timeout=2)
        state = self.console.snapshot()
        self.assertFalse(state['busy'])
        self.assertIn('Wrong microphone', state['error'])


if __name__ == '__main__':
    unittest.main()
