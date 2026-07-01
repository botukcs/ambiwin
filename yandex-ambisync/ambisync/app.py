from __future__ import annotations

import tkinter as tk

from ambisync.controller import AppController
from ambisync.tray import TrayManager
from ambisync.ui.main_window import MainWindow


class AmbiSyncApplication:
    def __init__(self) -> None:
        self.controller = AppController()
        self.root = tk.Tk()
        self.window = MainWindow(self.root, self.controller)
        self.tray = TrayManager(self)

        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.tray.start()

        if self.window.should_start_minimized():
            self.root.after(100, self.hide_window)

    def show_window(self) -> None:
        self.window.show_window()

    def hide_window(self) -> None:
        self.root.withdraw()
        self.tray.notify("Yandex AmbiSync", "Приложение работает в фоне")

    def on_window_close(self) -> None:
        if self.window.should_minimize_to_tray():
            self.hide_window()
            return
        self.quit()

    def quit(self) -> None:
        self.controller.shutdown()
        self.tray.stop()
        self.root.quit()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    AmbiSyncApplication().run()
