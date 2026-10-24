"""用 Windows 的“最后输入时间”判断用户是否在电脑前，累计连续使用时长。"""

from __future__ import annotations

import ctypes
import time


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    elapsed = (kernel32.GetTickCount64() - info.dwTime) / 1000.0
    return max(0.0, elapsed)


class ActivityTracker:
    def __init__(self):
        now = time.time()
        self._last_poll = now
        self._active_seconds = 0.0
        self._rest_ready_at = 0.0
        self._last_mood_at = now

    def tick(self, cfg: dict) -> list[str]:
        """每 5-10 秒调用一次，返回触发的事件：rest / mood。"""
        now = time.time()
        delta = min(now - self._last_poll, 60.0)
        self._last_poll = now
        events: list[str] = []

        idle_reset = float(cfg["idle_reset_min"]) * 60
        if idle_seconds() > idle_reset:
            # 长时间没动键鼠，视为离开电脑，连续使用时长清零
            self._active_seconds = 0.0
        else:
            self._active_seconds += max(0.0, delta)

        rest_seconds = float(cfg["rest_interval_min"]) * 60
        if cfg["remind_rest"] and self._active_seconds >= rest_seconds and now >= self._rest_ready_at:
            events.append("rest")
            # 保留连续使用时长：若用户继续忙，会在“延后”时间后再次提醒
            self._rest_ready_at = now + float(cfg["rest_snooze_min"]) * 60

        mood_seconds = float(cfg["mood_check_min"]) * 60
        if now - self._last_mood_at >= mood_seconds:
            events.append("mood")
            self._last_mood_at = now
        return events
