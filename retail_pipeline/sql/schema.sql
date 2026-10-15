CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS silver.products (
    product_id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL,
    category VARCHAR NOT NULL, catalog_price_cents BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS bronze.events (
    event_id VARCHAR PRIMARY KEY, order_id VARCHAR NOT NULL, version INTEGER NOT NULL,
    ordered_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL, status VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL, quantity INTEGER NOT NULL,
    unit_price_cents BIGINT NOT NULL, country VARCHAR NOT NULL,
    payload_hash VARCHAR NOT NULL,
    UNIQUE(order_id, version)
);
CREATE TABLE IF NOT EXISTS audit.sources (
    source_key VARCHAR PRIMARY KEY, rows_seen BIGINT NOT NULL,
    valid_rows BIGINT NOT NULL, rejected_rows BIGINT NOT NULL,
    loaded_at TIMESTAMP DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS audit.quarantine (
    source_key VARCHAR NOT NULL, row_number BIGINT NOT NULL, reason VARCHAR NOT NULL,
    PRIMARY KEY(source_key, row_number)
);
CREATE TABLE IF NOT EXISTS audit.runs (
    run_id VARCHAR PRIMARY KEY, started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP DEFAULT current_timestamp,
    files_loaded INTEGER NOT NULL, files_skipped INTEGER NOT NULL,
    rows_seen BIGINT NOT NULL, valid_rows BIGINT NOT NULL, rejected_rows BIGINT NOT NULL,
    events_inserted BIGINT NOT NULL, duplicates_ignored BIGINT NOT NULL
);
