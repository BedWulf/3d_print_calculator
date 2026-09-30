"""Модели данных (таблицы БД) для калькулятора цены 3D-печати.

Каждая модель соответствует таблице SQLite и имеет:
    - поля, соответствующие колонкам;
    - методы to_row() / from_row() для сериализации в SQL-запросы.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class Printer:
    """Принтер (вкладка 'Принтеры').

    Параметры нужны для расчёта:
        electricity_kwh_per_hour -- потребление электроэнергии, кВт*ч за час печати;
        depreciation_rub_per_hour -- амортизация, руб. за час наработки (уже рассчитанная
            стоимость износа принтера за час работы);
        power_rub_per_kwh может храниться глобально в настройках, но у принтера можно
            задать собственное значение (None = использовать общее).
    """

    id: int | None = None
    name: str = ""
    electricity_kwh_per_hour: float = 0.0     # кВт*ч
    depreciation_rub_per_hour: float = 0.0    # руб./час
    bed_x_mm: float = 300.0                   # размер печатной платформы, мм (этап 2)
    bed_y_mm: float = 300.0
    bed_z_mm: float = 300.0                   # высота (Z) — справочно
    note: str = ""

    @property
    def bed_size_str(self) -> str:
        return f"{self.bed_x_mm:g} × {self.bed_y_mm:g} × {self.bed_z_mm:g} мм"

    def to_row(self) -> dict:
        return asdict(self)


@dataclass
class Material:
    """Материал (вкладка 'Материалы').

    density_g_cm3   -- плотность, г/см3 (для пересчёта объёма в массу, если понадобится);
    spool_weight_kg -- масса катушки: допускается 0.5 или 1.0 кг;
    price_rub       -- цена за катушку;
    price_per_gram  -- вычисляемая величина: цена грамма материала.
    """

    SPOOL_WEIGHTS_KG = (0.5, 1.0)

    id: int | None = None
    name: str = ""
    density_g_cm3: float = 1.0
    spool_weight_kg: float = 1.0
    price_rub: float = 0.0
    note: str = ""

    @property
    def price_per_gram(self) -> float:
        if self.spool_weight_kg <= 0:
            return 0.0
        return self.price_rub / (self.spool_weight_kg * 1000.0)

    def to_row(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Consumable:
    """Расходный материал (вкладка 'Расходные материалы').

    kind -- тип расхода: napkin (салфетки), lubricant (смазка), nozzle (сопло), glue (клей);
    consumption -- норма расхода на одну деталь (шт., мл, % использования ресурса);
    price_rub -- цена за единицу.
    """

    KIND_NAPKIN = "napkin"
    KIND_LUBRICANT = "lubricant"
    KIND_NOZZLE = "nozzle"
    KIND_GLUE = "glue"

    KINDS = (KIND_NAPKIN, KIND_LUBRICANT, KIND_NOZZLE, KIND_GLUE)
    KIND_LABELS = {
        KIND_NAPKIN: "Салфетки (уборка стола)",
        KIND_LUBRICANT: "Смазка для принтера",
        KIND_NOZZLE: "Сопло",
        KIND_GLUE: "Клей",
    }

    id: int | None = None
    kind: str = KIND_NAPKIN
    name: str = ""
    unit: str = "шт."
    consumption_per_part: float = 1.0
    price_rub: float = 0.0
    note: str = ""

    def to_row(self) -> dict:
        return asdict(self)


@dataclass
class Settings:
    """Глобальные настройки расчёта (ключ-значение в таблице settings)."""

    electricity_price_rub_per_kwh: float = 5.0   # тариф за электроэнергию
    labor_rate_rub_per_hour: float = 0.0         # (зарезервировано) стоимость часа работы оператора
    markup_percent: float = 0.0                  # (зарезервировано) наценка
    work_start: str = "07:30"                    # начало рабочего окна (этап 2)
    work_end: str = "16:15"                      # конец рабочего окна; ночь — остальное время
    pack_gap_mm: float = 1.0                     # зазор между деталями на платформе


@dataclass
class PartItem:
    """Позиция деталей для планирования печати (этап 2, вкладка 'Планировщик').

    shape: rect -- прямоугольный габарит (x,y); circle -- круглый (диаметр в x).
    time_h -- время печати ОДНОЙ детали из слайсера; qty -- количество таких деталей.
    """

    SHAPE_RECT = "rect"
    SHAPE_CIRCLE = "circle"
    SHAPE_LABELS = {SHAPE_RECT: "Прямоугольная", SHAPE_CIRCLE: "Круглая"}

    id: int | None = None
    name: str = ""
    shape: str = SHAPE_RECT
    size_x_mm: float = 0.0     # ширина / диаметр, мм
    size_y_mm: float = 0.0     # глубина, мм (для круга = диаметру)
    time_h: float = 0.0        # часов на одну деталь
    qty: int = 1
    note: str = ""

    def to_row(self) -> dict:
        return asdict(self)
