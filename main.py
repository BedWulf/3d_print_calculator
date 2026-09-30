"""Точка входа десктоп-приложения (PyQt5).

Запуск для разработки:  python main.py
Сборка .exe:           build_exe.bat (на Windows)
"""

import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from printer_cost_calculator.db.repository import Repository
from printer_cost_calculator.ui.main_window import MainWindow
from printer_cost_calculator.ui.theme import apply_theme


def data_dir() -> Path:
    """Каталог для БД: %APPDATA%/Price3DCalc на Windows, ~/.local/share иначе.
    При запуске собранного .exe база лежит рядом с профилем пользователя,
    а не внутри временной распаковки PyInstaller."""
    if getattr(sys, "frozen", False):  # запущен exe, собранный PyInstaller
        base = os.environ.get("APPDATA", str(Path.home()))
        d = Path(base) / "Price3DCalc"
    else:
        d = Path(__file__).resolve().parent  # dev: база в корне проекта
    d.mkdir(parents=True, exist_ok=True)
    return d


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    repo = Repository(data_dir() / "calculator.db")
    win = MainWindow(repo)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
