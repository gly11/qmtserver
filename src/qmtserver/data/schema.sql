CREATE TABLE IF NOT EXISTS data_jobs (
    job_id VARCHAR PRIMARY KEY,
    job_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    request_json VARCHAR NOT NULL,
    result_json VARCHAR,
    error_code VARCHAR,
    error_message VARCHAR,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_files (
    file_id VARCHAR PRIMARY KEY,
    job_id VARCHAR,
    kind VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    period VARCHAR NOT NULL,
    adjust VARCHAR NOT NULL,
    format VARCHAR NOT NULL,
    path VARCHAR NOT NULL,
    hash VARCHAR NOT NULL,
    row_count BIGINT NOT NULL,
    coverage_start VARCHAR,
    coverage_end VARCHAR,
    schema_version VARCHAR NOT NULL,
    qmtserver_version VARCHAR NOT NULL,
    xtquant_version VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS data_coverage (
    coverage_id VARCHAR PRIMARY KEY,
    kind VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    period VARCHAR NOT NULL,
    adjust VARCHAR NOT NULL,
    coverage_start VARCHAR,
    coverage_end VARCHAR,
    row_count BIGINT NOT NULL,
    file_count BIGINT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_files_lookup
ON data_files (kind, symbol, period, adjust, coverage_start, coverage_end);

CREATE INDEX IF NOT EXISTS idx_data_coverage_lookup
ON data_coverage (kind, symbol, period, adjust);
