"""Слой доступа к данным (SQLite).

Один файл-база `calculator.db` в корне проекта (путь можно переопределить).
API репозитория:
    - list/get/add/update/delete для Printer, Material, Consumable;
    - get_settings/save_settings для глобальных настроек.
"""

import sqlite3
from pathlib import Path

from .models import Printer, Material, Consumable, Settings

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "calculator.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS printers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    electricity_kwh_per_hour REAL NOT NULL DEFAULT 0,
    depreciation_rub_per_hour REAL NOT NULL DEFAULT 0,
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


class Repository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------------ printers
    def list_printers(self) -> list[Printer]:
        rows = self.conn.execute("SELECT * FROM printers ORDER BY name").fetchall()
        return [Printer(**dict(r)) for r in rows]

    def add_printer(self, p: Printer) -> int:
        cur = self.conn.execute(
            "INSERT INTO printers(name, electricity_kwh_per_hour, depreciation_rub_per_hour, note)"
            " VALUES (?,?,?,?)",
            (p.name, p.electricity_kwh_per_hour, p.depreciation_rub_per_hour, p.note),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_printer(self, p: Printer) -> None:
        self.conn.execute(
            "UPDATE printers SET name=?, electricity_kwh_per_hour=?,"
            " depreciation_rub_per_hour=?, note=? WHERE id=?",
            (p.name, p.electricity_kwh_per_hour, p.depreciation_rub_per_hour, p.note, p.id),
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
        return s

    def save_settings(self, s: Settings) -> None:
        pairs = {
            "electricity_price_rub_per_kwh": str(s.electricity_price_rub_per_kwh),
            "labor_rate_rub_per_hour": str(s.labor_rate_rub_per_hour),
            "markup_percent": str(s.markup_percent),
        }
        self.conn.executemany(
            "INSERT INTO settings(key, value) VALUES (?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            list(pairs.items()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
