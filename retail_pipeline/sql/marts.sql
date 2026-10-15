-- В заказе одна товарная позиция. Большая версия задаёт новое состояние заказа.
CREATE OR REPLACE TABLE silver.orders AS
SELECT event_id, order_id, version, ordered_at, updated_at, status,
       product_id, quantity, unit_price_cents, country,
       quantity::BIGINT * unit_price_cents AS amount_cents
FROM bronze.events
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY version DESC) = 1;

-- Выручка считается по исходной дате заказа; возврат пересчитывает эту дату.
-- Модель не описывает движение денег или бухгалтерское признание выручки.
CREATE OR REPLACE TABLE gold.daily_sales AS
SELECT cast(ordered_at AS DATE) AS order_date, country,
       count(*) AS orders_total,
       count(*) FILTER (WHERE status = 'paid') AS paid_orders,
       count(*) FILTER (WHERE status = 'cancelled') AS cancelled_orders,
       count(*) FILTER (WHERE status = 'refunded') AS refunded_orders,
       coalesce(sum(amount_cents) FILTER (WHERE status = 'paid'), 0)::BIGINT AS revenue_cents,
       coalesce(sum(amount_cents) FILTER (WHERE status = 'refunded'), 0)::BIGINT AS refunded_cents
FROM silver.orders GROUP BY order_date, country;

CREATE OR REPLACE TABLE gold.product_sales AS
SELECT p.product_id, p.name, p.category,
       count(o.order_id) FILTER (WHERE o.status = 'paid') AS paid_orders,
       coalesce(sum(o.quantity) FILTER (WHERE o.status = 'paid'), 0)::BIGINT AS units_sold,
       coalesce(sum(o.amount_cents) FILTER (WHERE o.status = 'paid'), 0)::BIGINT AS revenue_cents
FROM silver.products p LEFT JOIN silver.orders o USING (product_id)
GROUP BY p.product_id, p.name, p.category;

CREATE OR REPLACE TABLE gold.quality_summary AS
SELECT reason, count(*) AS rejected_rows FROM audit.quarantine GROUP BY reason;
