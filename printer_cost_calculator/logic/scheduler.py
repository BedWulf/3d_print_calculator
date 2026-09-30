"""Логика этапа 2: рабочее время (день/ночь) и планирование партии деталей.

Два окна печати:
    * Дневное — задаётся пользователем (например, 07:30–16:15): детали нужно
      снимать со стола, поэтому оператор на месте;
    * Ночное — всё остальное время суток (рассчитывается автоматически:
      24 ч минус дневное окно). Сюда попадают длинные/большие детали.

Правило распределения (эвристика longest-processing-time):
    сначала заполняем ночное окно самыми ДОЛГИМИ деталями, остаток — в день.
Если суммарного времени суток не хватает — считаем дополнительные сутки
(партия печатается несколько дней подряд), лишние дни помечаются отдельно.

Никаких зависимостей от UI и БД — только чистые данные.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TimeWindow:
    """Окно работы принтера внутри одних суток."""
    start_min: int   # минуты от полуночи (0..1439)
    end_min: int     # минуты от полуночи; если end <= start — окно через полночь

    @property
    def duration_min(self) -> int:
        if self.end_min > self.start_min:
            return self.end_min - self.start_min
        return 1440 - self.start_min + self.end_min  # через полночь


def parse_hhmm(text: str) -> int:
    """'07:30' / '7:30' / '16.15' -> минуты от полуночи. ValueError при мусоре."""
    norm = text.strip().replace(".", ":")
    parts = norm.split(":")
    if len(parts) != 2:
        raise ValueError(f"Неверный формат времени: {text!r} (нужно ЧЧ:ММ)")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Время вне диапазона: {text!r}")
    return h * 60 + m


def format_hhmm(minutes: int) -> str:
    minutes %= 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def day_night_windows(work_start: str, work_end: str) -> tuple[TimeWindow, TimeWindow]:
    """Дневное окно из параметров пользователя; ночное — автоматический
    «остаток» суток (от конца дня до начала следующего рабочего утра)."""
    s = parse_hhmm(work_start)
    e = parse_hhmm(work_end)
    day = TimeWindow(s, e)
    night = TimeWindow(e, s)          # если e==s — «ночь» совпадает с сутками
    return day, night


# ---------------------------------------------------------------- packing ----

@dataclass
class PackRequest:
    name: str
    shape: str          # 'rect' | 'circle'
    size_x_mm: float
    size_y_mm: float
    qty: int


@dataclass
class PlacedPart:
    name: str
    x_mm: float
    y_mm: float
    w_mm: float         # занимаемая ширина (уже с зазором)
    h_mm: float
    shape: str
    index: int          # порядковый номер экземпляра (1..qty)


@dataclass
class PackResult:
    placed: list[PlacedPart] = field(default_factory=list)
    unplaced: list[str] = field(default_factory=list)   # "Имя (N шт.)"
    used_area_mm2: float = 0.0


def pack_bed(requests: list[PackRequest], bed_x: float, bed_y: float,
             gap_mm: float = 1.0, allow_rotation: bool = True,
             max_items: int = 800) -> PackResult:
    """Упаковка «сверху вниз» по рядам (shelf-packing) с зазором между деталями.

    Детали сортируются по высоте ряда; для круга занимает квадрат по диаметру.
    Это быстрый и предсказуемый алгоритм — качество близкое к ручному
    размещению, при этом результат всегда воспроизводим.
    """
    res = PackResult()
    # группируем одинаковые (имя, форма, габарит с зазором) -> количество
    counts: dict[tuple[str, str, float, float], int] = {}
    for r in requests:
        if r.size_x_mm <= 0 or r.qty <= 0:
            continue
        w = r.size_x_mm + gap_mm
        h = (r.size_x_mm if r.shape == "circle" else r.size_y_mm) + gap_mm
        key = (r.name, r.shape, round(w, 6), round(h, 6))
        counts[key] = counts.get(key, 0) + r.qty

    from collections import Counter

    shelves: list[dict] = []   # {"y": низ ряда, "x": курсор, "h": высота ряда}
    placed_idx: dict[str, int] = {}

    def try_shelf(sh, w, h):
        """Положить деталь в ряд; при allow_rotation — и повёрнутой. Возвращает (w,h) или None."""
        variants = [(w, h)] + ([(h, w)] if allow_rotation and abs(w - h) > 1e-9 else [])
        for pw, ph in variants:
            if sh["x"] + pw <= bed_x + 1e-9 and ph <= sh["h"] + 1e-9:
                return pw, ph
        return None

    def add_row(w, h):
        """Новый ряд над текущим верхним краем занятых рядов; False если не влезает."""
        top = max((sh["y"] + sh["h"] for sh in shelves), default=0.0)
        if w <= bed_x + 1e-9 and top + h <= bed_y + 1e-9:
            shelves.append({"y": top, "x": 0.0, "h": h})
            return True
        return False

    def place_one(name, shape, x, y, pw, ph):
        k = placed_idx.get(name, 0) + 1
        placed_idx[name] = k
        res.placed.append(PlacedPart(name, x, y, pw, ph, shape, k))

    remaining = Counter(counts)

    def fill_rows():
        """Один проход по рядам: курсор движется только вперёд (без отката),
        поэтому раскладка детерминирована и не зацикливается."""
        changed_any = False
        for sh in shelves:
            while True:
                # среди оставшихся выбираем максимально высокую деталь,
                # помещающуюся в высоту ряда (классический shelf-fill)
                best_key, best_fit = None, None
                for key, cnt in remaining.items():
                    if cnt <= 0:
                        continue
                    name, shape, w, h = key
                    fit = try_shelf(sh, w, h)
                    if fit and (best_fit is None or fit[1] > best_fit[1]):
                        best_key, best_fit = key, fit
                if best_key is None:
                    break
                name, shape, _w, _h = best_key
                pw, ph = best_fit
                place_one(name, shape, sh["x"], sh["y"], pw, ph)
                sh["x"] += pw
                remaining[best_key] -= 1
                changed_any = True
        return changed_any

    progress = True
    while any(c > 0 for c in remaining.values()) and progress:
        progress = fill_rows()
        if not any(c > 0 for c in remaining.values()):
            break
        # создаём новый ряд из самой крупной оставшейся детали, которая влезает
        candidates = [(k, c) for k, c in remaining.items() if c > 0]
        candidates.sort(key=lambda kc: (-kc[0][2] * kc[0][3], kc[0][0]))
        made_row = False
        for (name, shape, w, h), _cnt in candidates:
            variants = [(w, h)] + ([(h, w)] if allow_rotation and abs(w - h) > 1e-9 else [])
            for pw, ph in variants:
                if add_row(pw, ph):
                    made_row = True
                    break
            if made_row:
                break
        if not made_row:
            break  # стол заполнен

    for (name, _shape, _w, _h), cnt in remaining.items():
        if cnt > 0:
            res.unplaced.extend([name] * cnt)
    res.used_area_mm2 = sum((p.w_mm) * (p.h_mm) for p in res.placed)
    return res


# ------------------------------------------------------------- scheduling ----

@dataclass
class SchedItem:
    """Экземпляр детали для распределения по окнам."""
    name: str
    time_h: float


@dataclass
class WindowPlan:
    label: str                       # "День"/"Ночь"
    window: str                      # "07:30 → 16:15"
    capacity_h: float                # часов в окне (за одни сутки)
    items: list[tuple[str, float]] = field(default_factory=list)  # (имя, часы)
    overflow_h: float = 0.0          # сколько часов не влезло в окно (перенос на след. сутки)

    @property
    def load_h(self) -> float:
        return sum(t for _, t in self.items)


@dataclass
class ScheduleResult:
    day: WindowPlan
    night: WindowPlan
    total_time_h: float
    extra_days: int = 0              # полных/частичных дополнительных суток нехватки
    errors: list[str] = field(default_factory=list)

    @property
    def fits_one_day(self) -> bool:
        return not self.errors and self.extra_days == 0 and \
            self.day.overflow_h == 0 and self.night.overflow_h == 0


def schedule(items: list[SchedItem], work_start: str, work_end: str) -> ScheduleResult:
    """Распределяет экземпляры деталей по дневному и ночному окнам.

    Длинные (> размера ночного окна) ставятся в ночь первыми; затем остальные
    заполняют ночь по убыванию времени, а всё, что не влезло, — в день.
    Если не хватает и дня+ночи — добавляются сутки (extra_days).
    """
    res_errors: list[str] = []
    try:
        day_w, night_w = day_night_windows(work_start, work_end)
    except ValueError as ex:
        return ScheduleResult(day=WindowPlan("", "", 0), night=WindowPlan("", "", 0),
                              total_time_h=0, errors=[str(ex)])

    bad = [it for it in items if it.time_h <= 0]
    if bad:
        res_errors.append("Есть позиции с нулевым временем печати: "
                          + ", ".join(sorted({b.name for b in bad})))
        items = [it for it in items if it.time_h > 0]

    day_cap = day_w.duration_min / 60.0
    night_cap = night_w.duration_min / 60.0
    total = sum(it.time_h for it in items)

    day_plan = WindowPlan("День", f"{format_hhmm(day_w.start_min)} → {format_hhmm(day_w.end_min)}",
                          round(day_cap, 2))
    night_plan = WindowPlan("Ночь",
                            f"{format_hhmm(night_w.start_min)} → {format_hhmm(night_w.end_min)}",
                            round(night_cap, 2))

    if not res_errors and total > (day_cap + night_cap) + 1e-9:
        # партия больше, чем одни сутки: считаем нужное число суток
        import math
        res_errors.append(
            f"Партия не помещается в одни сутки ({total:.1f} ч > "
            f"{day_cap + night_cap:.1f} ч). Печать растянется минимум на "
            f"{math.ceil(total / (day_cap + night_cap))} сут(ок).")

    # --- эвристика LPT: длинные детали в НОЧЬ, короткие — в ДЕНЬ ---------------
    # Порог «длинная»: деталь нецелесообразно снимать днём (половина дневного окна).
    long_threshold = day_cap / 2.0
    sorted_items = sorted(items, key=lambda it: -it.time_h)
    night_left, day_left = night_cap, day_cap
    for it in sorted_items:
        if it.time_h >= long_threshold and it.time_h <= night_left + 1e-9:
            night_plan.items.append((it.name, it.time_h))
            night_left -= it.time_h
        elif it.time_h <= day_left + 1e-9:
            day_plan.items.append((it.name, it.time_h))
            day_left -= it.time_h
        elif it.time_h <= night_left + 1e-9:
            night_plan.items.append((it.name, it.time_h))
            night_left -= it.time_h
        else:
            # ни в день, ни в ночь не влезло -> перенос на следующие сутки
            if it.time_h > day_cap:
                night_plan.overflow_h += it.time_h
                night_plan.items.append((it.name + " (след. сутки)", it.time_h))
            else:
                day_plan.overflow_h += it.time_h
                day_plan.items.append((it.name + " (след. день)", it.time_h))

    return ScheduleResult(day=day_plan, night=night_plan,
                          total_time_h=round(total, 2), errors=res_errors)
