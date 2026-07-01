from __future__ import annotations

from typing import Any, Callable

from ambisync.config import load_config, save_config
from ambisync.screen_capture import RgbColor
from ambisync.sync_engine import SyncEngine


class AppController:
    """Управление синхронизацией и конфигурацией."""

    def __init__(self) -> None:
        self.config = load_config()
        self.engine: SyncEngine | None = None
        self._state_listeners: list[Callable[[bool], None]] = []

    @property
    def is_syncing(self) -> bool:
        return self.engine is not None and self.engine.running

    def add_state_listener(self, callback: Callable[[bool], None]) -> None:
        self._state_listeners.append(callback)

    def _notify_state(self, syncing: bool) -> None:
        for callback in self._state_listeners:
            callback(syncing)

    def validate_config(self, config: dict[str, Any]) -> str | None:
        yandex = config["yandex"]
        if not yandex.get("oauth_token"):
            return "Вставьте OAuth токен Яндекса"
        if not yandex.get("device_id"):
            return "Выберите лампу: нажмите «Загрузить» и выберите эмби-лампу из списка"
        return None

    def save_config(self, config: dict[str, Any]) -> None:
        self.config = config
        save_config(config)

    def start_sync(
        self,
        config: dict[str, Any],
        *,
        on_status: Callable[[str], None] | None = None,
        on_color: Callable[[RgbColor], None] | None = None,
        on_error: Callable[[str, bool], None] | None = None,
    ) -> str | None:
        error = self.validate_config(config)
        if error:
            return error

        self.save_config(config)
        if self.engine is not None:
            self.engine.stop()

        self.engine = SyncEngine(
            config,
            on_status=on_status,
            on_color=on_color,
            on_error=on_error,
        )
        self.engine.start()
        self._notify_state(True)
        return None

    def stop_sync(self) -> None:
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        self._notify_state(False)

    def shutdown(self) -> None:
        self.stop_sync()
