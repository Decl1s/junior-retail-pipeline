"""В демо одна товарная позиция на заказ; деньги хранятся в целых центах."""

COLUMNS = (
    "event_id", "order_id", "version", "ordered_at", "updated_at", "status",
    "product_id", "quantity", "unit_price_cents", "country",
)
PRODUCTS = (
    ("SKU-01", "Блокнот", "Канцелярия", 450),
    ("SKU-02", "Настольная лампа", "Дом", 3200),
    ("SKU-03", "Бутылка для воды", "Отдых", 1800),
    ("SKU-04", "Клавиатура", "Электроника", 6500),
    ("SKU-05", "Коврик для мыши", "Электроника", 900),
    ("SKU-06", "Коробка для хранения", "Дом", 1250),
)
COUNTRIES = ("GB", "DE", "FR", "US", "CA")
STATUSES = ("paid", "cancelled", "refunded")


REASON_LABELS = {
    "row_shape": "Число полей в строке", "event_id": "Код события",
    "order_id": "Код заказа", "version": "Версия заказа",
    "ordered_at": "Дата заказа", "updated_at": "Дата обновления",
    "status": "Статус заказа", "product_id": "Код товара",
    "quantity": "Количество", "unit_price_cents": "Цена товара", "country": "Код страны",
}


class PipelineError(Exception):
    """Понятная ошибка без вывода исходных строк или приватных путей."""
