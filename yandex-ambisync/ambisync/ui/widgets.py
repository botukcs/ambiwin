from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def add_labeled_scale(
    parent: ttk.LabelFrame,
    label: str,
    variable: tk.Variable,
    from_: float,
    to: float,
    row: int,
) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
    ttk.Scale(
        parent,
        from_=from_,
        to=to,
        variable=variable,
        orient="horizontal",
        length=280,
    ).grid(row=row, column=1, padx=8, pady=4, sticky="ew")


def add_labeled_entry(
    parent: ttk.LabelFrame,
    label: str,
    value: str,
    on_paste: Callable[[tk.Entry], None],
    show: str | None = None,
) -> tuple[tk.StringVar, tk.Entry]:
    row = parent.grid_size()[1]
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
    var = tk.StringVar(value=value)
    entry = tk.Entry(parent, textvariable=var, width=42, show=show, exportselection=True)
    entry.grid(row=row, column=1, padx=8, pady=4, sticky="ew")
    enable_clipboard(entry, on_paste)
    parent.columnconfigure(1, weight=1)
    return var, entry


def enable_clipboard(entry: tk.Entry, on_paste: Callable[[tk.Entry], None]) -> None:
    menu = tk.Menu(entry, tearoff=0)
    menu.add_command(label="Вырезать", command=lambda: entry.event_generate("<<Cut>>"))
    menu.add_command(label="Копировать", command=lambda: entry.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: on_paste(entry))

    def show_menu(event: tk.Event) -> str:
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    entry.bind("<Button-3>", show_menu)
    entry.bind("<Control-v>", lambda _event: on_paste(entry) or "break")
    entry.bind("<Control-V>", lambda _event: on_paste(entry) or "break")
    entry.bind("<Shift-Insert>", lambda _event: on_paste(entry) or "break")
    entry.bind("<Control-Insert>", lambda _event: entry.event_generate("<<Copy>>") or "break")


def paste_into_entry(root: tk.Misc, entry: tk.Entry) -> None:
    try:
        text = root.clipboard_get()
    except tk.TclError:
        return

    if entry.selection_present():
        entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
    entry.insert(tk.INSERT, text)
