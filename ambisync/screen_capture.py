from __future__ import annotations

from dataclasses import dataclass

import mss
import numpy as np


@dataclass(frozen=True)
class RgbColor:
    r: int
    g: int
    b: int

    def distance_to(self, other: RgbColor) -> float:
        return float(
            abs(self.r - other.r) + abs(self.g - other.g) + abs(self.b - other.b)
        )


class ScreenColorSampler:
    def __init__(self, monitor_index: int = 1, downsample: int = 12) -> None:
        self.monitor_index = monitor_index
        self.downsample = max(1, downsample)
        self._sct = mss.mss()

    def list_monitors(self) -> list[dict[str, int | str]]:
        monitors: list[dict[str, int | str]] = []
        for index, monitor in enumerate(self._sct.monitors):
            if index == 0:
                continue
            monitors.append(
                {
                    "index": index,
                    "label": (
                        f"Монитор {index}: "
                        f"{monitor['width']}x{monitor['height']}"
                    ),
                    "width": monitor["width"],
                    "height": monitor["height"],
                }
            )
        return monitors

    def sample_average(self) -> RgbColor:
        monitor = self._sct.monitors[self.monitor_index]
        frame = np.array(self._sct.grab(monitor), dtype=np.uint8)

        step = self.downsample
        sampled = frame[::step, ::step, :3]
        # mss returns BGRA; take BGR channels then convert to RGB mean.
        means = sampled.mean(axis=(0, 1))
        blue, green, red = means
        return RgbColor(
            r=int(red),
            g=int(green),
            b=int(blue),
        )

    def close(self) -> None:
        self._sct.close()
