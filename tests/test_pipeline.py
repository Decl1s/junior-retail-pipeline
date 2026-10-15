import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb

from retail_pipeline.contracts import COLUMNS, PipelineError
from retail_pipeline.pipeline import run
from retail_pipeline.synthetic import generate, write_csv


def event(number=1, version=1, **changes):
    row = dict(zip(COLUMNS, (
        f"EVT-{number:08d}-{version}", f"ORD-{number:08d}", str(version),
        "2026-01-01T10:00:00Z", f"2026-01-{version:02d}T11:00:00Z", "paid",
        "SKU-01", "2", "450", "GB",
    )))
    return {**row, **changes}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / "input"
        self.input.mkdir()
        self.database = self.root / "warehouse.duckdb"
        self.output = self.root / "output"

    def tearDown(self):
        self.temp.cleanup()

    def execute(self):
        return run(self.input, self.database, self.output)

    def query(self, query):
        with duckdb.connect(str(self.database), read_only=True) as db:
            return db.execute(query).fetchall()

    def batch(self, name, rows):
        write_csv(self.input / name, rows)

    def test_incremental_batches_and_idempotency(self):
        self.batch("first.csv", [event(), event(), event(2)])
        first = self.execute()
        self.assertEqual(first["events_inserted"], 2)
        self.assertEqual(first["duplicates_ignored"], 1)
        self.batch("second.csv", [event(version=2, status="refunded"), event(3)])
        second = self.execute()
        self.assertEqual(second["files_skipped"], 1)
        self.assertEqual(second["events_inserted"], 2)
        before = (self.output / "daily_sales.parquet").read_bytes()
        repeat = self.execute()
        self.assertEqual(repeat["events_inserted"], 0)
        self.assertEqual(repeat["files_skipped"], 2)
        self.assertEqual(before, (self.output / "daily_sales.parquet").read_bytes())
        self.assertEqual(self.query("SELECT count(*),sum(amount_cents) FILTER(WHERE status='paid') FROM silver.orders"), [(3, 1800)])
        self.assertEqual(self.query("SELECT sum(revenue_cents),sum(refunded_cents) FROM gold.daily_sales"), [(1800, 900)])

    def test_older_late_event_does_not_revert_order(self):
        self.batch("new.csv", [event(version=2, status="cancelled")])
        self.execute()
        self.batch("old.csv", [event()])
        self.execute()
        self.assertEqual(self.query("SELECT version,status FROM silver.orders"), [(2, "cancelled")])

    def test_same_content_under_new_filename_is_skipped(self):
        self.batch("one.csv", [event()])
        self.execute()
        shutil.copyfile(self.input / "one.csv", self.input / "copy.csv")
        result = self.execute()
        self.assertEqual(result["files_skipped"], 2)
        self.assertEqual(self.query("SELECT count(*) FROM audit.sources"), [(1,)])

    def test_rejected_rows_have_reasons_without_raw_payload(self):
        self.batch("bad.csv", [event(), event(2, quantity="1.5"), event(3, quantity="0"),
                               event(4, unit_price_cents="NaN"), event(5, country="ZZ"),
                               event(6, product_id="SKU-99"), event(7, status="unknown"),
                               event(8, ordered_at="2026-99-01T00:00:00Z"),
                               event(9, updated_at="2025-12-31T00:00:00Z")])
        result = self.execute()
        self.assertEqual(result["rejected_rows"], 8)
        self.assertEqual(result["events_inserted"], 1)
        self.assertEqual([r[0] for r in self.query("DESCRIBE audit.quarantine")], ["source_key", "row_number", "reason"])
        self.assertEqual(self.query("SELECT sum(rejected_rows) FROM gold.quality_summary"), [(8,)])

    def test_extra_and_missing_fields_are_quarantined(self):
        with (self.input / "shape.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerow(list(event().values()) + ["extra"])
            writer.writerow(list(event(2).values())[:-1])
        self.assertEqual(self.execute()["rejected_rows"], 2)
        self.assertEqual(self.query("SELECT reason FROM audit.quarantine"), [("row_shape",), ("row_shape",)])

    def test_conflicting_event_rolls_back_all_new_files(self):
        self.batch("first.csv", [event()])
        self.execute()
        report = (self.output / "report.html").read_bytes()
        self.batch("conflict.csv", [event(quantity="3")])
        self.batch("otherwise-good.csv", [event(2)])
        with self.assertRaisesRegex(PipelineError, "пакет отменён"):
            self.execute()
        self.assertEqual(self.query("SELECT count(*) FROM bronze.events"), [(1,)])
        self.assertEqual(self.query("SELECT count(*) FROM audit.sources"), [(1,)])
        self.assertEqual(self.query("SELECT count(*) FROM audit.runs"), [(1,)])
        self.assertEqual(report, (self.output / "report.html").read_bytes())

    def test_duplicate_order_version_with_another_event_id_fails(self):
        self.batch("conflict.csv", [event(), event(event_id="EVT-00000009-1")])
        with self.assertRaises(PipelineError):
            self.execute()

    def test_order_immutable_fields_cannot_change(self):
        self.batch("first.csv", [event()])
        self.execute()
        self.batch("update.csv", [event(version=2, country="US")])
        with self.assertRaises(PipelineError):
            self.execute()

    def test_version_timestamp_must_be_monotonic(self):
        self.batch("bad.csv", [event(updated_at="2026-01-04T11:00:00Z"), event(version=2)])
        with self.assertRaises(PipelineError):
            self.execute()

    def test_header_error_does_not_load_previous_new_file(self):
        self.batch("one.csv", [event()])
        self.execute()
        self.batch("two.csv", [event(2)])
        (self.input / "wrong.csv").write_text("unexpected\nvalue\n", encoding="utf-8")
        with self.assertRaisesRegex(PipelineError, "Заголовок"):
            self.execute()
        self.assertEqual(self.query("SELECT count(*) FROM audit.sources"), [(1,)])

    def test_empty_valid_batch_and_all_invalid_batch_export(self):
        self.batch("empty.csv", [])
        self.batch("invalid.csv", [event(quantity="-1")])
        result = self.execute()
        self.assertEqual(result["files_loaded"], 2)
        self.assertEqual(result["events_inserted"], 0)
        metrics = json.loads((self.output / "metrics.json").read_text())
        self.assertEqual(metrics["revenue_cents"], 0)
        self.assertIn("Заказов пока нет", (self.output / "report.html").read_text())

    def test_export_failure_can_be_recovered_without_duplicates(self):
        self.batch("one.csv", [event()])
        with patch("retail_pipeline.pipeline.export_snapshot", side_effect=OSError("синтетическая ошибка")):
            with self.assertRaisesRegex(PipelineError, "База сохранена"):
                self.execute()
        self.assertEqual(self.query("SELECT count(*) FROM bronze.events"), [(1,)])
        result = self.execute()
        self.assertEqual(result["files_skipped"], 1)
        self.assertEqual(result["events_inserted"], 0)
        self.assertTrue((self.output / "report.html").is_file())

    def test_parquet_exports_reconcile_and_report_is_offline(self):
        self.batch("one.csv", [event(), event(2)])
        self.execute()
        with duckdb.connect() as db:
            amount = db.execute("SELECT sum(revenue_cents) FROM read_parquet(?)", [str(self.output / "daily_sales.parquet")]).fetchone()[0]
        self.assertEqual(amount, 1800)
        report = (self.output / "report.html").read_text()
        self.assertIn("18,00 $", report)
        self.assertNotIn("<script", report)
        self.assertNotIn("https://", report)

    def test_output_cannot_replace_unrelated_directory_or_input(self):
        self.batch("one.csv", [event()])
        self.output.mkdir()
        note = self.output / "keep.txt"
        note.write_text("keep", encoding="utf-8")
        with self.assertRaises(PipelineError):
            self.execute()
        self.assertEqual(note.read_text(), "keep")
        with self.assertRaisesRegex(PipelineError, "пересекаться"):
            run(self.input, self.database, self.input)

    def test_symlink_source_is_rejected(self):
        target = self.root / "source.csv"
        write_csv(target, [event()])
        try:
            (self.input / "linked.csv").symlink_to(target)
        except OSError:
            self.skipTest("Для создания символических ссылок нужны права ОС")
        with self.assertRaisesRegex(PipelineError, "Символические ссылки"):
            self.execute()

    def test_demo_is_deterministic_and_refuses_overwrite(self):
        first, second = self.root / "demo-a", self.root / "demo-b"
        expectation = generate(first, orders=100)
        generate(second, orders=100)
        for name in ["001-initial.csv", "002-updates.csv"]:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        result = run(first, self.database, self.output)
        self.assertEqual(result["events_inserted"], expectation["expected_unique_events"])
        self.assertEqual(result["rejected_rows"], expectation["expected_quarantine"])
        with self.assertRaises(PipelineError):
            generate(first, orders=100)


if __name__ == "__main__":
    unittest.main()
