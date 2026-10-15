"""Чтение CSV, преобразования SQL в транзакции и обновляемые выгрузки отчётов."""

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .contracts import COLUMNS, PRODUCTS, PipelineError
from .report import write_report

SQL_DIR = Path(__file__).with_name("sql")
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_ROWS = 250_000


def sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _read_source(path: Path) -> tuple[str, list[tuple]]:
    if path.is_symlink():
        raise PipelineError("Символические ссылки на входные файлы запрещены.")
    with path.open("rb") as handle:
        content = handle.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise PipelineError("Размер входного файла превышает 32 МиБ.")
    key = hashlib.sha256(content).hexdigest()
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise PipelineError("Заголовок CSV должен точно соответствовать описанной схеме полей.")
        rows = []
        for number, row in enumerate(reader, 2):
            if len(rows) >= MAX_ROWS:
                raise PipelineError("Число строк во входном файле превышает 250 000.")
            structural = None in row or any(row.get(k) is None for k in COLUMNS)
            values = tuple((row.get(k) or "").strip() for k in COLUMNS)
            # Хэшируем нормализованные поля; пути и лишние столбцы в хэш события не входят.
            digest = hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
            rows.append((key, number, *values, digest, structural))
        return key, rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise PipelineError("Входной файл должен быть корректным CSV в кодировке UTF-8.") from exc


def _assert_no_conflicts(db: duckdb.DuckDBPyConnection) -> None:
    conflicts = (
        "SELECT 1 FROM accepted GROUP BY event_id HAVING count(DISTINCT payload_hash) > 1 LIMIT 1",
        "SELECT 1 FROM accepted GROUP BY order_id, version HAVING count(*) > 1 LIMIT 1",
        "SELECT 1 FROM accepted a JOIN bronze.events b USING (event_id) WHERE a.payload_hash <> b.payload_hash LIMIT 1",
        "SELECT 1 FROM accepted a JOIN bronze.events b USING (order_id, version) WHERE a.event_id <> b.event_id LIMIT 1",
        "SELECT 1 FROM (SELECT order_id, ordered_at, product_id, country FROM accepted UNION ALL SELECT order_id, ordered_at, product_id, country FROM bronze.events) GROUP BY order_id HAVING count(DISTINCT (ordered_at, product_id, country)) > 1 LIMIT 1",
        "SELECT 1 FROM (SELECT order_id, version, updated_at FROM accepted UNION SELECT order_id, version, updated_at FROM bronze.events) a JOIN (SELECT order_id, version, updated_at FROM accepted UNION SELECT order_id, version, updated_at FROM bronze.events) b ON a.order_id=b.order_id AND a.version>b.version WHERE a.updated_at<b.updated_at LIMIT 1",
    )
    for query in conflicts:
        if db.execute(query).fetchone():
            raise PipelineError("Конфликт события или версии заказа: весь новый пакет отменён.")


def _quality_gate(db: duckdb.DuckDBPyConnection) -> None:
    revenue = db.execute("SELECT coalesce(sum(amount_cents),0) FROM silver.orders WHERE status='paid'").fetchone()[0]
    daily = db.execute("SELECT coalesce(sum(revenue_cents),0) FROM gold.daily_sales").fetchone()[0]
    products = db.execute("SELECT coalesce(sum(revenue_cents),0) FROM gold.product_sales").fetchone()[0]
    if revenue != daily or revenue != products:
        raise PipelineError("Суммы выручки не совпали: весь новый пакет отменён.")
    if db.execute("SELECT 1 FROM silver.orders o LEFT JOIN silver.products p USING(product_id) WHERE p.product_id IS NULL LIMIT 1").fetchone():
        raise PipelineError("Проверка справочника товаров не пройдена: весь новый пакет отменён.")


def export_snapshot(db: duckdb.DuckDBPyConnection, destination: Path) -> None:
    """Сначала собираем полную выгрузку; прежняя папка сохраняется до успешной замены."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise PipelineError("Символические ссылки на папку результатов запрещены.")
    stage = Path(tempfile.mkdtemp(prefix=".retail-export-", dir=destination.parent))
    backup = None
    try:
        for name, order in (("daily_sales", "order_date,country"),
                            ("product_sales", "revenue_cents DESC,product_id"),
                            ("quality_summary", "reason")):
            for suffix, options in (("csv", "FORMAT CSV, HEADER TRUE"),
                                    ("parquet", "FORMAT PARQUET, COMPRESSION ZSTD")):
                output = str(stage / f"{name}.{suffix}").replace("'", "''")
                db.execute(f"COPY (SELECT * FROM gold.{name} ORDER BY {order}) TO '{output}' ({options})")
        metrics = {
            "orders": db.execute("SELECT count(*) FROM silver.orders").fetchone()[0],
            "events": db.execute("SELECT count(*) FROM bronze.events").fetchone()[0],
            "paid_orders": db.execute("SELECT count(*) FROM silver.orders WHERE status='paid'").fetchone()[0],
            "revenue_cents": db.execute("SELECT coalesce(sum(revenue_cents),0) FROM gold.daily_sales").fetchone()[0],
            "rejected_rows": db.execute("SELECT count(*) FROM audit.quarantine").fetchone()[0],
            "currency": "USD", "data_kind": "локальные данные; команда demo создаёт синтетические заказы",
        }
        (stage / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_report(db, stage / "report.html", metrics)
        if destination.exists():
            # Специальный файл-маркер защищает чужую папку от случайной замены.
            if not (destination / ".retail-snapshot").is_file():
                raise PipelineError("Папка результатов не является выгрузкой этого проекта; выберите другую папку.")
            backup = destination.with_name(destination.name + ".backup-" + uuid.uuid4().hex)
            os.replace(destination, backup)
        (stage / ".retail-snapshot").write_text("junior-retail-pipeline\n", encoding="utf-8")
        os.replace(stage, destination)
        if backup:
            shutil.rmtree(backup)
    except BaseException:
        if backup and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def run(input_dir: Path, database: Path, output: Path) -> dict:
    in_path, db_path, out_path = input_dir.resolve(), database.resolve(), output.resolve()
    if (out_path == in_path or out_path in in_path.parents or in_path in out_path.parents
            or out_path == db_path or out_path in db_path.parents):
        raise PipelineError("Пути входных данных, базы и результатов не должны пересекаться.")
    if not input_dir.is_dir():
        raise PipelineError("Папка входных данных не существует.")
    files = sorted(input_dir.glob("*.csv"))
    if not files:
        raise PipelineError("В папке входных данных нет CSV-файлов.")
    if len(files) > 100:
        raise PipelineError("За один запуск можно обработать не более 100 CSV-файлов.")
    if database.is_symlink():
        raise PipelineError("Символические ссылки на файл базы запрещены.")
    database.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    with duckdb.connect(str(database)) as db:
        db.execute("SET TimeZone='UTC'")
        db.execute("BEGIN TRANSACTION")
        try:
            db.execute(sql("schema.sql"))
            db.executemany("INSERT INTO silver.products VALUES (?, ?, ?, ?) ON CONFLICT(product_id) DO UPDATE SET name=excluded.name,category=excluded.category", PRODUCTS)
            types = ",".join(f"{name} VARCHAR" for name in COLUMNS)
            db.execute(f"CREATE TEMP TABLE incoming (source_key VARCHAR,row_number BIGINT,{types},payload_hash VARCHAR,structural_error BOOLEAN)")
            loaded, skipped, total_rows, seen = 0, 0, 0, set()
            placeholders = ",".join("?" for _ in range(len(COLUMNS) + 4))
            for path in files:
                key, rows = _read_source(path)
                if key in seen or db.execute("SELECT 1 FROM audit.sources WHERE source_key=?", [key]).fetchone():
                    skipped += 1
                    continue
                seen.add(key)
                loaded += 1
                total_rows += len(rows)
                if total_rows > MAX_ROWS:
                    raise PipelineError("Число новых строк в пакете превышает 250 000.")
                if rows:
                    db.executemany(f"INSERT INTO incoming VALUES ({placeholders})", rows)
                # Файлы с одним заголовком тоже отмечаем как загруженные.
                db.execute("INSERT INTO audit.sources(source_key,rows_seen,valid_rows,rejected_rows) VALUES (?, ?, 0, 0)", [key, len(rows)])
            db.execute(sql("validate.sql"))
            _assert_no_conflicts(db)
            rows_seen, valid, rejected = db.execute("SELECT count(*),count(*) FILTER(WHERE reason IS NULL),count(*) FILTER(WHERE reason IS NOT NULL) FROM checked").fetchone()
            before = db.execute("SELECT count(*) FROM bronze.events").fetchone()[0]
            db.execute("INSERT INTO bronze.events SELECT * FROM accepted ON CONFLICT DO NOTHING")
            inserted = db.execute("SELECT count(*) FROM bronze.events").fetchone()[0] - before
            db.execute("INSERT INTO audit.quarantine SELECT source_key,row_number,reason FROM checked WHERE reason IS NOT NULL")
            db.execute("UPDATE audit.sources s SET valid_rows=c.valid_rows,rejected_rows=c.rejected_rows FROM (SELECT source_key,count(*) FILTER(WHERE reason IS NULL) AS valid_rows,count(*) FILTER(WHERE reason IS NOT NULL) AS rejected_rows FROM checked GROUP BY source_key) c WHERE s.source_key=c.source_key")
            db.execute(sql("marts.sql"))
            _quality_gate(db)
            result = dict(zip(("files_loaded", "files_skipped", "rows_seen", "valid_rows", "rejected_rows", "events_inserted", "duplicates_ignored"), (loaded, skipped, rows_seen, valid, rejected, inserted, valid - inserted)))
            db.execute("INSERT INTO audit.runs(run_id,started_at,files_loaded,files_skipped,rows_seen,valid_rows,rejected_rows,events_inserted,duplicates_ignored) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [uuid.uuid4().hex, started, *result.values()])
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        # Коммит базы и запись файлов не образуют единую ACID-транзакцию.
        # После ошибки выгрузки повторный запуск пропустит загруженные данные и восстановит файлы.
        try:
            export_snapshot(db, output)
        except (OSError, duckdb.Error, PipelineError) as exc:
            raise PipelineError("База сохранена, но выгрузка не удалась. Повторите команду для восстановления отчёта.") from exc
        return result
