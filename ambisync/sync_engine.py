from __future__ import annotations

import threading
import time
from typing import Callable

from ambisync.color_processor import ColorSmoother
from ambisync.lamp_backends import create_backend
from ambisync.screen_capture import RgbColor, ScreenColorSampler
from ambisync.yandex_api import YandexApiError


class SyncEngine:
    def __init__(
        self,
        config: dict,
        on_status: Callable[[str], None] | None = None,
        on_color: Callable[[RgbColor], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.on_status = on_status
        self.on_color = on_color
        self.on_error = on_error

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._sampler: ScreenColorSampler | None = None
        self._backend = None
        self._smoother = ColorSmoother(
            smoothing=float(config.get("smoothing", 0.22)),
            lamp_min_change=int(config.get("min_color_change", 4)),
        )
        self._api_error_count = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._api_error_count = 0
        self._smoother.reset()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self._cleanup()
        self._emit_status("Остановлено")

    def _emit_status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _emit_error(self, message: str, *, fatal: bool = True) -> None:
        if self.on_error:
            self.on_error(message, fatal)

    def _cleanup(self) -> None:
        if self._sampler is not None:
            self._sampler.close()
            self._sampler = None
        if self._backend is not None:
            self._backend.close()
            self._backend = None

    def _run(self) -> None:
        fps = max(1, int(self.config.get("fps", 10)))
        interval = 1.0 / fps
        brightness = int(self.config.get("brightness", 70))

        try:
            self._sampler = ScreenColorSampler(
                monitor_index=int(self.config.get("monitor_index", 1)),
                downsample=int(self.config.get("downsample", 18)),
            )
            self._backend = create_backend(self.config)
            self._emit_status("Синхронизация запущена")
        except Exception as exc:
            self._emit_error(f"Ошибка инициализации: {exc}")
            self._cleanup()
            return

        while not self._stop_event.is_set():
            started = time.perf_counter()
            try:
                assert self._sampler is not None
                assert self._backend is not None

                sampled = self._sampler.sample_average()
                result = self._smoother.process(sampled)

                if self.on_color:
                    self.on_color(result.display)

                if result.send_to_lamp:
                    self._backend.set_color(result.display, brightness)
                    self._api_error_count = 0
            except YandexApiError as exc:
                self._api_error_count += 1
                message = str(exc)
                if self._api_error_count >= 8:
                    self._emit_error(message)
                    break
                self._emit_status(f"API: {message[:80]}… повтор")
                time.sleep(min(2.0 * self._api_error_count, 8.0))
            except Exception as exc:
                self._emit_error(f"Ошибка синхронизации: {exc}")
                time.sleep(1.0)

            elapsed = time.perf_counter() - started
            sleep_for = max(0.0, interval - elapsed)
            if self._stop_event.wait(sleep_for):
                break

        self._cleanup()
