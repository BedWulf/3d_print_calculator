"""Слой доступа к данным (SQLite).

Один файл-база `calculator.db` в корне проекта (путь можно переопределить).
API репозитория:
    - list/get/add/update/delete для Printer, Material, Consumable;
    - get_settings/save_settings для глобальных настроек.
"""

import sqlite3
from pathlib import Path

from .models import Printer, Material, Consumable, Settings, PartItem

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "calculator.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS printers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    electricity_kwh_per_hour REAL NOT NULL DEFAULT 0,
    depreciation_rub_per_hour REAL NOT NULL DEFAULT 0,
    bed_x_mm REAL NOT NULL DEFAULT 300,
    bed_y_mm REAL NOT NULL DEFAULT 300,
    bed_z_mm REAL NOT NULL DEFAULT 300,
    note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS part_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    shape TEXT NOT NULL DEFAULT 'rect',
    size_x_mm REAL NOT NULL DEFAULT 0,
    size_y_mm REAL NOT NULL DEFAULT 0,
    time_h REAL NOT NULL DEFAULT 0,
    qty INTEGER NOT NULL DEFAULT 1,
    note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    density_g_cm3 REAL NOT NULL DEFAULT 1,
    spool_weight_kg REAL NOT NULL DEFAULT 1,
    price_rub REAL NOT NULL DEFAULT 0,
    note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS consumables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT DEFAULT 'шт.',
    consumption_per_part REAL NOT NULL DEFAULT 1,
    price_rub REAL NOT NULL DEFAULT 0,
    note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def default_printers() -> list[Printer]:
    """Стартовые принтеры. Данные -- по открытым источникам/официальным сайтам
    (Raise3D: raise3d.com; Anycubic: anycubic.com), округлены. Все параметры
    можно изменить на вкладке 'Принтеры'."""
    return [
        Printer(
            name="Raise3D Pro3 (FFF)",
            electricity_kwh_per_hour=0.35,   # нагрев ~260C/стол ~100C, среднее за печать
            depreciation_rub_per_hour=17.4,  # ~195000 руб / 15000 ч ресурса (≈2 года 24/7)
            note="Цена ~195 000 руб (RFQ у дилеров). Ресурс до амортизации: 15 000 ч — правьте под себя.",
        ),
        Printer(
            name="Anycubic Kobra S1",
            electricity_kwh_per_hour=0.2,    # макс. мощность ~600 Вт, среднее при печати ~200 Вт
            depreciation_rub_per_hour=3.0,   # ~36 000 руб / 12 000 ч
            note="Цена ~36 000 руб (розница РФ). Ресурс 12 000 ч — правьте под себя.",
        ),
    ]


def default_materials() -> list[Material]:
    return [
        Material(
            name="PetG черный",
            density_g_cm3=1.27,       # типичная плотность PETG ~1.27 г/см3
            spool_weight_kg=1.0,
            price_rub=1800.0,         # задано пользователем
            note="1800 руб/кг — как указал пользователь. Цена грамма считается автоматически.",
        ),
    ]


def default_consumables() -> list[Consumable]:
    """Расходники: consumption_per_part -- доля расхода НА ОДНУ деталь,
    price_rub -- цена за целую единицу/упаковку. Значения типовые, правятся
    на вкладке 'Расходные материалы'."""
    return [
        Consumable(kind=Consumable.KIND_NAPKIN, name="Салфетки безворсовые (уборка стола)",
                   unit="шт.", consumption_per_part=0.05, price_rub=15.0,
                   note="~1 салфетка на 20 деталей"),
        Consumable(kind=Consumable.KIND_LUBRICANT, name="Смазка для принтера (PTFE/литиевая)",
                   unit="мл", consumption_per_part=0.01, price_rub=350.0,
                   note="Туба ~30 мл на ~3000 деталей — доля на деталь 1/3000*30=0.01 мл")
        ,
        Consumable(kind=Consumable.KIND_NOZZLE, name="Сопло 0.4 мм латунное",
                   unit="ч", consumption_per_part=0.005, price_rub=200.0,
                   note="Ресурс сопла ~200 ч; за деталь 1 ч расходуется 1/200 = 0.005 ресурса")
        ,
        Consumable(kind=Consumable.KIND_GLUE, name="Клей-стик для стола (PVP)",
                   unit="г", consumption_per_part=0.02, price_rub=250.0,
                   note="Стик ~50 г примерно на 10 сессий — корректируйте под расход"),
    ]


class Repository:
    def _migrate(self) -> None:
        """Бережно добавляет колонки, появившиеся в новых версиях приложения."""
        tables = {r["name"] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "printers" not in tables:
            return  # новая база — схема создаётся в __init__ после миграции
        cols = {r["name"] for r in
                self.conn.execute("PRAGMA table_info(printers)").fetchall()}
        for col, decl in (("bed_x_mm", "REAL NOT NULL DEFAULT 300"),
                          ("bed_y_mm", "REAL NOT NULL DEFAULT 300"),
                          ("bed_z_mm", "REAL NOT NULL DEFAULT 300")):
            if col not in cols:
                self.conn.execute(f"ALTER TABLE printers ADD COLUMN {col} {decl}")
        self.conn.commit()

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, seed_defaults: bool = True):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)   # сначала схема (создаёт таблицы)
        self._migrate()                     # потом догоняем недостающие колонки
        self.conn.commit()
        if seed_defaults:
            self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Заполняет БД стартовыми данными, только если соответствующие
        таблицы пусты. После этого всё редактируется через вкладки приложения."""
        if self.conn.execute("SELECT COUNT(*) FROM printers").fetchone()[0] == 0:
            for p in default_printers():
                self.add_printer(p)
        if self.conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0:
            for m in default_materials():
                self.add_material(m)
        if self.conn.execute("SELECT COUNT(*) FROM consumables").fetchone()[0] == 0:
            for c in default_consumables():
                self.add_consumable(c)

    # ------------------------------------------------------------------ printers
    def list_printers(self) -> list[Printer]:
        rows = self.conn.execute("SELECT * FROM printers ORDER BY name").fetchall()
        return [Printer(**dict(r)) for r in rows]

    def add_printer(self, p: Printer) -> int:
        cur = self.conn.execute(
            "INSERT INTO printers(name, electricity_kwh_per_hour, depreciation_rub_per_hour,"
            " bed_x_mm, bed_y_mm, bed_z_mm, note) VALUES (?,?,?,?,?,?,?)",
            (p.name, p.electricity_kwh_per_hour, p.depreciation_rub_per_hour,
             p.bed_x_mm, p.bed_y_mm, p.bed_z_mm, p.note),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_printer(self, p: Printer) -> None:
        self.conn.execute(
            "UPDATE printers SET name=?, electricity_kwh_per_hour=?,"
            " depreciation_rub_per_hour=?, bed_x_mm=?, bed_y_mm=?, bed_z_mm=?, note=?"
            " WHERE id=?",
            (p.name, p.electricity_kwh_per_hour, p.depreciation_rub_per_hour,
             p.bed_x_mm, p.bed_y_mm, p.bed_z_mm, p.note, p.id),
        )
        self.conn.commit()

    def delete_printer(self, printer_id: int) -> None:
        self.conn.execute("DELETE FROM printers WHERE id=?", (printer_id,))
        self.conn.commit()

    # ----------------------------------------------------------------- materials
    def list_materials(self) -> list[Material]:
        rows = self.conn.execute("SELECT * FROM materials ORDER BY name").fetchall()
        return [Material(**dict(r)) for r in rows]

    def add_material(self, m: Material) -> int:
        cur = self.conn.execute(
            "INSERT INTO materials(name, density_g_cm3, spool_weight_kg, price_rub, note)"
            " VALUES (?,?,?,?,?)",
            (m.name, m.density_g_cm3, m.spool_weight_kg, m.price_rub, m.note),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_material(self, m: Material) -> None:
        self.conn.execute(
            "UPDATE materials SET name=?, density_g_cm3=?, spool_weight_kg=?,"
            " price_rub=?, note=? WHERE id=?",
            (m.name, m.density_g_cm3, m.spool_weight_kg, m.price_rub, m.note, m.id),
        )
        self.conn.commit()

    def delete_material(self, material_id: int) -> None:
        self.conn.execute("DELETE FROM materials WHERE id=?", (material_id,))
        self.conn.commit()

    # --------------------------------------------------------------- consumables
    def list_consumables(self) -> list[Consumable]:
        rows = self.conn.execute("SELECT * FROM consumables ORDER BY kind, name").fetchall()
        return [Consumable(**dict(r)) for r in rows]

    def add_consumable(self, c: Consumable) -> int:
        cur = self.conn.execute(
            "INSERT INTO consumables(kind, name, unit, consumption_per_part, price_rub, note)"
            " VALUES (?,?,?,?,?,?)",
            (c.kind, c.name, c.unit, c.consumption_per_part, c.price_rub, c.note),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_consumable(self, c: Consumable) -> None:
        self.conn.execute(
            "UPDATE consumables SET kind=?, name=?, unit=?, consumption_per_part=?,"
            " price_rub=?, note=? WHERE id=?",
            (c.kind, c.name, c.unit, c.consumption_per_part, c.price_rub, c.note, c.id),
        )
        self.conn.commit()

    def delete_consumable(self, consumable_id: int) -> None:
        self.conn.execute("DELETE FROM consumables WHERE id=?", (consumable_id,))
        self.conn.commit()

    # --------------------------------------------------------------- part_items
    def list_part_items(self) -> list[PartItem]:
        rows = self.conn.execute("SELECT * FROM part_items ORDER BY name").fetchall()
        return [PartItem(**dict(r)) for r in rows]

    def add_part_item(self, it: PartItem) -> int:
        cur = self.conn.execute(
            "INSERT INTO part_items(name, shape, size_x_mm, size_y_mm, time_h, qty, note)"
            " VALUES (?,?,?,?,?,?,?)",
            (it.name, it.shape, it.size_x_mm, it.size_y_mm, it.time_h, it.qty, it.note),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_part_item(self, it: PartItem) -> None:
        self.conn.execute(
            "UPDATE part_items SET name=?, shape=?, size_x_mm=?, size_y_mm=?,"
            " time_h=?, qty=?, note=? WHERE id=?",
            (it.name, it.shape, it.size_x_mm, it.size_y_mm,
             it.time_h, it.qty, it.note, it.id),
        )
        self.conn.commit()

    def delete_part_item(self, item_id: int) -> None:
        self.conn.execute("DELETE FROM part_items WHERE id=?", (item_id,))
        self.conn.commit()

    # ------------------------------------------------------------------ settings
    def get_settings(self) -> Settings:
        s = Settings()
        rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        data = {r["key"]: r["value"] for r in rows}
        s.electricity_price_rub_per_kwh = float(data.get("electricity_price_rub_per_kwh",
                                                         s.electricity_price_rub_per_kwh))
        s.labor_rate_rub_per_hour = float(data.get("labor_rate_rub_per_hour",
                                                   s.labor_rate_rub_per_hour))
        s.markup_percent = float(data.get("markup_percent", s.markup_percent))
        s.work_start = data.get("work_start", s.work_start)
        s.work_end = data.get("work_end", s.work_end)
        s.pack_gap_mm = float(data.get("pack_gap_mm", s.pack_gap_mm))
        return s

    def save_settings(self, s: Settings) -> None:
        pairs = {
            "electricity_price_rub_per_kwh": str(s.electricity_price_rub_per_kwh),
            "labor_rate_rub_per_hour": str(s.labor_rate_rub_per_hour),
            "markup_percent": str(s.markup_percent),
            "work_start": s.work_start,
            "work_end": s.work_end,
            "pack_gap_mm": str(s.pack_gap_mm),
        }
        self.conn.executemany(
            "INSERT INTO settings(key, value) VALUES (?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            list(pairs.items()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
