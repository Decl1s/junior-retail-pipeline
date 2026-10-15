-- Все поля CSV сначала читаются как VARCHAR. Неоднозначные числа и даты без UTC отклоняем.
CREATE OR REPLACE TEMP TABLE checked AS
SELECT *, CASE
    WHEN structural_error THEN 'row_shape'
    WHEN NOT regexp_full_match(event_id, '[A-Z]+-[0-9]{8}(-[0-9]+)?') THEN 'event_id'
    WHEN NOT regexp_full_match(order_id, 'ORD-[0-9]{8}') THEN 'order_id'
    WHEN NOT regexp_full_match(version, '[0-9]+')
         OR try_cast(version AS INTEGER) NOT BETWEEN 1 AND 1000000
         OR try_cast(version AS INTEGER) IS NULL THEN 'version'
    WHEN NOT regexp_full_match(ordered_at, '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
         OR try_cast(ordered_at AS TIMESTAMP) IS NULL THEN 'ordered_at'
    WHEN NOT regexp_full_match(updated_at, '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
         OR try_cast(updated_at AS TIMESTAMP) IS NULL
         OR try_cast(updated_at AS TIMESTAMP) < try_cast(ordered_at AS TIMESTAMP) THEN 'updated_at'
    WHEN status NOT IN ('paid', 'cancelled', 'refunded') THEN 'status'
    WHEN product_id NOT IN (SELECT product_id FROM silver.products) THEN 'product_id'
    WHEN NOT regexp_full_match(quantity, '[0-9]+')
         OR try_cast(quantity AS INTEGER) NOT BETWEEN 1 AND 1000
         OR try_cast(quantity AS INTEGER) IS NULL THEN 'quantity'
    WHEN NOT regexp_full_match(unit_price_cents, '[0-9]+')
         OR try_cast(unit_price_cents AS BIGINT) NOT BETWEEN 1 AND 10000000
         OR try_cast(unit_price_cents AS BIGINT) IS NULL THEN 'unit_price_cents'
    WHEN country NOT IN ('GB', 'DE', 'FR', 'US', 'CA') THEN 'country'
    ELSE NULL END AS reason
FROM incoming;

CREATE OR REPLACE TEMP TABLE accepted AS
SELECT DISTINCT event_id, order_id, cast(version AS INTEGER) AS version,
       cast(ordered_at AS TIMESTAMP) AS ordered_at,
       cast(updated_at AS TIMESTAMP) AS updated_at,
       status, product_id, cast(quantity AS INTEGER) AS quantity,
       cast(unit_price_cents AS BIGINT) AS unit_price_cents, country, payload_hash
FROM checked WHERE reason IS NULL;
