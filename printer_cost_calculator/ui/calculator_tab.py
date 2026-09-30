"""Вкладка «Калькулятор»: ввод данных после слайсинга и результат расчёта."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import (
    QWidget, QComboBox, QLineEdit, QCheckBox, QLabel, QPushButton,
    QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
    QScrollArea, QSizePolicy,
)

from ..db.models import Consumable
from ..logic.calculator import CalcInput, calculate


class CalculatorTab(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        lay = QVBoxLayout(self)

        # ----------------------------- форма ввода -----------------------------
        self.c_printer = QComboBox()

        self.e_mass = QLineEdit()

        self.c_part_mat = QComboBox()

        self.cb_supports = QCheckBox("Есть поддержки")
        self.e_sup_mass = QLineEdit()
        self.c_sup_mat = QComboBox()
        self.e_sup_mass.setEnabled(False); self.c_sup_mat.setEnabled(False)
        self.cb_supports.toggled.connect(lambda on: (
            self.e_sup_mass.setEnabled(on), self.c_sup_mat.setEnabled(on)))

        self.e_time = QLineEdit()
        self.c_time_mode = QComboBox()
        self.c_time_mode.addItem("на 1 деталь", True)
        self.c_time_mode.addItem("на всю партию", False)

        self.e_qty = QLineEdit("1")

        # расходники: флажки по типам + выпадающий выбор конкретного клея/сопла
        box = QGroupBox("Расходные материалы")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(8, 4, 8, 6)
        bl.setSpacing(3)
        self._consum_checks: dict[str, QCheckBox] = {}
        for kind in Consumable.KINDS:
            cb = QCheckBox(Consumable.KIND_LABELS[kind])
            self._consum_checks[kind] = cb
            bl.addWidget(cb)
        self.c_glue = QComboBox(); self.c_nozzle = QComboBox()
        gl = QHBoxLayout(); gl.addWidget(QLabel("Клей:")); gl.addWidget(self.c_glue)
        gl.addWidget(QLabel("Сопло:")); gl.addWidget(self.c_nozzle)
        bl.addLayout(gl)

        calc_btn = QPushButton("РАССЧИТАТЬ")
        calc_btn.clicked.connect(self._on_calc)

        # ----------------------------- результат --------------------------------
        # Ход расчёта занимает всю ширину под формой и растягивается по высоте:
        # помещаются ВСЕ строки сразу, листать формулы не нужно.
        # Форма ввода — компактная сетка слева; при нехватке места прокручивается
        # только она, поле результата всегда видно целиком.
        form_host = QWidget()
        grid = QGridLayout(form_host)
        grid.setContentsMargins(4, 4, 12, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        def add_row_pair(row, col, label_text, widget):
            lab = QLabel(label_text)
            lab.setProperty("role", "muted")
            grid.addWidget(lab, row, col * 2)
            widget.setMinimumWidth(90)
            grid.addWidget(widget, row, col * 2 + 1)

        self._form_rows = []          # (метка, поле) для раскладки
        r = 0
        add_row_pair(r, 0, "Принтер:", self.c_printer); r += 1
        add_row_pair(r, 0, "Масса изделия, г:", self.e_mass)
        add_row_pair(r, 0, "Материал изделия:", self.c_part_mat); r += 1
        grid.addWidget(self.cb_supports, r, 0, 1, 2); r += 1
        add_row_pair(r, 0, "Масса поддержек, г:", self.e_sup_mass)
        add_row_pair(r, 0, "Мат. поддержек:", self.c_sup_mat); r += 1
        add_row_pair(r, 0, "Время печати, ч:", self.e_time)
        add_row_pair(r, 0, "Время указано:", self.c_time_mode); r += 1
        add_row_pair(r, 0, "Количество, шт.:", self.e_qty); r += 1

        box.setTitle("Расходные материалы")
        grid.addWidget(box, r, 0, 1, 4)
        box.setMaximumHeight(175)
        r += 1

        calc_btn.setObjectName("default")
        grid.addWidget(calc_btn, r, 0, 1, 4)
        r += 1
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setRowStretch(r, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll.setMaximumHeight(430)   # выше — только если окно маленькое
        lay.addWidget(scroll, 0)

        res_box = QVBoxLayout()
        head = QLabel("Ход расчёта:")
        head.setProperty("role", "accent")
        res_box.addWidget(head)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Статья", "Формула", "Сумма, ₽"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(380)
        # Строки подгоняются под содержимое: длинные формулы видны целиком,
        # горизонтальная прокрутка таблицы отключена.
        self.table.horizontalScrollBar().setEnabled(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        res_box.addWidget(self.table, 1)
        lay.addLayout(res_box, 1)

        tot = QHBoxLayout()
        self.l_per_part = QLabel("Цена за деталь: —")
        self.l_batch = QLabel("Цена за партию: —")
        for lbl in (self.l_per_part, self.l_batch):
            f = lbl.font()
            f.setPointSize(f.pointSize() + 3)
            f.setBold(True)
            lbl.setFont(f)
            lbl.setProperty("role", "accent")   # золото из темы
        tot.addWidget(self.l_per_part)
        tot.addWidget(self.l_batch)
        lay.addLayout(tot)

        self.reload_sources()

    # ------------------------------------------------------------------ data
    def reload_sources(self):
        """Обновляет списки из БД (после правок на других вкладках)."""
        keep_p = self.c_printer.currentText()
        self.printers = self.repo.list_printers()
        self.materials = self.repo.list_materials()
        self.consumables = self.repo.list_consumables()

        self.c_printer.clear()
        for p in self.printers:
            self.c_printer.addItem(p.name, p.id)
        i = self.c_printer.findText(keep_p)
        if i >= 0:
            self.c_printer.setCurrentIndex(i)

        for combo in (self.c_part_mat, self.c_sup_mat):
            cur = combo.currentData()
            combo.clear()
            for m in self.materials:
                combo.addItem(m.name, m.id)
            if cur is not None:
                j = combo.findData(cur)
                if j >= 0:
                    combo.setCurrentIndex(j)

        for kind, combo in ((Consumable.KIND_GLUE, self.c_glue),
                            (Consumable.KIND_NOZZLE, self.c_nozzle)):
            combo.clear()
            for c in self.consumables:
                if c.kind == kind:
                    combo.addItem(c.name, c.id)

    def _selected_consumables(self) -> list[Consumable]:
        sel = []
        for kind, cb in self._consum_checks.items():
            if not cb.isChecked():
                continue
            if kind in (Consumable.KIND_GLUE, Consumable.KIND_NOZZLE):
                cid = (self.c_glue if kind == Consumable.KIND_GLUE
                       else self.c_nozzle).currentData()
                if cid is not None:
                    sel.append(next(c for c in self.consumables if c.id == cid))
            else:
                sel.extend(c for c in self.consumables if c.kind == kind)
        return sel

    # ----------------------------------------------------------------- calc
    def _on_calc(self):
        printer = next((p for p in self.printers
                        if p.id == self.c_printer.currentData()), None)
        part_mat = next((m for m in self.materials
                         if m.id == self.c_part_mat.currentData()), None)
        sup_mat = next((m for m in self.materials
                        if m.id == self.c_sup_mat.currentData()), None)
        if printer is None or part_mat is None:
            QMessageBox.warning(self, "Ввод данных",
                                "Выберите принтер и материал изделия.")
            return

        def num(line):
            try:
                return float(line.text().strip().replace(",", "."))
            except ValueError:
                return 0.0

        inp = CalcInput(
            printer=printer,
            print_time_hours=num(self.e_time),
            part_mass_g=num(self.e_mass),
            part_material=part_mat,
            use_supports=self.cb_supports.isChecked(),
            support_mass_g=num(self.e_sup_mass),
            support_material=sup_mat,
            quantity=int(num(self.e_qty) or 1),
            selected_consumables=self._selected_consumables(),
            settings=self.repo.get_settings(),
            time_is_per_part=self.c_time_mode.currentData(),
        )
        res = calculate(inp)

        self.table.setRowCount(0)
        if res.errors:
            QMessageBox.warning(self, "Проверьте данные", "\n".join(res.errors))
            self.l_per_part.setText("Цена за деталь: —")
            self.l_batch.setText("Цена за партию: —")
            return

        self.table.setRowCount(len(res.steps))
        for r, s in enumerate(res.steps):
            self.table.setItem(r, 0, QTableWidgetItem(s.title))
            it = QTableWidgetItem(s.formula)
            it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # перенос длинных формул по словам — текст виден целиком, без «...»
            it.setFlags(it.flags() | Qt.ItemIsWrapText)
            self.table.setItem(r, 1, it)
            self.table.setItem(r, 2, QTableWidgetItem(f"{s.value_rub:.2f}"))
        # высота каждой строки = нужной для полного текста формулы (без «...»)
        col_w = max(self.table.columnWidth(1), 300)
        fm = QFontMetrics(self.table.font())
        for r in range(self.table.rowCount()):
            txt = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            rect = fm.boundingRect(0, 0, col_w, 1000,
                                   Qt.TextWordWrap | Qt.AlignLeft, txt)
            self.table.setRowHeight(r, max(28, rect.height() + 10))
        self.l_per_part.setText(f"Цена за деталь: {res.per_part_total:.2f} ₽")
        self.l_batch.setText(f"Цена за партию ({inp.quantity} шт.): "
                             f"{res.batch_total:.2f} ₽")
