from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ambisync.color_processor import rgb_to_yandex_hsv, rgb_to_yandex_value
from ambisync.screen_capture import RgbColor

API_BASE = "https://api.iot.yandex.net/v1.0"


@dataclass(frozen=True)
class YandexDevice:
    id: str
    name: str
    room: str
    color_mode: str  # "rgb" or "hsv"
    device_type: str = "devices.types.light"

    @property
    def label(self) -> str:
        if self.room:
            return f"{self.name} ({self.room})"
        return self.name


class YandexApiError(Exception):
    pass


class YandexSmartHomeClient:
    def __init__(self, oauth_token: str) -> None:
        token = oauth_token.strip()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    def close(self) -> None:
        self._session.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._session.request(
            method,
            f"{API_BASE}{path}",
            timeout=10,
            **kwargs,
        )
        if not response.ok:
            raise YandexApiError(
                f"HTTP {response.status_code}: {response.text.strip() or response.reason}"
            )
        payload = response.json()
        if payload.get("status") not in (None, "ok"):
            message = payload.get("message") or payload.get("status")
            raise YandexApiError(f"API: {message}")
        if method.upper() == "POST" and path.endswith("/actions"):
            self._raise_action_errors(payload)
        return payload

    def _raise_action_errors(self, payload: dict[str, Any]) -> None:
        errors: list[str] = []
        for device in payload.get("devices", []):
            for capability in device.get("capabilities", []):
                action_result = capability.get("state", {}).get("action_result", {})
                if action_result.get("status") != "ERROR":
                    continue
                code = action_result.get("error_code", "UNKNOWN")
                message = action_result.get("error_message", "")
                errors.append(f"{code}: {message}".strip(": "))

        if errors:
            raise YandexApiError("; ".join(errors))

    def list_color_lamps(self) -> tuple[list[YandexDevice], int]:
        payload = self._request("GET", "/user/info")
        room_names = {
            str(room.get("id", "")): str(room.get("name", ""))
            for room in payload.get("rooms", [])
            if room.get("id")
        }

        raw_devices = payload.get("devices", [])
        devices: list[YandexDevice] = []
        seen: set[str] = set()

        for device in raw_devices:
            if not isinstance(device, dict):
                continue
            parsed = self._parse_device(device, room_names)
            if parsed is None or parsed.id in seen:
                continue
            seen.add(parsed.id)
            devices.append(parsed)

        devices.sort(key=lambda item: item.label.casefold())
        return devices, len(raw_devices)

    def _parse_device(
        self,
        device: dict[str, Any],
        room_names: dict[str, str],
    ) -> YandexDevice | None:
        device_id = str(device.get("id", "")).strip()
        if not device_id:
            return None

        device_type = str(device.get("type", ""))
        color_mode = self._detect_color_mode(device)
        is_light = "light" in device_type

        if color_mode is None and not is_light:
            return None
        if color_mode is None:
            color_mode = "hsv"

        room_id = str(device.get("room", ""))
        room_name = room_names.get(room_id, "")
        aliases = device.get("aliases") or []
        name = str(device.get("name") or (aliases[0] if aliases else device_id))

        return YandexDevice(
            id=device_id,
            name=name,
            room=room_name,
            color_mode=color_mode,
            device_type=device_type,
        )

    def _detect_color_mode(self, device: dict[str, Any]) -> str | None:
        for capability in device.get("capabilities", []):
            if capability.get("type") != "devices.capabilities.color_setting":
                continue

            parameters = capability.get("parameters", {})
            color_model = parameters.get("color_model")
            if color_model in {"rgb", "hsv"}:
                return str(color_model)

            for instance in parameters.get("instances", []):
                instance_name = instance.get("name")
                if instance_name in {"rgb", "hsv"}:
                    return str(instance_name)

            state = capability.get("state", {})
            instance = state.get("instance")
            if instance in {"rgb", "hsv"}:
                return str(instance)

            return "hsv"

        return None

    def set_color(
        self,
        device: YandexDevice,
        color: RgbColor,
        brightness: int,
        *,
        include_power_setup: bool = True,
    ) -> None:
        brightness_value = max(1, min(100, int(brightness)))
        actions: list[dict[str, Any]] = []

        if include_power_setup:
            actions.append(
                {
                    "type": "devices.capabilities.on_off",
                    "state": {"instance": "on", "value": True},
                }
            )
            actions.append(
                {
                    "type": "devices.capabilities.range",
                    "state": {"instance": "brightness", "value": brightness_value},
                }
            )

        if device.color_mode == "hsv":
            actions.append(
                {
                    "type": "devices.capabilities.color_setting",
                    "state": {
                        "instance": "hsv",
                        "value": rgb_to_yandex_hsv(color, brightness_value),
                    },
                }
            )
        else:
            actions.append(
                {
                    "type": "devices.capabilities.color_setting",
                    "state": {
                        "instance": "rgb",
                        "value": rgb_to_yandex_value(color),
                    },
                }
            )

        self._request(
            "POST",
            "/devices/actions",
            json={"devices": [{"id": device.id, "actions": actions}]},
        )

    def turn_on(self, device_id: str) -> None:
        self._request(
            "POST",
            "/devices/actions",
            json={
                "devices": [
                    {
                        "id": device_id,
                        "actions": [
                            {
                                "type": "devices.capabilities.on_off",
                                "state": {"instance": "on", "value": True},
                            }
                        ],
                    }
                ]
            },
        )
