from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_ICO_PATH = ASSETS_DIR / "ziweiqi_app.ico"
ICON_PNG_PATH = ASSETS_DIR / "ziweiqi_app.png"


def _set_windows_app_id(app_id: str) -> None:
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def apply_app_icon(window, app_id: str = "ziweiqi.desktop.app") -> None:
    _set_windows_app_id(app_id)

    try:
        if ICON_ICO_PATH.exists():
            window.iconbitmap(default=str(ICON_ICO_PATH))
    except Exception:
        pass

    try:
        if ICON_PNG_PATH.exists():
            import tkinter as tk

            photo = tk.PhotoImage(file=str(ICON_PNG_PATH))
            window._codex_app_icon_photo = photo
            window.iconphoto(True, photo)
    except Exception:
        pass
