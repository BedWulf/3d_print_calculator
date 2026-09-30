"""Главное окно приложения: вкладки Калькулятор / Принтеры / Материалы /
Расходные материалы / Настройки."""

from PyQt5.QtWidgets import QMainWindow, QTabWidget

from ..db.repository import Repository
from .calculator_tab import CalculatorTab
from .crud_tabs import PrintersTab, MaterialsTab, ConsumablesTab, SettingsTab


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository):
        super().__init__()
        self.setWindowTitle("Калькулятор цены 3D-печати")
        self.resize(980, 720)
        self.repo = repo

        tabs = QTabWidget()
        self.calc_tab = CalculatorTab(repo)
        tabs.addTab(self.calc_tab, "Калькулятор")
        tabs.addTab(PrintersTab(repo), "Принтеры")
        tabs.addTab(MaterialsTab(repo), "Материалы")
        tabs.addTab(ConsumablesTab(repo), "Расходные материалы")
        tabs.addTab(SettingsTab(repo), "Настройки")

        # при переключении на калькулятор подтягиваем свежие справочники
        tabs.currentChanged.connect(lambda i: i == 0 and self.calc_tab.reload_sources())
        self.setCentralWidget(tabs)
