"""浏览器辅助：把抢焦点的 Chrome 窗口最小化。"""
import sys
import time


def minimize_browser_windows(retries=10, interval=0.1):
    """在窗口创建后尽快最小化所有 Chrome 窗口（排除 DevTools）。"""
    try:
        import ctypes
        import ctypes.wintypes
        import psutil
        user32 = ctypes.windll.user32
        SW_MINIMIZE = 6
        for attempt in range(retries):
            found = []

            def _enum_cb(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    pid = ctypes.wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    try:
                        proc = psutil.Process(pid.value)
                        if 'chrome' in proc.name().lower():
                            length = user32.GetWindowTextLengthW(hwnd)
                            title = ''
                            if length > 0:
                                buf = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buf, length + 1)
                                title = buf.value.lower()
                            if 'devtools' not in title:
                                found.append(hwnd)
                    except Exception:
                        pass
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
            for hwnd in found:
                user32.ShowWindow(hwnd, SW_MINIMIZE)
            if attempt < retries - 1:
                time.sleep(interval)
    except Exception:
        pass
