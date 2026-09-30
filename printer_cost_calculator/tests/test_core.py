"""Тесты слоя данных и расчётной логики (запуск: python -m pytest или python -m unittest)."""

import tempfile
import unittest
from pathlib import Path

from printer_cost_calculator.db.models import Printer, Material, Consumable, Settings
from printer_cost_calculator.db.repository import Repository
from printer_cost_calculator.logic.calculator import CalcInput, calculate


class RepoCRUDTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.repo = Repository(self.tmp.name)

    def tearDown(self):
        self.repo.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_printer_crud(self):
        pid = self.repo.add_printer(Printer(name="Ender 3", electricity_kwh_per_hour=0.15,
                                             depreciation_rub_per_hour=10))
        printers = self.repo.list_printers()
        self.assertEqual(len(printers), 1)
        printers[0].depreciation_rub_per_hour = 12
        self.repo.update_printer(printers[0])
        self.assertEqual(self.repo.list_printers()[0].depreciation_rub_per_hour, 12)
        self.repo.delete_printer(pid)
        self.assertEqual(self.repo.list_printers(), [])

    def test_material_crud_and_price_per_gram(self):
        self.repo.add_material(Material(name="PLA", density_g_cm3=1.24,
                                        spool_weight_kg=1.0, price_rub=1000))
        m = self.repo.list_materials()[0]
        self.assertAlmostEqual(m.price_per_gram, 1.0)
        m.spool_weight_kg = 0.5
        self.repo.update_material(m)
        self.assertAlmostEqual(self.repo.list_materials()[0].price_per_gram, 2.0)

    def test_consumable_and_settings(self):
        self.repo.add_consumable(Consumable(kind=Consumable.KIND_GLUE, name="Клей-карандаш",
                                            unit="шт.", consumption_per_part=0.05, price_rub=60))
        c = self.repo.list_consumables()[0]
        self.assertEqual(c.kind, "glue")
        s = self.repo.get_settings()
        s.electricity_price_rub_per_kwh = 7.5
        self.repo.save_settings(s)
        self.assertEqual(self.repo.get_settings().electricity_price_rub_per_kwh, 7.5)


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.printer = Printer(id=1, name="Ender 3", electricity_kwh_per_hour=0.15,
                               depreciation_rub_per_hour=10)
        self.pla = Material(id=1, name="PLA", spool_weight_kg=1.0, price_rub=1000)   # 1 ₽/г
        self.petg = Material(id=2, name="PETG", spool_weight_kg=0.5, price_rub=700)  # 1.4 ₽/г
        self.napkin = Consumable(id=1, kind="napkin", name="Салфетки",
                                 unit="шт.", consumption_per_part=2, price_rub=5)
        self.settings = Settings(electricity_price_rub_per_kwh=5)

    def _input(self, **kw):
        base = dict(printer=self.printer, print_time_hours=2.0, part_mass_g=50,
                    part_material=self.pla, use_supports=False, quantity=1,
                    selected_consumables=[self.napkin], settings=self.settings)
        base.update(kw)
        return CalcInput(**base)

    def test_without_supports(self):
        r = calculate(self._input())
        self.assertEqual(r.errors, [])
        titles = [s.title for s in r.steps]
        self.assertNotIn("Материал поддержек", titles)
        # электричество: 2*0.15*5 = 1.5; амортизация: 2*10 = 20; материал: 50*1 = 50; салфетки: 2
        self.assertAlmostEqual(r.per_part_total, 1.5 + 20 + 50 + 2)
        self.assertAlmostEqual(r.batch_total, r.per_part_total)

    def test_with_supports_different_material(self):
        r = calculate(self._input(use_supports=True, support_mass_g=20,
                                  support_material=self.petg))
        sup = [s for s in r.steps if s.title == "Материал поддержек"][0]
        self.assertAlmostEqual(sup.value_rub, 20 * 1.4)

    def test_batch(self):
        r = calculate(self._input(quantity=10))
        self.assertAlmostEqual(r.batch_total, r.per_part_total * 10)

    def test_validation_errors(self):
        r = calculate(self._input(part_mass_g=0, use_supports=True, support_mass_g=0))
        self.assertTrue(r.errors)
        self.assertEqual(r.steps, [])


if __name__ == "__main__":
    unittest.main()
