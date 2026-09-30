"""Чистая бизнес-логика расчёта цены 3D-печати (без зависимостей от UI и БД).

Входные данные расчёта -- CalcInput, результат -- CalcResult со списком
подробных шагов ("ход расчета") и итогами для одной детали и всей партии.
"""

from dataclasses import dataclass, field

from ..db.models import Printer, Material, Consumable, Settings


@dataclass
class CalcInput:
    printer: Printer
    print_time_hours: float            # время печати одной детали (или партии -- см. comment)
    part_mass_g: float                 # масса изделия, г
    part_material: Material            # материал изделия
    use_supports: bool                 # флажок "есть поддержки"
    support_mass_g: float = 0.0        # масса поддержек, г (учитывается только при use_supports)
    support_material: Material | None = None  # материал поддержек (может отличаться)
    quantity: int = 1                  # количество деталей в партии
    selected_consumables: list[Consumable] = field(default_factory=list)  # отмеченные флажками
    settings: Settings = field(default_factory=Settings)
    time_is_per_part: bool = True      # True: print_time_hours указан на 1 деталь;
                                       # False: общее время на всю партию


@dataclass
class CalcStep:
    """Один шаг хода расчёта: формула + числовое пояснение."""
    title: str
    formula: str
    value_rub: float
    comment: str = ""


@dataclass
class CalcResult:
    steps: list[CalcStep] = field(default_factory=list)
    per_part_total: float = 0.0     # себестоимость одной детали
    batch_total: float = 0.0        # себестоимость всей партии
    errors: list[str] = field(default_factory=list)


def _fmt(v: float) -> str:
    return f"{v:,.4f}".replace(",", " ") if abs(v) < 1 else f"{v:,.2f}".replace(",", " ")


def calculate(inp: CalcInput) -> CalcResult:
    res = CalcResult()

    # --- проверки входных данных ------------------------------------------------
    if inp.print_time_hours <= 0:
        res.errors.append("Укажите время печати (> 0).")
    if inp.part_mass_g <= 0:
        res.errors.append("Укажите массу изделия (> 0).")
    if inp.quantity < 1:
        res.errors.append("Количество деталей должно быть >= 1.")
    if inp.use_supports and inp.support_mass_g <= 0:
        res.errors.append("Отмечены поддержки, но их масса не указана.")
    if inp.use_supports and inp.support_material is None:
        res.errors.append("Выберите материал поддержек.")
    if res.errors:
        return res

    qty = inp.quantity
    hours_per_part = (inp.print_time_hours if inp.time_is_per_part
                      else inp.print_time_hours / qty)
    price_kwh = inp.settings.electricity_price_rub_per_kwh

    # --- 1. Электроэнергия -------------------------------------------------------
    elec_cost = hours_per_part * inp.printer.electricity_kwh_per_hour * price_kwh
    res.steps.append(CalcStep(
        title="Электроэнергия",
        formula=(f"{_fmt(hours_per_part)} ч × {_fmt(inp.printer.electricity_kwh_per_hour)} кВт·ч/ч"
                 f" × {_fmt(price_kwh)} ₽/кВт·ч"),
        value_rub=elec_cost,
        comment=f"Принтер: {inp.printer.name}",
    ))

    # --- 2. Амортизация принтера --------------------------------------------------
    depr_cost = hours_per_part * inp.printer.depreciation_rub_per_hour
    res.steps.append(CalcStep(
        title="Амортизация принтера",
        formula=f"{_fmt(hours_per_part)} ч × {_fmt(inp.printer.depreciation_rub_per_hour)} ₽/ч",
        value_rub=depr_cost,
    ))

    # --- 3. Материал изделия ------------------------------------------------------
    part_mat_cost = inp.part_mass_g * inp.part_material.price_per_gram
    res.steps.append(CalcStep(
        title="Материал изделия",
        formula=(f"{_fmt(inp.part_mass_g)} г × {_fmt(inp.part_material.price_per_gram)} ₽/г"
                 f" ({inp.part_material.name}, катушка {_fmt(inp.part_material.spool_weight_kg)} кг"
                 f" по {_fmt(inp.part_material.price_rub)} ₽)"),
        value_rub=part_mat_cost,
    ))

    # --- 4. Материал поддержек (только если флажок установлен) --------------------
    if inp.use_supports and inp.support_material is not None:
        sup_mat_cost = inp.support_mass_g * inp.support_material.price_per_gram
        res.steps.append(CalcStep(
            title="Материал поддержек",
            formula=(f"{_fmt(inp.support_mass_g)} г × {_fmt(inp.support_material.price_per_gram)} ₽/г"
                     f" ({inp.support_material.name})"),
            value_rub=sup_mat_cost,
        ))

    # --- 5. Расходные материалы ----------------------------------------------------
    for c in inp.selected_consumables:
        cost = c.consumption_per_part  # норма уже задана на одну деталь
        res.steps.append(CalcStep(
            title=f"Расходный материал: {c.name}",
            formula=(f"{_fmt(c.consumption_per_part)} {c.unit}/деталь"
                     f" × {_fmt(c.price_rub / max(c.consumption_per_part, 1e-9))} ₽/{c.unit}"
                     if c.consumption_per_part > 0 else "0"),
            value_rub=cost,
        ))

    # --- Итоги ---------------------------------------------------------------------
    res.per_part_total = sum(s.value_rub for s in res.steps)
    res.batch_total = res.per_part_total * qty
    return res
