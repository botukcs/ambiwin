from __future__ import annotations

from typing import Any

from ambisync.screen_capture import RgbColor
from ambisync.yandex_api import YandexDevice, YandexSmartHomeClient


class YandexLampBackend:
    def __init__(self, settings: dict[str, Any]) -> None:
        self._client = YandexSmartHomeClient(settings["oauth_token"])
        self._device = YandexDevice(
            id=settings["device_id"],
            name=settings.get("device_name", settings["device_id"]),
            room=settings.get("room", ""),
            color_mode=settings.get("color_mode", "hsv"),
            device_type=settings.get("device_type", "devices.types.light"),
        )
        self._primed = False

    def set_color(self, color: RgbColor, brightness: int) -> None:
        self._client.set_color(
            self._device,
            color,
            brightness,
            include_power_setup=not self._primed,
        )
        self._primed = True

    def turn_on(self) -> None:
        self._client.turn_on(self._device.id)

    def close(self) -> None:
        self._client.close()


def create_backend(config: dict[str, Any]) -> YandexLampBackend:
    return YandexLampBackend(config["yandex"])
