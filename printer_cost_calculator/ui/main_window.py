"""Главное окно приложения: вкладки Калькулятор / Принтеры / Материалы /
Расходные материалы / Настройки."""

from PyQt5.QtWidgets import QMainWindow, QTabWidget

from ..db.repository import Repository
from .calculator_tab import CalculatorTab
from .crud_tabs import PrintersTab, MaterialsTab, ConsumablesTab, SettingsTab
from .planner_tab import PlannerTab


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository):
        super().__init__()
        self.setWindowTitle("Калькулятор цены 3D-печати")
        self.resize(1240, 760)
        self.repo = repo

        tabs = QTabWidget()
        tabs.setDocumentMode(True)   # без «каркаса» tabBar — вкладки не обрезаются по краям
        self.calc_tab = CalculatorTab(repo)
        tabs.addTab(self.calc_tab, "Калькулятор")
        self.planner_tab = PlannerTab(repo)
        tabs.addTab(self.planner_tab, "Планировщик (столы)")
        tabs.addTab(PrintersTab(repo), "Принтеры")
        tabs.addTab(MaterialsTab(repo), "Материалы")
        tabs.addTab(ConsumablesTab(repo), "Расходные материалы")
        tabs.addTab(SettingsTab(repo), "Настройки")

        # при переключении подтягиваем свежие справочники из вкладок БД
        def _refresh(i):
            if i == 0:
                self.calc_tab.reload_sources()
            elif i == 1:
                self.planner_tab.reload_sources()
        tabs.currentChanged.connect(_refresh)
        self.setCentralWidget(tabs)
