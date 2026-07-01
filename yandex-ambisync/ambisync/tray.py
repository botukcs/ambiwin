from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pystray
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from ambisync.app import AmbiSyncApplication

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _resource_path(name: str) -> Path:
    import sys

    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name


def create_icon_image(size: int = 64) -> Image.Image:
    icon_path = _resource_path("icon.png")
    if icon_path.exists():
        image = Image.open(icon_path).convert("RGBA")
        return image.resize((size, size), Image.Resampling.LANCZOS)

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = size // 8
    draw.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=(255, 204, 0, 255),
        outline=(220, 50, 30, 255),
        width=max(2, size // 16),
    )
    inner = size // 4
    draw.ellipse(
        (inner, inner, size - inner, size - inner),
        fill=(255, 120, 40, 200),
    )
    return image


class TrayManager:
    def __init__(self, app: AmbiSyncApplication) -> None:
        self._app = app
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._start_item: pystray.MenuItem | None = None
        self._stop_item: pystray.MenuItem | None = None

    def start(self) -> None:
        if self._thread is not None:
            return

        image = create_icon_image()
        self._start_item = pystray.MenuItem("Старт", self._on_start, enabled=lambda _: not self._app.controller.is_syncing)
        self._stop_item = pystray.MenuItem("Стоп", self._on_stop, enabled=lambda _: self._app.controller.is_syncing)

        menu = pystray.Menu(
            pystray.MenuItem("Открыть", self._on_show, default=True),
            self._start_item,
            self._stop_item,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._on_exit),
        )
        self._icon = pystray.Icon("yandex-ambisync", image, "Yandex AmbiSync", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

        self._app.controller.add_state_listener(lambda _: self._refresh_menu())

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        self._thread = None

    def notify(self, title: str, message: str) -> None:
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _refresh_menu(self) -> None:
        if self._icon is not None:
            self._icon.update_menu()

    def _run_on_ui(self, callback: Callable[[], None]) -> None:
        self._app.root.after(0, callback)

    def _on_show(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._run_on_ui(self._app.show_window)

    def _on_start(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._run_on_ui(self._app.window.start_from_tray)

    def _on_stop(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._run_on_ui(self._app.window.stop_sync)

    def _on_exit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._run_on_ui(self._app.quit)
