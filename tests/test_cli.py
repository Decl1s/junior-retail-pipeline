import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CommandTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([sys.executable, "-m", "retail_pipeline", *args], capture_output=True, text=True, encoding="utf-8")

    def test_russian_help_and_error(self):
        help_result = self.command("--help")
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("Использование:", help_result.stdout)
        self.assertIn("Команды:", help_result.stdout)
        self.assertIn("создать синтетические CSV", help_result.stdout)
        error = self.command("неизвестная-команда")
        self.assertEqual(error.returncode, 2)
        self.assertIn("Ошибка параметров", error.stderr)

    def test_default_output_is_russian(self):
        with tempfile.TemporaryDirectory() as folder:
            demo = self.command("demo", "--input", str(Path(folder)/"input"), "--orders", "10")
            self.assertEqual(demo.returncode, 0, demo.stderr)
            self.assertIn("Демоданные готовы.", demo.stdout)
            self.assertIn("Создано заказов: 10", demo.stdout)
            self.assertNotIn('"synthetic"', demo.stdout)

    def test_json_mode_keeps_automation_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            demo = self.command("demo", "--input", str(root/"input"), "--orders", "10", "--json")
            self.assertEqual(demo.returncode, 0, demo.stderr)
            self.assertTrue(json.loads(demo.stdout)["synthetic"])
            result = self.command("run", "--input", str(root/"input"), "--database", str(root/"warehouse.duckdb"), "--output", str(root/"output"), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["events_inserted"], 11)
            self.assertEqual(data["rejected_rows"], 6)
            report = (root/"output/report.html").read_text(encoding="utf-8")
            self.assertIn('lang="ru"', report)
            self.assertIn("Качество данных", report)
            self.assertIn("Дата заказа", report)
            self.assertIn("Блокнот", report)


if __name__ == "__main__":
    unittest.main()
