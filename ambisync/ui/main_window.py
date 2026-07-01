from __future__ import annotations

import threading
import webbrowser
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import messagebox, ttk

from ambisync.config import SMOOTH_PRESET, config_path
from ambisync.screen_capture import ScreenColorSampler
from ambisync.ui.widgets import add_labeled_entry, add_labeled_scale, paste_into_entry
from ambisync.yandex_api import YandexApiError, YandexSmartHomeClient

if TYPE_CHECKING:
    from ambisync.controller import AppController


class MainWindow:
    def __init__(self, root: tk.Tk, controller: AppController) -> None:
        self.root = root
        self.controller = controller
        self.config = controller.config
        self._devices_by_label: dict[str, dict] = {}

        root.title("Yandex AmbiSync")
        root.geometry("580x760")
        root.resizable(False, False)

        self._build_ui()
        self._refresh_monitors()
        self._restore_saved_device()

        controller.add_state_listener(self._on_sync_state_changed)

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        main_tab = ttk.Frame(notebook, padding=12)
        settings_tab = ttk.Frame(notebook, padding=12)
        notebook.add(main_tab, text="Синхронизация")
        notebook.add(settings_tab, text="Настройки")

        self.preview = tk.Canvas(main_tab, width=520, height=80, highlightthickness=1)
        self.preview.pack(pady=(0, 12))
        self.preview.create_rectangle(0, 0, 520, 80, fill="#202020", outline="")

        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(main_tab, textvariable=self.status_var).pack(anchor="w")
        self.color_var = tk.StringVar(value="RGB: —")
        ttk.Label(main_tab, textvariable=self.color_var).pack(anchor="w", pady=(4, 12))

        buttons = ttk.Frame(main_tab)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Старт", command=self.start_sync)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(
            buttons, text="Стоп", command=self.stop_sync, state="disabled"
        )
        self.stop_button.pack(side="left")

        ttk.Label(
            main_tab,
            text="Закрытие окна сворачивает приложение в трей — синхронизация продолжается.",
            wraplength=520,
            foreground="#555555",
        ).pack(anchor="w", pady=(12, 0))

        self._build_settings_tab(settings_tab)

    def _build_settings_tab(self, settings_tab: ttk.Frame) -> None:
        yandex_frame = ttk.LabelFrame(settings_tab, text="Яндекс Умный дом")
        yandex_frame.pack(fill="x", pady=(0, 10))

        paste_cb = lambda entry: paste_into_entry(self.root, entry)
        self.oauth_token, self.oauth_token_entry = add_labeled_entry(
            yandex_frame,
            "OAuth токен",
            self.config["yandex"]["oauth_token"],
            paste_cb,
            show="*",
        )
        self.client_id, _ = add_labeled_entry(
            yandex_frame,
            "Client ID (для получения токена)",
            "",
            paste_cb,
        )

        paste_row = ttk.Frame(yandex_frame)
        paste_row.grid(
            row=yandex_frame.grid_size()[1],
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=(0, 4),
        )
        ttk.Button(paste_row, text="Вставить токен из буфера", command=self._paste_token).pack(
            side="left"
        )
        self.show_token_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            paste_row,
            text="Показать токен",
            variable=self.show_token_var,
            command=self._toggle_token_visibility,
        ).pack(side="left", padx=(10, 0))

        auth_row = ttk.Frame(yandex_frame)
        auth_row.grid(row=yandex_frame.grid_size()[1], column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Button(auth_row, text="Открыть страницу авторизации", command=self._open_auth_page).pack(
            side="left"
        )
        ttk.Label(auth_row, text="Нужны права iot:view и iot:control", foreground="#555555").pack(
            side="left", padx=(10, 0)
        )

        device_row = ttk.Frame(yandex_frame)
        device_row.grid(row=yandex_frame.grid_size()[1], column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Label(device_row, text="Лампа").pack(side="left")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            device_row, textvariable=self.device_var, state="readonly", width=34
        )
        self.device_combo.pack(side="left", padx=(8, 8))
        ttk.Button(device_row, text="Загрузить", command=self._load_devices).pack(side="left")

        capture_frame = ttk.LabelFrame(settings_tab, text="Захват экрана")
        capture_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(capture_frame, text="Монитор").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(
            capture_frame, textvariable=self.monitor_var, state="readonly", width=48
        )
        self.monitor_combo.grid(row=0, column=1, padx=8, pady=4)

        ui = self.config.get("ui", {})
        self.fps_var = tk.IntVar(value=int(self.config.get("fps", 10)))
        self.brightness_var = tk.IntVar(value=int(self.config.get("brightness", 70)))
        self.smoothing_var = tk.DoubleVar(value=float(self.config.get("smoothing", 0.22)))
        self.min_change_var = tk.IntVar(value=int(self.config.get("min_color_change", 4)))
        self.downsample_var = tk.IntVar(value=int(self.config.get("downsample", 18)))
        self.minimize_to_tray_var = tk.BooleanVar(value=bool(ui.get("minimize_to_tray", True)))
        self.start_minimized_var = tk.BooleanVar(value=bool(ui.get("start_minimized", False)))

        add_labeled_scale(capture_frame, "FPS", self.fps_var, 1, 15, 1)
        add_labeled_scale(capture_frame, "Яркость лампы (1–100)", self.brightness_var, 1, 100, 2)
        add_labeled_scale(capture_frame, "Сглаживание", self.smoothing_var, 0.0, 1.0, 3)
        add_labeled_scale(capture_frame, "Порог для лампы (HSV)", self.min_change_var, 1, 20, 4)
        add_labeled_scale(capture_frame, "Downsample", self.downsample_var, 4, 30, 5)

        preset_row = ttk.Frame(capture_frame)
        preset_row.grid(row=6, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 0))
        ttk.Button(preset_row, text="Плавный режим", command=self._apply_smooth_preset).pack(side="left")
        ttk.Label(
            preset_row,
            text="FPS 10 · сглаживание 0.22 · порог лампы 4",
            foreground="#555555",
        ).pack(side="left", padx=(10, 0))

        ui_frame = ttk.LabelFrame(settings_tab, text="Поведение")
        ui_frame.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(
            ui_frame,
            text="Сворачивать в трей при закрытии окна",
            variable=self.minimize_to_tray_var,
        ).pack(anchor="w", padx=8, pady=4)
        ttk.Checkbutton(
            ui_frame,
            text="Запускать свёрнутым в трей",
            variable=self.start_minimized_var,
        ).pack(anchor="w", padx=8, pady=4)

        ttk.Button(settings_tab, text="Сохранить настройки", command=self.save_settings).pack(
            anchor="e", pady=(8, 0)
        )
        ttk.Label(
            settings_tab,
            text=f"Файл конфигурации: {config_path()}",
            wraplength=520,
        ).pack(anchor="w", pady=(8, 0))

    def _restore_saved_device(self) -> None:
        if not self.config["yandex"].get("device_name"):
            return
        label = self._device_label_from_config(self.config["yandex"])
        self.device_combo.set(label)
        self._devices_by_label[label] = self.config["yandex"]

    @staticmethod
    def _device_label_from_config(yandex: dict) -> str:
        room = yandex.get("room", "")
        name = yandex.get("device_name", yandex.get("device_id", ""))
        return f"{name} ({room})" if room else str(name)

    def _paste_token(self) -> None:
        paste_into_entry(self.root, self.oauth_token_entry)
        self.oauth_token_entry.focus_set()

    def _toggle_token_visibility(self) -> None:
        self.oauth_token_entry.configure(show="" if self.show_token_var.get() else "*")

    def _apply_smooth_preset(self) -> None:
        self.fps_var.set(int(SMOOTH_PRESET["fps"]))
        self.brightness_var.set(int(SMOOTH_PRESET["brightness"]))
        self.smoothing_var.set(float(SMOOTH_PRESET["smoothing"]))
        self.min_change_var.set(int(SMOOTH_PRESET["min_color_change"]))
        self.downsample_var.set(int(SMOOTH_PRESET["downsample"]))
        self.status_var.set("Применён плавный режим — сохраните настройки")

    def _open_auth_page(self) -> None:
        client_id = self.client_id.get().strip()
        if not client_id:
            messagebox.showinfo(
                "Client ID",
                "Создайте приложение на oauth.yandex.ru с доступами iot:view и iot:control.",
            )
            webbrowser.open("https://oauth.yandex.ru/client/new")
            return
        webbrowser.open(
            f"https://oauth.yandex.ru/authorize?response_type=token&client_id={client_id}"
        )

    def _load_devices(self) -> None:
        token = self.oauth_token.get().strip()
        if not token:
            messagebox.showerror("Токен", "Сначала вставьте OAuth токен.")
            return

        self.status_var.set("Загрузка устройств...")
        self.device_combo.set("")

        def worker() -> None:
            error_message: str | None = None
            devices = []
            total_devices = 0
            try:
                client = YandexSmartHomeClient(token)
                devices, total_devices = client.list_color_lamps()
                client.close()
            except YandexApiError as exc:
                error_message = str(exc)
            except Exception as exc:
                error_message = f"Не удалось загрузить устройства: {exc}"

            def apply() -> None:
                if error_message:
                    self.status_var.set("Ошибка загрузки")
                    messagebox.showerror("Яндекс API", error_message)
                    return

                self._devices_by_label = {
                    device.label: {
                        "device_id": device.id,
                        "device_name": device.name,
                        "room": device.room,
                        "color_mode": device.color_mode,
                        "device_type": device.device_type,
                    }
                    for device in devices
                }
                labels = list(self._devices_by_label.keys())
                self.device_combo["values"] = labels
                if not labels:
                    self.status_var.set("Лампы не найдены")
                    messagebox.showwarning(
                        "Устройства",
                        f"Лампы не найдены. Всего устройств: {total_devices}.",
                    )
                    return
                self.device_combo.set(labels[0])
                self.status_var.set(f"Найдено ламп: {len(labels)}")
                messagebox.showinfo("Устройства", f"Найдено ламп: {len(labels)}")

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_monitors(self) -> None:
        sampler = ScreenColorSampler()
        monitors = sampler.list_monitors()
        sampler.close()

        labels = [str(item["label"]) for item in monitors]
        self.monitor_combo["values"] = labels
        if not labels:
            self.monitor_combo.set("")
            return

        selected_index = int(self.config.get("monitor_index", 1))
        selected_label = next(
            (str(item["label"]) for item in monitors if item["index"] == selected_index),
            labels[0],
        )
        self.monitor_combo.set(selected_label)
        self._monitor_map = {str(item["label"]): int(item["index"]) for item in monitors}

    def _selected_yandex_settings(self) -> dict:
        label = self.device_var.get().strip()
        selected = self._devices_by_label.get(label)
        if selected:
            return {"oauth_token": self.oauth_token.get().strip(), **selected}
        return {
            "oauth_token": self.oauth_token.get().strip(),
            "device_id": self.config["yandex"].get("device_id", ""),
            "device_name": self.config["yandex"].get("device_name", ""),
            "room": self.config["yandex"].get("room", ""),
            "color_mode": self.config["yandex"].get("color_mode", "hsv"),
        }

    def collect_config(self) -> dict:
        monitor_label = self.monitor_var.get()
        return {
            "monitor_index": self._monitor_map.get(monitor_label, 1),
            "fps": int(self.fps_var.get()),
            "brightness": int(self.brightness_var.get()),
            "smoothing": float(self.smoothing_var.get()),
            "min_color_change": int(self.min_change_var.get()),
            "downsample": int(self.downsample_var.get()),
            "ui": {
                "minimize_to_tray": bool(self.minimize_to_tray_var.get()),
                "start_minimized": bool(self.start_minimized_var.get()),
            },
            "yandex": self._selected_yandex_settings(),
        }

    def save_settings(self) -> None:
        self.controller.save_config(self.collect_config())
        self.config = self.controller.config
        messagebox.showinfo("Сохранено", "Настройки сохранены.")

    def start_sync(self) -> None:
        config = self.collect_config()
        error = self.controller.start_sync(
            config,
            on_status=self._set_status,
            on_color=self._set_color,
            on_error=self._set_error,
        )
        if error:
            messagebox.showerror("Настройки", error)

    def start_from_tray(self) -> None:
        if self.controller.is_syncing:
            self.show_window()
            return
        self.start_sync()

    def stop_sync(self) -> None:
        self.controller.stop_sync()

    def _on_sync_state_changed(self, syncing: bool) -> None:
        def update() -> None:
            if syncing:
                self.start_button.configure(state="disabled")
                self.stop_button.configure(state="normal")
                self.status_var.set("Синхронизация запущена")
            else:
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")

        self.root.after(0, update)

    def _set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_var.set(message))

    def _set_error(self, message: str, fatal: bool = True) -> None:
        def update() -> None:
            self.status_var.set(message)
            if fatal:
                messagebox.showerror("Ошибка", message)
                self.stop_sync()
            else:
                messagebox.showwarning("Предупреждение", message)

        self.root.after(0, update)

    def _set_color(self, color) -> None:
        def update() -> None:
            hex_color = f"#{color.r:02x}{color.g:02x}{color.b:02x}"
            self.preview.delete("all")
            self.preview.create_rectangle(0, 0, 520, 80, fill=hex_color, outline="")
            self.color_var.set(f"RGB: {color.r}, {color.g}, {color.b}")

        self.root.after(0, update)

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def should_minimize_to_tray(self) -> bool:
        return bool(self.minimize_to_tray_var.get())

    def should_start_minimized(self) -> bool:
        return bool(self.start_minimized_var.get())
