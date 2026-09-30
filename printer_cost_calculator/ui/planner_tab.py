"""Вкладка «Планировщик» (этап 2): столы, визуальная раскладка деталей и график
печати по дневному/ночному окнам.

Состав вкладки:
  * слева   — список позиций деталей (из БД) с кнопкой «➕» добавить на платформу;
  * по центру — вид платформы (вид сверху, как в слайсере Anycubic): стол принтера,
                ряды раскладки, зазор между деталями; кнопки управления;
  * справа  — окно выбора стола, зазор, сохранение/загрузка конфигураций;
  * снизу   — результат: сколько часов занимает партия, разбивка День/Ночь,
              непоместившиеся детали считаются отдельной конфигурацией.
"""

import json
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QFont
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QLineEdit, QGroupBox,
    QSplitter, QMessageBox, QAbstractItemView, QSizePolicy, QScrollArea,
)

from ..db.models import PartItem, Consumable
from ..logic.calculator import CalcInput, calculate
from ..logic.scheduler import (
    PackRequest, pack_bed, schedule, SchedItem, parse_hhmm, format_hhmm,
)
from . import theme


# ------------------------------------------------------------------ вид стола --
class BedView(QWidget):
    """Визуализация печатной платформы сверху вниз (только X/Y)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bed_x = 300.0
        self.bed_y = 300.0
        self.placed = []            # list[PlacedPart]
        self.gap_mm = 1.0
        self.unplaced_names = []
        self.setMinimumSize(340, 340)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(self, bed_x, bed_y, placed, gap_mm, unplaced):
        self.bed_x, self.bed_y = bed_x, bed_y
        self.placed = placed
        self.gap_mm = gap_mm
        self.unplaced_names = unplaced
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        m = 26                                   # поля под подписи мм
        avail_w, avail_h = self.width() - 2 * m, self.height() - 2 * m
        if self.bed_x <= 0 or self.bed_y <= 0 or avail_w <= 0 or avail_h <= 0:
            return
        scale = min(avail_w / self.bed_x, avail_h / self.bed_y)
        ox = m + (avail_w - self.bed_x * scale) / 2
        oy = m + (avail_h - self.bed_y * scale) / 2

        # фон вокруг стола
        p.fillRect(self.rect(), QColor(theme.BG_DEEP))

        # сам стол
        table_rect = QRectF(ox, oy, self.bed_x * scale, self.bed_y * scale)
        p.setPen(QPen(QColor(theme.GOLD_DIM), 1.5))
        p.setBrush(QColor(theme.SURFACE))
        p.drawRect(table_rect)

        # сетка каждые 50 мм
        p.setPen(QPen(QColor(theme.BORDER), 0.5, Qt.DotLine))
        step = 50.0
        gx = step
        while gx < self.bed_x:
            p.drawLine(QRectF(ox + gx * scale, oy, 0.5, self.bed_y * scale))
            gx += step
        gy = step
        while gy < self.bed_y:
            p.drawLine(QRectF(ox, oy + gy * scale, self.bed_x * scale, 0.5))
            gy += step

        # детали (Y инвертируем: нули координат — в левом нижнем углу стола)
        pal = [theme.GOLD, "#a9746f", "#7f9b83", "#7d8aa8", "#c0a37e", "#967fa6"]
        name_idx: dict[str, int] = {}
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, min(10.0, scale * 9)))
        for part in self.placed:
            key = part.name
            color = QColor(pal[name_idx.setdefault(key, len(name_idx) % len(pal))])
            w = part.w_mm * scale
            h = part.h_mm * scale
            x = ox + part.x_mm * scale
            y = oy + (self.bed_y - part.y_mm - (part.h_mm if part.shape == "rect"
                                               else part.w_mm)) * scale
            if part.shape == "circle":
                d = part.w_mm * scale
                p.setPen(QPen(color.darker(130), 1))
                p.setBrush(color.lighter(115))
                p.drawEllipse(QRectF(x, oy + (self.bed_y * scale) - (part.y_mm * scale) - d,
                                     d, d))
            else:
                p.setPen(QPen(color.darker(130), 1))
                p.setBrush(color.lighter(115))
                p.drawRect(QRectF(x, y, w, h))
            # подпись, если хватает места
            label = f"{key}"
            p.setFont(font)
            p.setPen(QPen(QColor(theme.BG_DEEP)))
            box = QRectF(x + 2, y + 2, max(w - 4, 0), max(h - 4, 0))
            if box.width() > 24 and box.height() > 12:
                p.drawText(box, Qt.AlignCenter | Qt.TextWordWrap, label)

        # размеры стола
        p.setPen(QPen(QColor(theme.GOLD_SOFT)))
        fm = p.fontMetrics()
        p.drawText(int(table_rect.center().x() - fm.horizontalAdvance("X") / 2),
                   int(oy - 8), f"{self.bed_x:g} мм")
        side = f"{self.bed_y:g}"
        p.save()
        p.translate(ox - 10, table_rect.center().y())
        p.rotate(-90)
        p.drawText(0, 0, side + " мм")
        p.restore()

        # легенда имён
        ly = oy + self.bed_y * scale + 12
        p.setPen(QPen(QColor(theme.TEXT)))
        small = QFont(self.font()); small.setPointSize(8); p.setFont(small)
        lx = ox
        for name, idx in name_idx.items():
            c = QColor(pal[idx % len(pal)])
            p.setBrush(c.lighter(115)); p.setPen(QPen(c.darker(130)))
            p.drawRect(QRectF(lx, ly, 10, 10))
            p.setPen(QPen(QColor(theme.TEXT)))
            p.drawText(int(lx + 14), int(ly + 9), name)
            lx += 24 + fm.horizontalAdvance(name)
            if lx > self.width() - 60:
                break

        if self.unplaced_names:
            p.setPen(QPen(QColor(theme.DANGER)))
            big = QFont(self.font()); big.setBold(True); p.setFont(big)
            p.drawText(m + 4, int(oy + 16),
                       f"Не влезло: {len(self.unplaced_names)} шт.")


# ---------------------------------------------------------------------- вкладка --
class PlannerTab(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.parts: list[PartItem] = []
        self._last_pack = None
        self._last_schedule = None

        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # ------------------------- левая колонка: список позиций ----------------
        left = QVBoxLayout()
        t = QLabel("Позиции деталей"); t.setProperty("role", "accent")
        left.addWidget(t)
        self.listw = QListWidget()
        self.listw.setSelectionMode(QAbstractItemView.SingleSelection)
        left.addWidget(self.listw, 1)
        btns = QHBoxLayout()
        add = QPushButton("Новая позиция"); add.clicked.connect(self._add_part)
        edit = QPushButton("Изменить");     edit.clicked.connect(self._edit_part)
        dele = QPushButton("Удалить");      dele.setObjectName("danger")
        dele.clicked.connect(self._delete_part)
        btns.addWidget(add); btns.addWidget(edit); btns.addWidget(dele)
        left.addLayout(btns)
        host_l = QWidget(); host_l.setLayout(left)
        splitter.addWidget(host_l)

        # ------------------------- центр: вид платформы --------------------------
        center = QVBoxLayout()
        self.bed_view = BedView()
        center.addWidget(self.bed_view, 1)
        row = QHBoxLayout()
        self.b_pack = QPushButton("РАСКЛАСТЬ НА СТОЛ")
        self.b_pack.setObjectName("default")
        self.b_pack.clicked.connect(self._pack)
        self.b_clear = QPushButton("Очистить стол")
        self.b_clear.clicked.connect(self._clear_bed)
        row.addWidget(self.b_pack); row.addWidget(self.b_clear)
        row.addStretch(1)
        row.addWidget(QLabel("Сохранённые конфигурации:"))
        self.c_saved = QComboBox(); self.c_saved.setMinimumWidth(160)
        row.addWidget(self.c_saved)
        load_b = QPushButton("Загрузить"); load_b.clicked.connect(self._load_config)
        del_b = QPushButton("Удалить"); del_b.setObjectName("danger")
        del_b.clicked.connect(self._delete_config)
        row.addWidget(load_b); row.addWidget(del_b)
        center.addLayout(row)
        host_c = QWidget(); host_c.setLayout(center)
        splitter.addWidget(host_c)

        # ------------------------- правая колонка: параметры ---------------------
        right = QVBoxLayout()
        box = QGroupBox("Параметры стола и времени")
        form = QFormLayout(box)
        self.c_printer = QComboBox()
        form.addRow("Стол (принтер):", self.c_printer)
        self.l_bed_size = QLabel("—"); self.l_bed_size.setProperty("role", "muted")
        form.addRow("Размер платформы:", self.l_bed_size)
        self.e_gap = QLineEdit(str(self.repo.get_settings().pack_gap_mm))
        form.addRow("Зазор между деталями, мм:", self.e_gap)
        self.e_start = QLineEdit(self.repo.get_settings().work_start)
        self.e_end = QLineEdit(self.repo.get_settings().work_end)
        form.addRow("Рабочее время с:", self.e_start)
        form.addRow("до:", self.e_end)
        self.l_night = QLabel("")
        self.l_night.setProperty("role", "muted")
        form.addRow("Автоматически:", self.l_night)
        save_cfg = QPushButton("Сохранить конфигурацию стола")
        save_cfg.clicked.connect(self._save_config)
        form.addRow(save_cfg)
        right.addWidget(box)

        calc_box = QGroupBox("Расчёт цены партии (по данным слайсинга)")
        cf = QFormLayout(calc_box)
        self.c_material = QComboBox()
        cf.addRow("Материал изделия:", self.c_material)
        self.e_mass = QLineEdit(); cf.addRow("Масса 1 детали, г:", self.e_mass)
        self.b_calc = QPushButton("РАССЧИТАТЬ ЦЕНУ ПАРТИИ")
        self.b_calc.clicked.connect(self._calc_price)
        cf.addRow(self.b_calc)
        right.addWidget(calc_box)

        res_wrap = QVBoxLayout()
        rt = QLabel("График печати:")
        rt.setProperty("role", "accent")
        res_wrap.addWidget(rt)
        self.res = QTextDisplay()
        res_wrap.addWidget(self.res, 1)
        right.addLayout(res_wrap, 1)
        host_r = QWidget(); host_r.setLayout(right)
        splitter.addWidget(host_r)

        splitter.setSizes([260, 460, 300])
        root.addWidget(QLabel(
            "Правило: длинные/крупные детали уходят в ночное окно (их не нужно "
            "снимать сразу), короткие — в дневное. Ночное окно рассчитывается "
            "автоматически: 24 ч минус ваше рабочее время."), role="muted")

        self.reload_sources()
        self._update_night_label()
        self.e_start.textChanged.connect(self._update_night_label)
        self.e_end.textChanged.connect(self._update_night_label)
        self.c_printer.currentIndexChanged.connect(self._on_printer_changed)

    # ------------------------------------------------------------------ data ---
    def reload_sources(self):
        keep_p = self.c_printer.currentData()
        keep_m = self.c_material.currentData()
        self.printers = self.repo.list_printers()
        self.materials = self.repo.list_materials()
        self.parts = self.repo.list_part_items()

        self.c_printer.clear()
        for pr in self.printers:
            self.c_printer.addItem(pr.name, pr.id)
        if keep_p is not None:
            i = self.c_printer.findData(keep_p)
            if i >= 0:
                self.c_printer.setCurrentIndex(i)

        self.c_material.clear()
        for m in self.materials:
            self.c_material.addItem(m.name, m.id)
        if keep_m is not None:
            i = self.c_material.findData(keep_m)
            if i >= 0:
                self.c_material.setCurrentIndex(i)

        sel_name = None
        cur = self.listw.currentItem()
        if cur:
            sel_name = cur.data(Qt.UserRole)
        self.listw.clear()
        for it in self.parts:
            shape = "◯" if it.shape == PartItem.SHAPE_CIRCLE else "▭"
            item = QListWidgetItem(
                f"{shape} {it.name}  {it.size_x_mm:g}×{it.size_y_mm:g} мм · "
                f"{it.time_h:g} ч · {it.qty} шт.")
            item.setData(Qt.UserRole, it.id)
            self.listw.addItem(item)
            self._append_add_button(it)
        if sel_name is not None:
            for i in range(self.listw.count()):
                if self.listw.item(i).data(Qt.UserRole) == sel_name:
                    self.listw.setCurrentRow(i)
                    break
        self._refresh_saved_list()
        self._on_printer_changed()

    def _append_add_button(self, part: PartItem):
        """К кастомному элементу списка прицепляем маленькую кнопку '➕'."""
        pass  # реализовано через ItemWidget ниже

    def _current_part(self) -> PartItem | None:
        item = self.listw.currentItem()
        if not item:
            return None
        pid = item.data(Qt.UserRole)
        return next((p for p in self.parts if p.id == pid), None)

    # ------------------------------------------------------------- positions ---
    def _add_part(self):
        dlg = PartDialog(self)
        if dlg.exec_() == dlg.Accepted and dlg.result_item:
            self.repo.add_part_item(dlg.result_item)
            self.reload_sources()

    def _edit_part(self):
        p = self._current_part()
        if not p:
            QMessageBox.information(self, "Позиции", "Выберите позицию в списке.")
            return
        dlg = PartDialog(self, existing=p)
        if dlg.exec_() == dlg.Accepted and dlg.result_item:
            self.repo.update_part_item(dlg.result_item)
            self.reload_sources()

    def _delete_part(self):
        p = self._current_part()
        if p and QMessageBox.question(
                self, "Удалить", f"Удалить позицию «{p.name}»?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.repo.delete_part_item(p.id)
            self.reload_sources()

    # ----------------------------------------------------------------- pack ----
    def _bed(self):
        pr = next((p for p in self.printers if p.id == self.c_printer.currentData()),
                  None)
        return pr

    def _on_printer_changed(self):
        pr = self._bed()
        if pr:
            self.l_bed_size.setText(f"{pr.bed_x_mm:g} × {pr.bed_y_mm:g} × "
                                    f"{pr.bed_z_mm:g} мм")
            self.bed_view.set_state(
                pr.bed_x_mm, pr.bed_y_mm,
                self._last_pack.placed if self._last_pack else [],
                self._gap(), self._last_pack.unplaced if self._last_pack else [])

    def _gap(self) -> float:
        try:
            return max(0.0, float(self.e_gap.text().replace(",", ".")))
        except ValueError:
            return 1.0

    def _requests(self) -> list[PackRequest]:
        reqs = []
        for it in self.parts:
            if it.qty > 0 and it.size_x_mm > 0:
                reqs.append(PackRequest(it.name, it.shape, it.size_x_mm,
                                        it.size_y_mm, it.qty))
        return reqs

    def _pack(self):
        pr = self._bed()
        if not pr:
            QMessageBox.warning(self, "Стол", "Выберите принтер (стол).")
            return
        reqs = self._requests()
        if not reqs:
            QMessageBox.warning(self, "Позиции",
                                "Добавьте позиции деталей (кнопка «Новая позиция»).")
            return
        res = pack_bed(reqs, pr.bed_x_mm, pr.bed_y_mm, gap_mm=self._gap())
        self._last_pack = res
        self.bed_view.set_state(pr.bed_x_mm, pr.bed_y_mm, res.placed,
                                self._gap(), res.unplaced)
        area_pct = (res.used_area_mm2 / (pr.bed_x_mm * pr.bed_y_mm) * 100
                    if pr.bed_x_mm * pr.bed_y_mm else 0)
        msg = (f"Размещено {len(res.placed)} шт. из "
               f"{sum(r.qty for r in reqs)} · заполнение стола ≈ {area_pct:.0f}%")
        if res.unplaced:
            msg += f"\nНе влезло: {len(res.unplaced)} шт. — посчитаны отдельной " \
                   f"конфигурацией (см. график)."
        self.res.set_text(msg)

    def _clear_bed(self):
        self._last_pack = None
        pr = self._bed()
        if pr:
            self.bed_view.set_state(pr.bed_x_mm, pr.bed_y_mm, [], self._gap(), [])
        self.res.set_text("Стол очищен.")

    # ------------------------------------------------------------ schedule -----
    def _update_night_label(self):
        try:
            s = parse_hhmm(self.e_start.text())
            e = parse_hhmm(self.e_end.text())
        except ValueError:
            self.l_night.setText("нужно ЧЧ:ММ")
            return
        day_min = (e - s) % 1440 or 1440
        night_min = 1440 - day_min
        self.l_night.setText(
            f"ночь {format_hhmm(e)} → {format_hhmm(s)} "
            f"({night_min / 60:.1f} ч; день {day_min / 60:.1f} ч)")

    def _schedule_text(self) -> str:
        items = []
        for it in self.parts:
            for _n in range(max(0, it.qty)):
                items.append(SchedItem(it.name, it.time_h))
        sched = schedule(items, self.e_start.text(), self.e_end.text())
        self._last_schedule = sched
        lines = [f"Всего время партии: {sched.total_time_h:.1f} ч", ""]
        for plan in (sched.day, sched.night):
            lines.append(f"{plan.label}  ({plan.window}, {plan.capacity_h:.1f} ч):")
            if plan.items:
                agg: dict[str, list[float]] = {}
                for nm, t in plan.items:
                    a = agg.setdefault(nm, [0, 0])
                    a[0] += t
                    a[1] += 1
                for nm, (t, cnt) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
                    lines.append(f"   • {nm} ×{cnt} — {t:.1f} ч")
            else:
                lines.append("   — пусто")
            used = plan.load_h
            lines.append(f"   Загрузка окна: {used:.1f} ч из {plan.capacity_h:.1f} ч"
                         + ("  ⚠ перенос на след. сутки" if plan.overflow_h else ""))
            lines.append("")
        for err in sched.errors:
            lines.append(f"⚠ {err}")
        if self._last_pack and self._last_pack.unplaced:
            lines.append("")
            lines.append("Отдельная конфигурация (не влезло на текущий стол):")
            agg: dict[str, int] = {}
            for nm in self._last_pack.unplaced:
                agg[nm] = agg.get(nm, 0) + 1
            for nm, cnt in sorted(agg.items()):
                lines.append(f"   • {nm} — {cnt} шт.")
        return "\n".join(lines)

    def _calc_price(self):
        """Цена всей партии: материал × количество + машинное время по графику."""
        pr = self._bed()
        mat = next((m for m in self.materials
                    if m.id == self.c_material.currentData()), None)
        total_qty = sum(max(0, it.qty) for it in self.parts)
        if not (pr and mat and total_qty):
            QMessageBox.warning(self, "Расчёт",
                                "Нужны: стол-принтер, материал и хотя бы одна позиция.")
            return
        mass = _f(self.e_mass)
        if mass <= 0:
            QMessageBox.warning(self, "Расчёт", "Укажите массу одной детали.")
            return
        sched = self._last_schedule or schedule(
            [SchedItem(it.name, it.time_h) for it in self.parts
             for _n in range(max(0, it.qty))],
            self.e_start.text(), self.e_end.text())
        hours = sched.total_time_h
        inp = CalcInput(
            printer=pr, print_time_hours=hours, part_mass_g=mass,
            part_material=mat, use_supports=False, support_mass_g=0,
            support_material=None, quantity=total_qty,
            selected_consumables=self.repo.list_consumables(),
            settings=self.repo.get_settings(), time_is_per_part=False)
        res = calculate(inp)
        if res.errors:
            QMessageBox.warning(self, "Проверьте данные", "\n".join(res.errors))
            return
        text = self._schedule_text()
        text += ("\n\nЦЕНА ПАРТИИ (машина отработает %.1f ч, всего %d шт.):"
                 % (hours, total_qty))
        for s in res.steps:
            text += f"\n   {s.title}: {s.value_rub:.2f} ₽"
        text += (f"\n   Итого за деталь: {res.per_part_total:.2f} ₽"
                 f"\n   Итого за партию: {res.batch_total:.2f} ₽")
        self.res.set_text(text)

    # -------------------------------------------------------- saved configs ----
    def _configs_dir(self) -> Path:
        d = Path.home() / ".price3dcalc" / "configs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _refresh_saved_list(self):
        self.c_saved.clear()
        for f in sorted(self._configs_dir().glob("*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            self.c_saved.addItem(f.stem, str(f))

    def _save_config(self):
        if not self._last_pack:
            QMessageBox.information(self, "Конфигурация",
                                    "Сначала выполните раскладку («Рассчитать»/"
                                    "«РАСКЛАСТЬ НА СТОЛ»).")
            return
        name = datetime.now().strftime("config_%Y%m%d_%H%M%S")
        data = {
            "printer_id": self.c_printer.currentData(),
            "gap_mm": self._gap(),
            "work_start": self.e_start.text(),
            "work_end": self.e_end.text(),
            "placed": [[p.name, p.x_mm, p.y_mm, p.w_mm, p.h_mm, p.shape, p.index]
                       for p in self._last_pack.placed],
            "unplaced": self._last_pack.unplaced,
        }
        path = self._configs_dir() / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self._refresh_saved_list()
        self.res.set_text(f"Конфигурация сохранена: {path}")

    def _load_config(self):
        fp = self.c_saved.currentData()
        if not fp:
            return
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
        from ..logic.scheduler import PlacedPart, PackResult
        res = PackResult()
        for row in data["placed"]:
            res.placed.append(PlacedPart(*row))
        res.unplaced = data.get("unplaced", [])
        self._last_pack = res
        self.e_gap.setText(str(data.get("gap_mm", 1.0)))
        self.e_start.setText(data.get("work_start", "07:30"))
        self.e_end.setText(data.get("work_end", "16:15"))
        pid = data.get("printer_id")
        i = self.c_printer.findData(pid)
        if i >= 0:
            self.c_printer.setCurrentIndex(i)
        pr = self._bed()
        if pr:
            self.bed_view.set_state(pr.bed_x_mm, pr.bed_y_mm, res.placed,
                                    self._gap(), res.unplaced)
        self.res.set_text(f"Загружена конфигурация {Path(fp).stem}: "
                          f"{len(res.placed)} шт. на столе, "
                          f"{len(res.unplaced)} вне стола.")

    def _delete_config(self):
        fp = self.c_saved.currentData()
        if fp and QMessageBox.question(self, "Удалить", f"Удалить {Path(fp).name}?",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No) == QMessageBox.Yes:
            Path(fp).unlink(missing_ok=True)
            self._refresh_saved_list()


class QTextDisplay(QScrollArea):
    """Многострочный читаемый вывод результата (тёмная тема, без редактирования)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lbl = QLabel("—")
        self.lbl.setWordWrap(True)
        self.lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl.setStyleSheet(f"color: {theme.TEXT}; padding: 8px;")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.StyledPanel)
        self.setWidget(self.lbl)

    def set_text(self, text: str):
        self.lbl.setText(text.replace("\n", "<br>").replace(" ", "&nbsp;")
                         if "<" not in text else text)


def _f(line: QLineEdit, default: float = 0.0) -> float:
    try:
        return float(line.text().strip().replace(",", ".") or default)
    except ValueError:
        return default


# ---------------------------------------------------------------- диалог позиции --
from PyQt5.QtWidgets import QDialog, QDialogButtonBox  # noqa: E402


class PartDialog(QDialog):
    """Карточка позиции детали: название, форма, габарит, время, количество."""

    def __init__(self, parent=None, existing: PartItem | None = None):
        super().__init__(parent)
        self.setWindowTitle("Позиция детали")
        self.result_item: PartItem | None = None
        self._orig = existing or PartItem()
        form = QFormLayout(self)
        self.e_name = QLineEdit(self._orig.name)
        self.c_shape = QComboBox()
        for val, lab in PartItem.SHAPE_LABELS.items():
            self.c_shape.addItem(lab, val)
        i = self.c_shape.findData(self._orig.shape)
        if i >= 0:
            self.c_shape.setCurrentIndex(i)
        self.e_x = QLineEdit(str(self._orig.size_x_mm or ""))
        self.e_y = QLineEdit(str(self._orig.size_y_mm or ""))
        self.e_t = QLineEdit(str(self._orig.time_h or ""))
        self.e_q = QLineEdit(str(self._orig.qty or 1))
        form.addRow("Название:", self.e_name)
        form.addRow("Форма:", self.c_shape)
        form.addRow("Габарит X (для круга — диаметр), мм:", self.e_x)
        form.addRow("Габарит Y, мм:", self.e_y)
        form.addRow("Время печати 1 шт., ч:", self.e_t)
        form.addRow("Количество, шт.:", self.e_q)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _ok(self):
        name = self.e_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Позиция", "Укажите название.")
            return
        it = PartItem(
            id=self._orig.id, name=name,
            shape=self.c_shape.currentData(),
            size_x_mm=_f(self.e_x), size_y_mm=_f(self.e_y),
            time_h=_f(self.e_t), qty=int(_f(self.e_q, 1) or 1),
            note=self._orig.note)
        if it.shape == PartItem.SHAPE_CIRCLE:
            it.size_y_mm = it.size_x_mm
        if it.size_x_mm <= 0:
            QMessageBox.warning(self, "Позиция", "Габарит должен быть больше нуля.")
            return
        self.result_item = it
        self.accept()
