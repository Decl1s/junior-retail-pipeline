# Учебный проект дата-инженера

Проект показывает путь от двух CSV-поставок до аналитических таблиц и отчёта:
загрузка, проверка схемы, удаление дублей, обновления заказов, карантин ошибок,
SQL-витрины и выгрузка в Parquet. Все демоданные придуманы генератором.

## Запуск

Нужен Python 3.11 или 3.12. В каталоге проекта:

```sh
python -m venv .venv
```

Linux: `source .venv/bin/activate`.
Windows PowerShell: `.venv\Scripts\Activate.ps1`.
Если активация запрещена, заменяйте `python` на `.venv\Scripts\python.exe`.

```sh
python -m pip install --only-binary=:all: -r requirements.txt
python -m retail_pipeline demo
python -m retail_pipeline run
```

Откройте `workspace/output/report.html` двойным щелчком. В нём будут
10 000 заказов, 9 000 оплаченных заказов и 6 отклонённых строк.
В базе хранится 11 000 уникальных событий; 100 дублей игнорируются.

## Как проверить

1. Повторите `python -m retail_pipeline run`. Новых событий будет 0,
   пропущенных ранее загруженных файлов — 2. Выручка не удвоится.
2. Выполните `python -m unittest discover -s tests -v`: все тесты должны пройти.
3. Откройте `workspace/output/quality_summary.csv`: увидите причины отказа.
4. Схема и запросы находятся в `retail_pipeline/sql/`, правила CSV —
   в [контракте](DATA-CONTRACT.md), объяснение для собеседования —
   в [INTERVIEW.md](INTERVIEW.md).

Чтобы увидеть последовательные поставки, сгенерируйте демо в другом каталоге,
сначала перенесите в рабочую папку только `001-initial.csv` и запустите обработку.
Затем добавьте `002-updates.csv` и повторите запуск: часть заказов изменит статус.

Новый набор демоданных можно создать в пустой папке:

```sh
python -m retail_pipeline demo --input workspace/another-input --orders 1000 --seed 7
python -m retail_pipeline run --input workspace/another-input --database workspace/another.duckdb --output workspace/another-output
```

Деньги представлены целыми центами USD. В заказе одна товарная позиция.
Выручка — сумма заказов, которые сейчас имеют статус paid, по исходной дате заказа.
При возврате пересчитывается исходная дата, а не дата возврата.

Рабочие файлы остаются локально в `workspace/`. Не публикуйте свои настоящие данные
и полученные из них отчёты. Перед загрузкой исходников запускайте
`python scripts/check_public.py`. Полный стек указан в [TECHNOLOGIES.md](../TECHNOLOGIES.md).
