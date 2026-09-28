"""On-demand OS media-key reader. No general key logging or startup service."""
from pathlib import Path
import ctypes
import json
import os
import platform
import subprocess
import threading


class PhoneButtons:
    def __init__(self, on_key, on_status):
        self.on_key = on_key
        self.on_status = on_status
        self.process = None
        self.thread_id = None
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        system = platform.system()
        if system not in ('Darwin', 'Windows'):
            raise ValueError('Phone media buttons support macOS and Windows. On-screen controls still work here.')
        self.running = True
        self.thread = threading.Thread(target=self._mac if system == 'Darwin' else self._windows,
                                       daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)

    def _mac(self):
        try:
            root = Path(__file__).resolve().parent.parent
            binary = root / 'native/MediaButtons'
            source = root / 'native/MediaButtons.swift'
            if not binary.exists():
                cache = Path(os.environ.get('RETRO_PHONE_CACHE', str(Path.home() / '.cache/retro-codex-phone')))
                cache.mkdir(parents=True, exist_ok=True)
                binary = cache / 'MediaButtons'
                if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
                    subprocess.run(['swiftc', '-O', str(source), '-o', str(binary)], check=True,
                                   capture_output=True, timeout=120)
            if not self.running:
                return
            self.process = subprocess.Popen([str(binary)], stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True)
            for line in self.process.stdout:
                if not self.running:
                    break
                event = json.loads(line)
                if event.get('key'):
                    self.on_key(event['key'])
                if event.get('status'):
                    self.on_status(event['status'])
            self.process.wait()
        except Exception as error:
            self.on_status(f'Buttons unavailable: {error}. Use the on-screen controls.')
        finally:
            self.running = False

    def _windows(self):
        from ctypes import wintypes
        user = ctypes.windll.user32
        kernel = ctypes.windll.kernel32
        pointer = ctypes.c_ssize_t
        CALLBACK = ctypes.WINFUNCTYPE(pointer, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class KeyInfo(ctypes.Structure):
            _fields_ = [('vkCode', wintypes.DWORD), ('scanCode', wintypes.DWORD),
                        ('flags', wintypes.DWORD), ('time', wintypes.DWORD),
                        ('dwExtraInfo', ctypes.c_size_t)]

        user.SetWindowsHookExW.argtypes = [ctypes.c_int, CALLBACK, wintypes.HINSTANCE, wintypes.DWORD]
        user.SetWindowsHookExW.restype = wintypes.HHOOK
        user.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user.CallNextHookEx.restype = pointer
        user.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user.UnhookWindowsHookEx.restype = wintypes.BOOL
        user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user.PostThreadMessageW.restype = wintypes.BOOL
        user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user.GetMessageW.restype = wintypes.BOOL
        user.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user.DispatchMessageW.restype = pointer
        kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype = wintypes.HMODULE
        kernel.GetCurrentThreadId.restype = wintypes.DWORD
        held = set()
        keys = {0xB3: 'play', 0xAF: 'up', 0xAE: 'down'}

        def callback(code, message, data):
            if code >= 0 and self.running:
                key = ctypes.cast(data, ctypes.POINTER(KeyInfo)).contents.vkCode
                if key in keys:
                    if message in (0x100, 0x104) and key not in held:
                        held.add(key)
                        self.on_key(keys[key])
                    elif message in (0x101, 0x105):
                        held.discard(key)
                    return 1
            return user.CallNextHookEx(None, code, message, data)

        cb = CALLBACK(callback)
        hook = None
        try:
            self.thread_id = kernel.GetCurrentThreadId()
            hook = user.SetWindowsHookExW(13, cb, kernel.GetModuleHandleW(None), 0)
            if not hook:
                raise OSError('Windows did not allow the media-key hook.')
            self.on_status('Listening for phone buttons. Test each button once.')
            msg = wintypes.MSG()
            while self.running and user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user.TranslateMessage(ctypes.byref(msg))
                user.DispatchMessageW(ctypes.byref(msg))
        except Exception as error:
            self.on_status(str(error))
        finally:
            if hook:
                user.UnhookWindowsHookEx(hook)
            self.thread_id = None
            self.running = False
