"""Проверка стандартного демо и повторного запуска без вывода исходных данных."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    completed = subprocess.run([sys.executable, "-m", "retail_pipeline", "run", "--json"], check=True, capture_output=True, text=True, encoding="utf-8")
    result = json.loads(completed.stdout)
    assert result["files_loaded"] == 0 and result["files_skipped"] == 2
    assert result["events_inserted"] == 0
    metrics = json.loads(Path("workspace/output/metrics.json").read_text(encoding="utf-8"))
    assert (metrics["orders"], metrics["events"], metrics["paid_orders"], metrics["rejected_rows"]) == (10000, 11000, 9000, 6)
    print("Синтетическое демо и повторный запуск без дублей проверены.")


if __name__ == "__main__":
    main()
