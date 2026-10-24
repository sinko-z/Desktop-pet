"""开机自启动：写入当前用户的注册表 Run 项，使用 pythonw 启动以避免黑框。"""

from __future__ import annotations

import sys

import winreg

from . import config

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DesktopPet"


def _command() -> str:
    python = sys.executable
    pythonw = python.replace("python.exe", "pythonw.exe")
    import os
    if os.path.exists(pythonw):
        python = pythonw
    return f'"{python}" "{config.APP_DIR / "main.py"}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        raise RuntimeError(f"无法写入注册表：{exc}") from exc
