"""Desktop Pet 启动入口。双击 run.bat 或执行 python main.py 即可。"""

from __future__ import annotations

import ctypes
import logging
import sys
import tkinter as tk
from tkinter import messagebox

from app import config


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _acquire_single_instance() -> bool:
    """命名互斥体保证只运行一个桌宠，句柄保存在模块级防止被回收。"""
    global _MUTEX
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _MUTEX = kernel32.CreateMutexW(None, False, "DesktopPet_SingleInstance")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def _setup_logging() -> None:
    config.ensure_dirs()
    logging.basicConfig(
        filename=str(config.DATA_DIR / "app.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        encoding="utf-8",
    )


def main() -> None:
    _enable_dpi_awareness()
    _setup_logging()
    if not _acquire_single_instance():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Desktop Pet", "桌宠已经在运行啦，看看屏幕右下角。")
        return
    try:
        from app.application import Application
        Application().run()
    except Exception:  # noqa: BLE001 - 启动失败时给用户明确提示并留日志
        logging.exception("启动失败")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Desktop Pet", "程序启动失败，详情见 data/app.log。")
    finally:
        logging.shutdown()


if __name__ == "__main__":
    sys.exit(main())
