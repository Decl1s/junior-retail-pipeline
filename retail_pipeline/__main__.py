import argparse
import json
import sys
from pathlib import Path

import duckdb

from . import __version__
from .contracts import PipelineError
from .pipeline import run
from .synthetic import generate


class RussianArgumentParser(argparse.ArgumentParser):
    """Русские заголовки справки и безопасное сообщение о неверных параметрах."""

    def __init__(self, *args, **kwargs):
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", help="показать справку и выйти")

    def format_help(self):
        return super().format_help().replace("usage: ", "Использование: ").replace("options:", "Параметры:").replace("positional arguments:", "Аргументы:")

    def format_usage(self):
        return super().format_usage().replace("usage: ", "Использование: ")

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "Ошибка параметров. Проверьте команду и значения; справка: --help.\n")


RESULT_LABELS = {
    "synthetic": "Данные полностью синтетические", "seed": "Начальное значение генератора",
    "orders": "Создано заказов", "initial_rows": "Строк в первой поставке",
    "update_rows": "Строк во второй поставке", "expected_unique_events": "Ожидается уникальных событий",
    "expected_quarantine": "Ожидается отклонённых строк", "expected_paid_orders": "Ожидается оплаченных заказов",
    "files_loaded": "Загружено файлов", "files_skipped": "Пропущено загруженных ранее файлов",
    "rows_seen": "Прочитано новых строк", "valid_rows": "Корректных строк",
    "rejected_rows": "Отклонено строк", "events_inserted": "Добавлено событий",
    "duplicates_ignored": "Пропущено повторов событий",
}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = RussianArgumentParser(prog="python -m retail_pipeline", description="Синтетические заказы: CSV → DuckDB → Parquet и локальный HTML-отчёт")
    parser.add_argument("--version", action="version", version=__version__, help="показать версию")
    commands = parser.add_subparsers(dest="command", required=True, title="Команды")
    demo = commands.add_parser("demo", help="создать синтетические CSV без чтения чужих файлов")
    demo.add_argument("--input", type=Path, default=Path("workspace/input"), help="пустая папка для демоданных")
    demo.add_argument("--orders", type=int, default=10_000, help="число заказов: от 10 до 100 000")
    demo.add_argument("--seed", type=int, default=42, help="значение для воспроизводимого генератора")
    execute = commands.add_parser("run", help="загрузить новые CSV и пересчитать витрины")
    execute.add_argument("--input", type=Path, default=Path("workspace/input"), help="папка с CSV")
    execute.add_argument("--database", type=Path, default=Path("workspace/warehouse.duckdb"), help="файл локальной базы")
    execute.add_argument("--output", type=Path, default=Path("workspace/output"), help="папка для отчёта и выгрузок")
    for command in (demo, execute):
        command.add_argument("--json", action="store_true", help="вывести результат в JSON для автоматизации")
    args = parser.parse_args()
    try:
        result = generate(args.input, args.orders, args.seed) if args.command == "demo" else run(args.input, args.database, args.output)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Демоданные готовы." if args.command == "demo" else "Обработка завершена.")
            for key, value in result.items():
                if isinstance(value, bool):
                    value = "да" if value else "нет"
                print(f"{RESULT_LABELS[key]}: {value}")
            if args.command == "run":
                print("Откройте report.html в выбранной папке результатов.")
        return 0
    except (PipelineError, OSError, duckdb.Error) as exc:
        # Ошибки ОС и базы могут содержать пути или исходные значения: не выводим их.
        message = str(exc) if isinstance(exc, PipelineError) else "Ошибка записи или базы. Проверьте права на файлы и закройте другие процессы, записывающие в базу."
        print("Ошибка обработки: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
