from __future__ import annotations

import colorsys
from dataclasses import dataclass

from ambisync.screen_capture import RgbColor


@dataclass(frozen=True)
class SmoothingResult:
    display: RgbColor
    send_to_lamp: bool


class ColorSmoother:
    """Плавно догоняет цель каждый кадр; на лампу шлёт только заметные изменения."""

    def __init__(
        self,
        smoothing: float = 0.22,
        lamp_min_change: int = 4,
    ) -> None:
        self.alpha = max(0.05, min(0.95, smoothing))
        self.lamp_min_change = max(1, lamp_min_change)
        self._target: RgbColor | None = None
        self._display: RgbColor | None = None
        self._last_sent_hsv: tuple[int, int, int] | None = None

    def process(self, sampled: RgbColor) -> SmoothingResult:
        if self._display is None:
            self._display = sampled
            self._target = sampled
            self._last_sent_hsv = _rgb_to_hsv_tuple(sampled)
            return SmoothingResult(sampled, True)

        self._target = sampled
        current = self._display
        target = self._target
        alpha = self.alpha

        self._display = RgbColor(
            r=_lerp_channel(current.r, target.r, alpha),
            g=_lerp_channel(current.g, target.g, alpha),
            b=_lerp_channel(current.b, target.b, alpha),
        )

        display_hsv = _rgb_to_hsv_tuple(self._display)
        send_to_lamp = (
            self._last_sent_hsv is None
            or _hsv_distance(display_hsv, self._last_sent_hsv) >= self.lamp_min_change
        )
        if send_to_lamp:
            self._last_sent_hsv = display_hsv

        return SmoothingResult(self._display, send_to_lamp)

    def reset(self) -> None:
        self._target = None
        self._display = None
        self._last_sent_hsv = None


def _lerp_channel(current: int, target: int, alpha: float) -> int:
    return int(round(current + (target - current) * alpha))


def _rgb_to_hsv_tuple(color: RgbColor) -> tuple[int, int, int]:
    hue, saturation, value = colorsys.rgb_to_hsv(
        color.r / 255.0,
        color.g / 255.0,
        color.b / 255.0,
    )
    return (
        int(hue * 360) % 360,
        int(round(max(0.0, min(1.0, saturation)) * 100)),
        int(round(max(0.0, min(1.0, value)) * 100)),
    )


def _hsv_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    hue_delta = abs(left[0] - right[0])
    hue_delta = min(hue_delta, 360 - hue_delta)
    sat_delta = abs(left[1] - right[1])
    val_delta = abs(left[2] - right[2])
    return hue_delta + sat_delta * 0.5 + val_delta * 0.3


def rgb_to_yandex_value(color: RgbColor) -> int:
    return (color.r << 16) | (color.g << 8) | color.b


def rgb_to_yandex_hsv(color: RgbColor, brightness: int) -> dict[str, int]:
    hue, saturation, _value = _rgb_to_hsv_tuple(color)
    brightness_value = max(1, min(100, int(brightness)))
    return {
        "h": hue,
        "s": saturation,
        "v": brightness_value,
    }
