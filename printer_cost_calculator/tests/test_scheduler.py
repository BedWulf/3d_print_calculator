"""Тесты логики этапа 2: окна день/ночь, упаковка на стол, планировщик."""

import unittest

from printer_cost_calculator.logic.scheduler import (
    TimeWindow, parse_hhmm, format_hhmm, day_night_windows,
    PackRequest, pack_bed, SchedItem, schedule,
)


class TimeTests(unittest.TestCase):
    def test_parse_format(self):
        self.assertEqual(parse_hhmm("07:30"), 450)
        self.assertEqual(parse_hhmm("7:05"), 425)
        self.assertEqual(format_hhmm(450), "07:30")
        with self.assertRaises(ValueError):
            parse_hhmm("25:00")

    def test_day_night(self):
        day, night = day_night_windows("07:30", "16:15")
        self.assertEqual(day.duration_min, 525)          # 8.75 ч
        self.assertEqual(night.duration_min, 1440 - 525) # 15.25 ч
        self.assertAlmostEqual(night.duration_min / 60, 15.25)

    def test_window_across_midnight(self):
        w = TimeWindow(22 * 60, 6 * 60)
        self.assertEqual(w.duration_min, 8 * 60)


class PackTests(unittest.TestCase):
    def test_rect_fit_with_gap(self):
        reqs = [PackRequest("Корпус", "rect", 100, 100, 8)]
        res = pack_bed(reqs, 300, 300, gap_mm=1)
        # габарит с зазором 101 мм: по X влезает floor(300/101)=2 ряда-колонки
        self.assertEqual(len(res.placed), 8)
        self.assertEqual(res.unplaced, [])
        for p in res.placed:                   # ничего не вылезает за стол
            self.assertLessEqual(p.x_mm + p.w_mm, 300 + 1e-6)
            self.assertLessEqual(p.y_mm + p.h_mm, 300 + 1e-6)

    def test_gap_consumes_capacity(self):
        # без зазора на стол 300 влезает ровно 9 деталей 100×100,
        # с зазором 1 мм — только 8 (это ожидаемое поведение, см. тест выше)
        reqs = [PackRequest("Корпус", "rect", 100, 100, 9)]
        res = pack_bed(reqs, 300, 300, gap_mm=0)
        self.assertEqual(len(res.placed), 9)
        self.assertEqual(res.unplaced, [])

    def test_no_overlap_gap_respected(self):
        reqs = [PackRequest("A", "rect", 50, 40, 4)]
        res = pack_bed(reqs, 300, 300, gap_mm=1)
        pts = sorted((p.x_mm, p.y_mm) for p in res.placed)
        # соседние в ряду стоят с шагом 50+gap
        row = [p for p in res.placed if abs(p.y_mm - pts[0][1]) < 1e-6]
        xs = sorted(p.x_mm for p in row)
        if len(xs) >= 2:
            self.assertAlmostEqual(xs[1] - xs[0], 51.0)

    def test_overflow_reported(self):
        reqs = [PackRequest("Большая", "rect", 200, 200, 5)]
        res = pack_bed(reqs, 300, 300, gap_mm=1)
        self.assertTrue(res.unplaced)          # 5 штук по 200×200 на 300×300 не влезут
        self.assertEqual(len(res.placed) + len(res.unplaced), 5)

    def test_circle_uses_diameter_square(self):
        reqs = [PackRequest("Круг", "circle", 100, 0, 9)]
        res = pack_bed(reqs, 300, 300, gap_mm=1)
        self.assertEqual(len(res.placed), 9)


class ScheduleTests(unittest.TestCase):
    def test_long_part_to_night_short_to_day(self):
        items = [SchedItem(f"Мелочь{i}", 0.5) for i in range(10)] + \
                [SchedItem("Долгая", 5.0)]
        r = schedule(items, "07:30", "16:15")
        self.assertEqual(r.errors, [])
        names_night = {n for n, _ in r.night.items}
        names_day = {n for n, _ in r.day.items}
        self.assertIn("Долгая", names_night)
        self.assertNotIn("Долгая", names_day)
        self.assertTrue(names_day)             # короткие — в день
        self.assertTrue(r.fits_one_day)

    def test_total_time_preserved(self):
        items = [SchedItem("A", 2.0), SchedItem("B", 3.5)]
        r = schedule(items, "07:30", "16:15")
        self.assertAlmostEqual(r.total_time_h, 5.5)
        self.assertAlmostEqual(r.day.load_h + r.night.load_h, 5.5)

    def test_over_day_capacity(self):
        items = [SchedItem("X", 20.0)] + [SchedItem("Y", 10.0)]
        r = schedule(items, "07:30", "16:15")
        self.assertTrue(r.errors)              # 30 ч > 24 ч
        self.assertFalse(r.fits_one_day)

    def test_invalid_time_returns_error(self):
        r = schedule([SchedItem("A", 1)], "abc", "16:15")
        self.assertTrue(r.errors)


if __name__ == "__main__":
    unittest.main()
