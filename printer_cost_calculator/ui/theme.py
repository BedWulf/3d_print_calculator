"""Тёмная тема оформления: глубокий бордовый фон + золотые акценты.

Цвета подобраны так, чтобы не «кричать»: приглушённые тона, мягкий контраст
(не чистый белый на чёрном), одинаковая читаемость основного текста и цифр.

Палитра:
    BG_DEEP   #221319  — фон главного окна (самый тёмный бордовый)
    BG        #2b1a22  — фон вкладок/групп
    SURFACE   #341f28  — поля ввода, таблицы, списки
    SURFACE_2 #3d2731  — чередующиеся строки, header'ы
    GOLD      #d4b06a  — основной золотой текст (аккуратнее чистого жёлтого)
    GOLD_SOFT #b89b62  — второстепенные подписи
    TEXT      #e9ddd2  — обычный текст (тёплый светлый, не слепит)
    BORDER    #52323f  — границы элементов
"""

from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QApplication

BG_DEEP = "#221319"
BG = "#2b1a22"
SURFACE = "#341f28"
SURFACE_2 = "#3d2731"
GOLD = "#d4b06a"
GOLD_DIM = "#8a744c"
GOLD_SOFT = "#b89b62"
TEXT = "#e9ddd2"
TEXT_MUTED = "#b3a499"
BORDER = "#52323f"
HOVER = "#4a2e3a"
SEL = "#5a3a48"
DANGER = "#cf7d6d"

FONT_FAMILY = "Segoe UI"

STYLESHEET = f"""
/* ---------------- общая база ---------------- */
QMainWindow, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT};
    font-family: "{FONT_FAMILY}", "DejaVu Sans", sans-serif;
    font-size: 14px;
}}

/* ---------------- вкладки ---------------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {BG};
    top: -1px;
}}
/* documentMode снимает «каркас» вокруг tabBar — вкладки больше не обрезаются
   по краям (первая и последняя целиком видны); рамку держит ::pane ниже. */
QTabWidget::tab-bar {{
    left: 4px;
}}
QTabBar {{
    qdocument-mode: true;
}}
QTabBar::tab {{
    background-color: {SURFACE};
    color: {GOLD_SOFT};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 3px;
    font-weight: 600;
}}
QTabBar::tab:hover {{ background-color: {HOVER}; }}
QTabBar::tab:selected {{
    background-color: {SURFACE_2};
    color: {GOLD};
    border-bottom: 2px solid {GOLD};
}}

/* ---------------- группы ---------------- */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    background-color: {BG};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {GOLD};
    font-weight: 700;
}}

/* ---------------- надписи ---------------- */
QLabel {{ background: transparent; color: {TEXT}; }}
QLabel[role="accent"] {{ color: {GOLD}; font-weight: 700; }}
QLabel[role="muted"] {{ color: {TEXT_MUTED}; }}

/* ---------------- поля ввода ---------------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: {GOLD_DIM};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {GOLD_DIM};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: {TEXT_MUTED};
    background-color: {BG};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {GOLD};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {SEL};
    selection-color: {GOLD};
    outline: none;
}}

/* ---------------- чекбоксы ---------------- */
QCheckBox {{ background: transparent; color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {SURFACE};
}}
QCheckBox::indicator:hover {{ border: 1px solid {GOLD_DIM}; }}
QCheckBox::indicator:checked {{
    background-color: {GOLD};
    border: 1px solid {GOLD};
}}

/* ---------------- кнопки ---------------- */
QPushButton {{
    background-color: {SURFACE_2};
    color: {GOLD};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {HOVER}; border-color: {GOLD_DIM}; }}
QPushButton:pressed {{ background-color: {SEL}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; background-color: {BG}; }}
QPushButton#default {{
    background-color: {GOLD};
    color: {BG_DEEP};
    border: none;
    font-size: 15px;
    font-weight: 700;
    padding: 10px 22px;
}}
QPushButton#default:hover {{ background-color: #e2c07d; }}
QPushButton#default:pressed {{ background-color: {GOLD_DIM}; }}
QPushButton#danger {{ color: {DANGER}; }}

/* ---------------- таблицы ---------------- */
QTableWidget, QTableView {{
    background-color: {SURFACE};
    alternate-background-color: {SURFACE_2};
    color: {TEXT};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 4px;
    selection-background-color: {SEL};
    selection-color: {GOLD};
}}
QHeaderView::section {{
    background-color: {SURFACE_2};
    color: {GOLD};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-weight: 700;
}}
QTableCornerButton::section {{ background-color: {SURFACE_2}; border: none; }}

/* ---------------- списки ---------------- */
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT};
    padding: 2px;
    outline: none;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}
QListWidget::item:hover {{ background-color: {HOVER}; }}
QListWidget::item:selected {{ background-color: {SEL}; color: {GOLD}; }}

/* ---------------- прокрутка ---------------- */
QScrollBar:vertical {{
    background: {BG}; width: 12px; margin: 0; border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; min-height: 24px; border-radius: 6px; margin: 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {GOLD_DIM}; }}
QScrollBar:horizontal {{
    background: {BG}; height: 12px; margin: 0; border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; min-width: 24px; border-radius: 6px; margin: 2px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ---------------- прочее ---------------- */
QToolTip {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {GOLD_DIM};
    padding: 4px 8px;
}}
QMessageBox {{ background-color: {BG}; }}
QStatusBar {{ background-color: {BG}; color: {TEXT_MUTED}; }}
"""


def apply_theme(app: QApplication) -> None:
    """Включает тему и базовый шрифт для всего приложения."""
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    base = QFont(FONT_FAMILY, 10)
    app.setFont(base)
