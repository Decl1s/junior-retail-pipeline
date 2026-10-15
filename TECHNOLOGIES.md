# Используемые технологии и зависимости

| Компонент | Версия | Назначение | Причина выбора | Официальная документация |
| --- | --- | --- | --- | --- |
| Python | Поддержка 3.11–3.12; локально проверен 3.12.14 | Команды, чтение CSV, генерация и упаковка | Понятный код и небольшой набор зависимостей | https://docs.python.org/3.12/ |
| DuckDB для Python | 1.4.5, закреплена | Локальное хранилище, проверки и выгрузки CSV/Parquet | Аналитический SQL внутри процесса | https://duckdb.org/docs/lts/clients/python/overview |
| SQL DuckDB | Движок 1.4.5 | Оконные функции, QUALIFY, объединения, транзакции и агрегаты | Преобразования читаются отдельно от загрузчика | https://duckdb.org/docs/lts/sql/introduction |
| CSV | UTF-8, фиксированная схема | Пакетный ввод и читаемые выгрузки | Простой просмотр и воспроизведение | https://docs.python.org/3.12/library/csv.html |
| Apache Parquet | Встроенная запись DuckDB; сжатие Zstandard | Типизированные столбцовые выгрузки | Распространённый формат без ещё одной Python-библиотеки | https://parquet.apache.org/docs/ |
| HTML5 и CSS | Веб-стандарты | Локальный русский отчёт | Без JavaScript, внешних ресурсов и сборщика | https://developer.mozilla.org/ru/docs/Web/HTML |
| unittest и unittest.mock | Стандартная библиотека Python | Проверки поведения и восстановления | Не требуется отдельная зависимость | https://docs.python.org/3.12/library/unittest.html |
| Git | 2.x | История исходников и контроль состава | Стандартный инструмент с локальным служебным авторством | https://git-scm.com/docs |
| GitHub Actions | Исполнители Ubuntu и Windows | Тесты, проверка демо и упаковка | Воспроизводимая проверка целевых платформ | https://docs.github.com/ru/actions |
| actions/checkout | v4, закреплён коммит | Получение исходников в CI | Официальное действие | https://github.com/actions/checkout |
| actions/setup-python | v5, закреплён коммит | Установка Python в CI | Официальное действие | https://github.com/actions/setup-python |
| actions/upload-artifact | v4, закреплён коммит | Сохранение ZIP и контрольной суммы в CI | Официальное действие | https://github.com/actions/upload-artifact |
| pip и venv | Поставляются с Python | Установка DuckDB в отдельное окружение | Обычный запуск на обеих ОС | https://pip.pypa.io/en/stable/ |

Используются модули стандартной библиотеки: argparse, csv, datetime, hashlib, html,
importlib, io, json, os, pathlib, random, re, shutil, subprocess, sys, tempfile,
unittest, uuid и zipfile. Отдельно их устанавливать не нужно.
Parquet и Zstandard предоставляются библиотекой DuckDB; внешние расширения не скачиваются.

В `requirements.txt` закреплена единственная прямая зависимость.
DuckDB 1.4.5 не требует транзитивных Python-зависимостей. CI устанавливает готовый
бинарный пакет без дополнительных возможностей. Архив содержит исходники проекта;
Python и пакет DuckDB устанавливаются отдельно, DuckDB загружается из PyPI.
Названия пакетов, команд и полей сохраняют стандартную запись.
