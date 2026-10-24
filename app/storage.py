"""宠物档案与养成状态（饥饿度、心情、亲密度、聊天记录）的持久化。"""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from . import config

PETS_PATH = config.DATA_DIR / "pets.json"
STATE_PATH = config.DATA_DIR / "state.json"

HUNGER_PER_MIN = 0.2   # 约 8 小时从吃饱到饿扁
MOOD_PER_MIN = 0.06

BASE_STATS = {
    "hunger": 100.0,
    "mood": 80.0,
    "affection": 0.0,
    "feeds": 0,
    "pets": 0,
    "last_seen": 0.0,
    "history": [],
}


def pet_image_path(pet: dict) -> Path:
    return config.APP_DIR / pet["image"]


def pet_thumb_path(pet: dict) -> Path:
    return config.APP_DIR / pet["thumb"]


class Store:
    def __init__(self):
        config.ensure_dirs()
        self.pets: list[dict] = config.read_json(PETS_PATH, [])
        state = config.read_json(STATE_PATH, {})
        self.active_pet_id: str | None = state.get("active_pet_id")
        self.stats: dict[str, dict] = state.get("stats", {})

    # ---------- 持久化 ----------
    def save_pets(self) -> None:
        config.write_json(PETS_PATH, self.pets)

    def save_state(self) -> None:
        config.write_json(
            STATE_PATH,
            {"active_pet_id": self.active_pet_id, "stats": self.stats},
        )

    # ---------- 宠物档案 ----------
    def active_pet(self) -> dict | None:
        pet = next((p for p in self.pets if p["id"] == self.active_pet_id), None)
        if pet is None and self.pets:
            pet = self.pets[0]
            self.active_pet_id = pet["id"]
        return pet

    def set_active(self, pid: str) -> None:
        if any(p["id"] == pid for p in self.pets):
            self.active_pet_id = pid
            self.save_state()

    def create_pet(self, name: str, image, mode: str = "cutout", source: str = "") -> dict:
        pid = uuid.uuid4().hex[:12]
        folder = config.PETS_DIR / pid
        folder.mkdir(parents=True, exist_ok=True)
        image.save(folder / "pet.png")
        thumb = image.copy()
        thumb.thumbnail((120, 120))
        thumb.save(folder / "thumb.png")
        pet = {
            "id": pid,
            "name": name,
            "mode": mode,
            "source": source,
            "created_at": time.time(),
            "image": (folder / "pet.png").relative_to(config.APP_DIR).as_posix(),
            "thumb": (folder / "thumb.png").relative_to(config.APP_DIR).as_posix(),
        }
        self.pets.insert(0, pet)
        self.active_pet_id = pid
        self.stats[pid] = {**BASE_STATS, "history": [], "last_seen": time.time()}
        self.save_pets()
        self.save_state()
        return pet

    def rename_pet(self, pid: str, name: str) -> None:
        for pet in self.pets:
            if pet["id"] == pid:
                pet["name"] = name
        self.save_pets()

    def delete_pet(self, pid: str) -> None:
        if len(self.pets) <= 1:
            return
        shutil.rmtree(config.PETS_DIR / pid, ignore_errors=True)
        self.pets = [p for p in self.pets if p["id"] != pid]
        self.stats.pop(pid, None)
        if self.active_pet_id == pid:
            self.active_pet_id = self.pets[0]["id"] if self.pets else None
        self.save_pets()
        self.save_state()

    # ---------- 养成数值 ----------
    def _ensure(self, pid: str) -> dict:
        stats = self.stats.get(pid)
        if stats is None:
            stats = {**BASE_STATS, "history": [], "last_seen": time.time()}
            self.stats[pid] = stats
        return stats

    def decay(self, pid: str) -> dict:
        """按离开时长扣减饥饿度与心情，每次调用都会刷新 last_seen。"""
        stats = self._ensure(pid)
        now = time.time()
        minutes = max(0.0, (now - stats.get("last_seen", now)) / 60.0)
        if minutes > 0.5:
            stats["hunger"] = max(8.0, stats["hunger"] - minutes * HUNGER_PER_MIN)
            stats["mood"] = max(10.0, stats["mood"] - minutes * MOOD_PER_MIN)
        stats["last_seen"] = now
        return stats

    def stats_for(self, pid: str) -> dict:
        return dict(self.decay(pid))

    def feed(self, pid: str, amount: float, mood: float) -> dict:
        stats = self.decay(pid)
        stats["hunger"] = min(100.0, stats["hunger"] + amount)
        stats["mood"] = min(100.0, stats["mood"] + mood)
        stats["feeds"] += 1
        stats["affection"] += 1
        return dict(stats)

    def stroke(self, pid: str) -> dict:
        stats = self.decay(pid)
        stats["mood"] = min(100.0, stats["mood"] + 2)
        stats["affection"] += 1
        stats["pets"] += 1
        return dict(stats)

    def add_chat(self, pid: str, role: str, text: str) -> None:
        stats = self._ensure(pid)
        stats["history"].append({"role": role, "text": text, "ts": time.time()})
        stats["history"] = stats["history"][-80:]
        stats["affection"] += 0.5
        stats["mood"] = min(100.0, stats["mood"] + 0.5)
        stats["last_seen"] = time.time()

    def history(self, pid: str) -> list[dict]:
        return list(self._ensure(pid).get("history", []))
