"""Создание воспроизводимых демопоставок без чтения внешних данных."""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import COLUMNS, COUNTRIES, PRODUCTS, PipelineError


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def generate(directory: Path, orders: int = 10_000, seed: int = 42) -> dict:
    if not 10 <= orders <= 100_000:
        raise PipelineError("Укажите от 10 до 100 000 демозаказов.")
    # Не перезаписываем чужие файлы. Для повторного демо нужна новая пустая папка.
    if directory.exists() and any(directory.iterdir()):
        raise PipelineError("Папка для демоданных должна быть пустой; выберите другую папку.")
    rng = random.Random(seed)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def stamp(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    initial = []
    updates = []
    for i in range(1, orders + 1):
        product = rng.choice(PRODUCTS)
        ordered = base + timedelta(minutes=rng.randrange(30 * 24 * 60))
        event = dict(zip(COLUMNS, (
            f"EVT-{i:08d}-1", f"ORD-{i:08d}", 1, stamp(ordered), stamp(ordered),
            "paid", product[0], rng.randint(1, 5), product[3], rng.choice(COUNTRIES),
        )))
        initial.append(event)
        if i % 10 == 0:
            updates.append({**event, "event_id": f"EVT-{i:08d}-2", "version": 2,
                            "updated_at": stamp(ordered + timedelta(days=2)),
                            "status": "refunded" if i % 20 == 0 else "cancelled"})
    invalid = []
    changes = (("quantity", "-2"), ("unit_price_cents", "not-a-number"),
               ("country", "ZZ"), ("ordered_at", "not-a-date"),
               ("product_id", "SKU-99"), ("status", "unknown"))
    for i, (field, value) in enumerate(changes, 1):
        event = {**initial[0], "event_id": f"BAD-{i:08d}", "order_id": f"ORD-{orders+i:08d}"}
        event[field] = value
        invalid.append(event)
    duplicates = max(1, orders // 100)
    write_csv(directory / "001-initial.csv", initial + initial[:duplicates])
    write_csv(directory / "002-updates.csv", updates + invalid)
    return {"synthetic": True, "seed": seed, "orders": orders,
            "initial_rows": len(initial) + duplicates, "update_rows": len(updates) + len(invalid),
            "expected_unique_events": orders + len(updates), "expected_quarantine": len(invalid),
            "expected_paid_orders": orders - len(updates)}
