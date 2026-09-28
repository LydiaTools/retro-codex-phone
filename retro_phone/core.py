"""Audio transcription and explicit, shell-free agent dispatch."""
from dataclasses import dataclass
from pathlib import Path
import os
import signal
import shutil
import subprocess
import threading
import time


class ButtonGesture:
    """A double media-key tap toggles recording; held-key repeats are ignored."""
    def __init__(self, interval=.42):
        self.interval = interval
        self.last_tap = None

    def press(self, key, now=None):
        now = time.monotonic() if now is None else now
        if key == 'play':
            if self.last_tap is not None and 0 <= now - self.last_tap <= self.interval:
                self.last_tap = None
                return 'record'
            self.last_tap = now
            return None
        self.last_tap = None
        return {'up': 'send', 'down': 'clear'}.get(key)


@dataclass(frozen=True)
class Job:
    agent: str
    workspace: str
    prompt: str
    allow_edits: bool = False


def agent_command(job, resolver=shutil.which):
    if job.agent not in ('codex', 'claude'):
        raise ValueError('Choose Codex or Claude.')
    if not job.prompt.strip():
        raise ValueError('Record or type a prompt before sending.')
    if len(job.prompt) > 30000:
        raise ValueError('Keep the prompt below 30,000 characters.')
    if not job.workspace.strip():
        raise ValueError('Choose an existing project folder before sending.')
    workspace = Path(job.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError('Choose an existing project folder.')
    binary = resolver(job.agent)
    if not binary:
        raise ValueError(f'Install and sign in to {job.agent} CLI first. See the setup guide.')
    if job.agent == 'codex':
        args = [binary, 'exec', '--color', 'never', '--sandbox',
                'workspace-write' if job.allow_edits else 'read-only',
                '--skip-git-repo-check', '-']
    else:
        args = [binary, '-p', '--output-format', 'text', '--permission-mode',
                'acceptEdits' if job.allow_edits else 'plan']
    return args, str(workspace)


class AgentRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.process = None

    def run(self, job, timeout=240):
        args, cwd = agent_command(job)
        with self.lock:
            if self.process is not None:
                raise ValueError('An agent is already working.')
            # Text is stdin data, never a shell command or a command-line option.
            self.process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, shell=False,
                                            start_new_session=(os.name != 'nt'))
            process = self.process
        try:
            out, err = process.communicate(job.prompt, timeout=timeout)
            if process.returncode:
                raise ValueError((err or out or 'The agent stopped without a reply.')[-6000:])
            return out.strip() or 'Completed without a text reply.'
        except subprocess.TimeoutExpired:
            self.stop_process(process, force=True)
            process.communicate()
            raise ValueError('Timed out. No retry was sent; check the selected agent before resending.')
        finally:
            with self.lock:
                self.process = None

    def cancel(self):
        with self.lock:
            if self.process is not None:
                self.stop_process(self.process)

    @staticmethod
    def stop_process(process, force=False):
        if process.poll() is not None:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass


class Transcriber:
    def __init__(self, model='base', cache=None, offline=False):
        self.name = model
        self.cache = cache
        self.offline = offline
        self.model = None
        self.lock = threading.Lock()

    def prepare(self):
        with self.lock:
            if self.model is None:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(self.name, device='cpu', compute_type='int8',
                                          cpu_threads=2, num_workers=1,
                                          download_root=self.cache,
                                          local_files_only=self.offline)

    def transcribe(self, path):
        self.prepare()
        with self.lock:
            segments, _ = self.model.transcribe(str(path), beam_size=3, vad_filter=True)
            return ' '.join(s.text.strip() for s in segments).strip()


def redact_home(text):
    """Keep local diagnostic errors from disclosing a full home directory."""
    return str(text).replace(str(Path.home()), '~')
