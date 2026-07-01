from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "monitor_index": 1,
    "fps": 10,
    "brightness": 70,
    "smoothing": 0.22,
    "min_color_change": 4,
    "downsample": 18,
    "ui": {
        "minimize_to_tray": True,
        "start_minimized": False,
    },
    "yandex": {
        "oauth_token": "",
        "device_id": "",
        "device_name": "",
        "room": "",
        "color_mode": "hsv",
    },
}

SMOOTH_PRESET: dict[str, int | float] = {
    "fps": 10,
    "brightness": 70,
    "smoothing": 0.22,
    "min_color_change": 4,
    "downsample": 18,
}


def config_path() -> Path:
    base = Path.home() / ".config" / "yandex-ambisync"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    merged = deepcopy(DEFAULT_CONFIG)
    for key, value in data.items():
        if key == "tuya":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
