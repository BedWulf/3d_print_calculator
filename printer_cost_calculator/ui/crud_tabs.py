"""Вкладки-редакторы баз данных: Принтеры, Материалы, Расходные материалы, Настройки.

Все справочники полностью редактируются пользователем: добавление, изменение,
удаление записей. Стартовые данные вносятся только при первом запуске.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QListWidget, QGroupBox,
)

from ..db.models import Printer, Material, Consumable, Settings


def _title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "accent")
    return lbl


class PrintersTab(QWidget):
    """Список принтеров + форма параметров для расчёта."""

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        lay = QHBoxLayout(self)

        self.listw = _ListWidget(repo.list_printers, lambda o: o.name, self)
        self.listw.currentTextChanged.connect(self._load_row)
        left = QVBoxLayout()
        left.addWidget(_title("Принтеры"))
        left.addWidget(self.listw)
        btns = QHBoxLayout()
        for text, slot in (("Добавить", self._add), ("Удалить", self._delete)):
            b = QPushButton(text); b.clicked.connect(slot); btns.addWidget(b)
        left.addLayout(btns)
        lay.addLayout(left, 1)

        box = QGroupBox("Параметры выбранного принтера")
        form = QFormLayout(box)
        self.e_name = QLineEdit();      form.addRow("Название:", self.e_name)
        self.e_kwh = QLineEdit();       form.addRow("Потребление, кВт·ч/час:", self.e_kwh)
        self.e_dep = QLineEdit();       form.addRow("Амортизация, ₽/час:", self.e_dep)
        bed_row = QHBoxLayout()
        self.e_bed_x = QLineEdit(); self.e_bed_y = QLineEdit(); self.e_bed_z = QLineEdit()
        for w in (self.e_bed_x, self.e_bed_y, self.e_bed_z):
            w.setMaximumWidth(90); bed_row.addWidget(w)
        bed_row.addWidget(QLabel("(X × Y × Z, мм)"))
        bed_row.addStretch(1)
        form.addRow("Размер платформы:", bed_row)
        self.e_note = QLineEdit();      form.addRow("Примечание:", self.e_note)
        save = QPushButton("Сохранить"); save.setObjectName("default")
        save.clicked.connect(self._save)
        form.addRow(save)
        hint = QLabel("Подсказка: амортизация = цена принтера ÷ ресурс наработки в часах.\n"
                      "Например: 36 000 ₽ ÷ 12 000 ч = 3 ₽/ч.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        lay.addWidget(box, 2)

    # ---------------------------------------------------------------- helpers
    def _current(self):
        return self.listw.current_item()

    def _load_row(self, _=None):
        p = self._current()
        if not p:
            return
        self.e_name.setText(p.name)
        self.e_kwh.setText(str(p.electricity_kwh_per_hour))
        self.e_dep.setText(str(p.depreciation_rub_per_hour))
        self.e_bed_x.setText(str(p.bed_x_mm))
        self.e_bed_y.setText(str(p.bed_y_mm))
        self.e_bed_z.setText(str(p.bed_z_mm))
        self.e_note.setText(p.note)

    def _add(self):
        pid = self.repo.add_printer(Printer(name="Новый принтер"))
        self.listw.reload(select=str(self.repo.conn.execute(
            "SELECT name FROM printers WHERE id=?", (pid,)).fetchone()[0]))

    def _delete(self):
        p = self._current()
        if p and QMessageBox.question(self, "Удалить", f"Удалить «{p.name}»?\n"
                "Это действие нельзя отменить.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_printer(p.id)
            self.listw.reload()

    def _save(self):
        p = self._current()
        if not p:
            QMessageBox.information(self, "Сохранение", "Сначала выберите принтер в списке.")
            return
        p.name = self.e_name.text().strip() or p.name
        p.electricity_kwh_per_hour = _f(self.e_kwh)
        p.depreciation_rub_per_hour = _f(self.e_dep)
        p.bed_x_mm = _f(self.e_bed_x, p.bed_x_mm)
        p.bed_y_mm = _f(self.e_bed_y, p.bed_y_mm)
        p.bed_z_mm = _f(self.e_bed_z, p.bed_z_mm)
        p.note = self.e_note.text().strip()
        self.repo.update_printer(p)
        self.listw.reload(select=p.name)


class MaterialsTab(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        lay = QHBoxLayout(self)

        self.listw = _ListWidget(repo.list_materials,
                                 lambda o: f"{o.name} ({o.spool_weight_kg} кг, {o.price_rub:.0f} ₽)",
                                 self)
        self.listw.currentTextChanged.connect(self._load_row)
        left = QVBoxLayout()
        left.addWidget(_title("Материалы"))
        left.addWidget(self.listw)
        btns = QHBoxLayout()
        for text, slot in (("Добавить", self._add), ("Удалить", self._delete)):
            b = QPushButton(text); b.clicked.connect(slot); btns.addWidget(b)
        left.addLayout(btns)
        lay.addLayout(left, 1)

        box = QGroupBox("Параметры выбранного материала")
        form = QFormLayout(box)
        self.e_name = QLineEdit();   form.addRow("Название:", self.e_name)
        self.e_dens = QLineEdit();   form.addRow("Плотность, г/см³:", self.e_dens)
        self.c_spool = QComboBox()
        for w in Material.SPOOL_WEIGHTS_KG:
            self.c_spool.addItem(f"{w} кг", w)
        form.addRow("Катушка:", self.c_spool)
        self.e_price = QLineEdit();  form.addRow("Цена за катушку, ₽:", self.e_price)
        self.l_ppg = QLabel("—")
        self.l_ppg.setProperty("role", "accent")
        form.addRow("Цена за грамм (расчётная):", self.l_ppg)
        self.e_note = QLineEdit();   form.addRow("Примечание:", self.e_note)
        save = QPushButton("Сохранить"); save.setObjectName("default")
        save.clicked.connect(self._save)
        form.addRow(save)
        lay.addWidget(box, 2)

        self.e_price.textChanged.connect(self._update_ppg)
        self.c_spool.currentIndexChanged.connect(self._update_ppg)

    def _current(self):
        return self.listw.current_item()

    def _load_row(self, _=None):
        m = self._current()
        if not m:
            return
        self.e_name.setText(m.name)
        self.e_dens.setText(str(m.density_g_cm3))
        idx = self.c_spool.findData(m.spool_weight_kg)
        if idx >= 0:
            self.c_spool.setCurrentIndex(idx)
        self.e_price.setText(str(m.price_rub))
        self.e_note.setText(m.note)
        self._update_ppg()

    def _update_ppg(self):
        try:
            price = float(self.e_price.text().replace(",", "."))
            spool = self.c_spool.currentData()
            self.l_ppg.setText(f"{price / (spool * 1000):.4f} ₽/г")
        except (ValueError, ZeroDivisionError):
            self.l_ppg.setText("—")

    def _add(self):
        mid = self.repo.add_material(Material(name="Новый материал"))
        self.listw.reload(select=self.repo.conn.execute(
            "SELECT name FROM materials WHERE id=?", (mid,)).fetchone()[0])

    def _delete(self):
        m = self._current()
        if m and QMessageBox.question(self, "Удалить", f"Удалить «{m.name}»?\n"
                "Это действие нельзя отменить.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_material(m.id)
            self.listw.reload()

    def _save(self):
        m = self._current()
        if not m:
            QMessageBox.information(self, "Сохранение", "Сначала выберите материал в списке.")
            return
        m.name = self.e_name.text().strip() or m.name
        m.density_g_cm3 = _f(self.e_dens, 1.0)
        m.spool_weight_kg = self.c_spool.currentData()
        m.price_rub = _f(self.e_price)
        m.note = self.e_note.text().strip()
        self.repo.update_material(m)
        self.listw.reload(select=m.name)


class ConsumablesTab(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        lay = QHBoxLayout(self)

        self.listw = _ListWidget(repo.list_consumables,
                                 lambda o: f"[{Consumable.KIND_LABELS.get(o.kind, o.kind)}] {o.name}",
                                 self)
        self.listw.currentTextChanged.connect(self._load_row)
        left = QVBoxLayout()
        left.addWidget(_title("Расходные материалы"))
        left.addWidget(self.listw)
        btns = QHBoxLayout()
        for text, slot in (("Добавить", self._add), ("Удалить", self._delete)):
            b = QPushButton(text); b.clicked.connect(slot); btns.addWidget(b)
        left.addLayout(btns)
        lay.addLayout(left, 1)

        box = QGroupBox("Параметры выбранного расходника")
        form = QFormLayout(box)
        self.c_kind = QComboBox()
        for k in Consumable.KINDS:
            self.c_kind.addItem(Consumable.KIND_LABELS[k], k)
        form.addRow("Тип:", self.c_kind)
        self.e_name = QLineEdit();   form.addRow("Название:", self.e_name)
        self.e_unit = QLineEdit();   form.addRow("Ед. измерения:", self.e_unit)
        self.e_cons = QLineEdit()
        form.addRow("Расход на деталь (доля единицы):", self.e_cons)
        self.e_price = QLineEdit();  form.addRow("Цена за ед., ₽:", self.e_price)
        self.e_note = QLineEdit();   form.addRow("Примечание:", self.e_note)
        save = QPushButton("Сохранить"); save.setObjectName("default")
        save.clicked.connect(self._save)
        form.addRow(save)
        hint = QLabel("Пример: сопло служит 200 ч → расход на деталь 6 ч = 0.03 ресурса; "
                      "цена — за целое сопло.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        lay.addWidget(box, 2)

    def _current(self):
        return self.listw.current_item()

    def _load_row(self, _=None):
        c = self._current()
        if not c:
            return
        idx = self.c_kind.findData(c.kind)
        if idx >= 0:
            self.c_kind.setCurrentIndex(idx)
        self.e_name.setText(c.name)
        self.e_unit.setText(c.unit)
        self.e_cons.setText(str(c.consumption_per_part))
        self.e_price.setText(str(c.price_rub))
        self.e_note.setText(c.note)

    def _add(self):
        cid = self.repo.add_consumable(Consumable(
            kind=self.c_kind.currentData(), name="Новый расходник"))
        self.listw.reload()

    def _delete(self):
        c = self._current()
        if c and QMessageBox.question(self, "Удалить", f"Удалить «{c.name}»?\n"
                "Это действие нельзя отменить.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_consumable(c.id)
            self.listw.reload()

    def _save(self):
        c = self._current()
        if not c:
            QMessageBox.information(self, "Сохранение", "Сначала выберите запись в списке.")
            return
        c.kind = self.c_kind.currentData()
        c.name = self.e_name.text().strip() or c.name
        c.unit = self.e_unit.text().strip() or "шт."
        c.consumption_per_part = _f(self.e_cons)
        c.price_rub = _f(self.e_price)
        c.note = self.e_note.text().strip()
        self.repo.update_consumable(c)
        self.listw.reload(select=f"[{Consumable.KIND_LABELS[c.kind]}] {c.name}")


class SettingsTab(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        lay = QVBoxLayout(self)
        box = QGroupBox("Общие параметры расчёта")
        form = QFormLayout(box)
        s = repo.get_settings()
        self.e_elec = QLineEdit(str(s.electricity_price_rub_per_kwh))
        form.addRow("Тариф электроэнергии, ₽/кВт·ч:", self.e_elec)
        self.e_labor = QLineEdit(str(s.labor_rate_rub_per_hour))
        form.addRow("Ставка труда, ₽/час (резерв):", self.e_labor)
        self.e_markup = QLineEdit(str(s.markup_percent))
        form.addRow("Наценка, % (резерв):", self.e_markup)
        save = QPushButton("Сохранить настройки")
        save.setObjectName("default")
        save.clicked.connect(self._save)
        form.addRow(save)
        lay.addWidget(box)
        lay.addStretch(1)

    def _save(self):
        s = Settings(
            electricity_price_rub_per_kwh=_f(self.e_elec, 5.0),
            labor_rate_rub_per_hour=_f(self.e_labor),
            markup_percent=_f(self.e_markup),
        )
        self.repo.save_settings(s)
        QMessageBox.information(self, "Настройки", "Сохранено.")


# --------------------------------------------------------------------- утилиты
def _f(line: QLineEdit, default: float = 0.0) -> float:
    try:
        return float(line.text().strip().replace(",", ".") or default)
    except ValueError:
        return default


class _ListWidget(QListWidget):
    """QListWidget с перезагрузкой из функции и выбором по тексту."""

    def __init__(self, loader, display, parent=None):
        super().__init__(parent)
        self._loader = loader
        self._display = display
        self.reload()

    def reload(self, select: str | None = None):
        self._items = self._loader()
        self.clear()
        for o in self._items:
            self.addItem(self._display(o))
        if select:
            idx = self.findItems(select, Qt.MatchExactly)
            if idx:
                self.setCurrentItem(idx[0])

    def current_item(self):
        row = self.currentRow()
        return self._items[row] if 0 <= row < len(self._items) else None
