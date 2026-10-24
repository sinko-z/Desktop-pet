"""全局路径与配置读写。所有数据都保存在程序目录，方便整个文件夹拷走。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
PETS_DIR = DATA_DIR / "pets"
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "autostart": False,
    "always_on_top": True,
    "wander": True,
    "pet_height": 160,
    "pet_pos": None,
    "user_name": "你",
    "onboarded": False,
    "remind_rest": True,
    "rest_interval_min": 50,
    "rest_snooze_min": 15,
    "idle_reset_min": 5,
    "mood_check_min": 120,
    "llm": {"enabled": False, "base_url": "", "api_key": "", "model": ""},
}


def ensure_dirs() -> None:
    PETS_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    """先写临时文件再替换，避免异常退出留下半截 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load_config() -> dict:
    raw = read_json(CONFIG_PATH, {})
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({key: value for key, value in raw.items() if key in DEFAULT_CONFIG})
    cfg["llm"] = {**DEFAULT_CONFIG["llm"], **raw.get("llm", {})}
    return cfg


def save_config(cfg: dict) -> None:
    write_json(CONFIG_PATH, cfg)
