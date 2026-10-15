"""Самостоятельный отчёт без JavaScript, слежения, внешних шрифтов и ресурсов."""

from html import escape
from pathlib import Path

from .contracts import REASON_LABELS


def number(value: int) -> str:
    return f"{value:,}".replace(",", "\u202f")


def money(cents: int) -> str:
    return f"{number(cents // 100)},{cents % 100:02d} $"


def write_report(db, path: Path, metrics: dict) -> None:
    days = db.execute("SELECT order_date,sum(revenue_cents) AS revenue FROM gold.daily_sales GROUP BY order_date ORDER BY order_date").fetchall()
    maximum = max((revenue for _, revenue in days), default=1) or 1
    bars = "".join(f'<div class="bar-row"><span>{day:%d.%m.%Y}</span><div class="track"><div class="bar" style="width:{revenue/maximum*100:.2f}%"></div></div><strong>{money(revenue)}</strong></div>' for day, revenue in days)
    products = db.execute("SELECT name,category,paid_orders,units_sold,revenue_cents FROM gold.product_sales ORDER BY revenue_cents DESC,product_id").fetchall()
    product_rows = "".join("<tr>" + "".join(f"<td>{escape(number(value) if isinstance(value, int) else str(value))}</td>" for value in (*row[:4], money(row[4]))) + "</tr>" for row in products)
    quality = db.execute("SELECT reason,rejected_rows FROM gold.quality_summary ORDER BY reason").fetchall()
    quality_rows = "".join(f"<tr><td>{escape(REASON_LABELS.get(reason, reason))}</td><td>{count}</td></tr>" for reason, count in quality) or '<tr><td colspan="2">Отклонённых строк нет</td></tr>'
    path.write_text(f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>Конвейер продаж · Отчёт по данным</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f5f7;color:#142b3e;font:15px/1.6 system-ui,sans-serif}}main{{max-width:1050px;margin:auto;padding:36px 24px}}header{{display:flex;justify-content:space-between;align-items:center;gap:20px}}h1{{font-size:34px;line-height:1.2;margin:8px 0}}h2{{font-size:20px}}.eyebrow{{color:#087e8b;letter-spacing:2px;font-size:12px;font-weight:700}}.badge{{background:#dceff0;border:1px solid #a1ced2;color:#096873;padding:7px 12px;border-radius:30px;white-space:nowrap}}.muted{{color:#597184}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:28px 0}}.card,section{{background:white;border:1px solid #dde5ea;border-radius:14px;padding:22px}}.card strong{{display:block;font-size:25px;margin-top:10px}}section{{margin:20px 0}}.bar-row{{display:grid;grid-template-columns:92px 1fr 112px;gap:12px;align-items:center;font-size:12px;margin:6px 0}}.bar-row strong{{text-align:right}}.track{{height:12px;background:#edf3f6;border-radius:3px}}.bar{{height:100%;background:#138e99;border-radius:3px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:11px 8px;text-align:left;border-bottom:1px solid #e8edf1}}th{{color:#597184;font-size:12px;text-transform:uppercase;letter-spacing:1px}}.tables{{display:grid;grid-template-columns:2fr 1fr;gap:18px}}.scroll{{overflow:auto}}footer{{font-size:12px;color:#597184}}@media(max-width:720px){{.cards{{grid-template-columns:repeat(2,1fr)}}.tables{{display:block}}header{{display:block}}.badge{{display:inline-block;margin-top:12px}}.bar-row{{grid-template-columns:78px 1fr 90px;gap:6px;font-size:11px}}}}
</style></head><body><main><header><div><div class="eyebrow">УЧЕБНЫЙ ПРОЕКТ ДАТА-ИНЖЕНЕРА</div><h1>Конвейер продаж</h1><div class="muted">CSV → проверенные события → актуальные заказы → витрины SQL</div></div><span class="badge">Локальный отчёт · USD</span></header><div class="cards"><div class="card">Всего заказов<strong>{number(metrics['orders'])}</strong></div><div class="card">Оплачено заказов<strong>{number(metrics['paid_orders'])}</strong></div><div class="card">Текущая выручка<strong>{money(metrics['revenue_cents'])}</strong></div><div class="card">Отклонено строк<strong>{number(metrics['rejected_rows'])}</strong></div></div><section><h2>Выручка по исходной дате заказа</h2><p class="muted">Показано последнее состояние заказов. Отменённые и возвращённые заказы исключены из выручки.</p>{bars or '<p>Заказов пока нет.</p>'}</section><div class="tables"><section class="scroll"><h2>Продажи по товарам</h2><table><thead><tr><th>Товар</th><th>Категория</th><th>Оплачено</th><th>Штук</th><th>Выручка</th></tr></thead><tbody>{product_rows}</tbody></table></section><section><h2>Качество данных</h2><p class="muted">Ошибочные строки не попадают в таблицы продаж.</p><table><thead><tr><th>Причина</th><th>Строк</th></tr></thead><tbody>{quality_rows}</tbody></table></section></div><footer>{number(metrics['events'])} уникальных событий · Суммы хранятся в центах USD. Генератор создаёт полностью синтетические данные. Отчёт может также содержать ваши локальные данные: не публикуйте настоящие данные.</footer></main></body></html>''', encoding="utf-8")
