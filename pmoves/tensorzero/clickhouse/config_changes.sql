-- TensorZero Configuration Changes Table
-- Stores audit trail of all configuration changes for observability and debugging

CREATE DATABASE IF NOT EXISTS tensorzero;

USE tensorzero;

-- Drop table if exists (for clean recreation)
-- DROP TABLE IF EXISTS tensorzero_config_changes;

-- Configuration Changes Table
CREATE TABLE IF NOT EXISTS tensorzero_config_changes (
    -- Timestamp of the change
    timestamp DateTime COMMENT 'When the configuration change occurred',

    -- Configuration version identifier
    version String COMMENT 'Version of the configuration (e.g., git hash, sequential number)',

    -- Author information
    author String COMMENT 'Username or service account that made the change',

    -- Change metadata
    change_type String COMMENT 'Type of change: create, update, delete, rollback, hot_reload',
    resource_type String COMMENT 'Type of resource: function, variant, tool, global_config',
    resource_name String COMMENT 'Name of the resource being changed',

    -- Configuration content
    previous_config Nullable(String) COMMENT 'Previous configuration as JSON string',
    new_config Nullable(String) COMMENT 'New configuration as JSON string',
    diff Nullable(String) COMMENT 'Unified diff between previous and new configuration',

    -- Validation results
    validation_result Bool COMMENT 'Whether configuration validation passed',
    validation_errors Nullable(String) COMMENT 'JSON array of validation error messages',

    -- Additional metadata
    metadata Nullable(String) COMMENT 'Additional metadata as JSON string',

    -- Unique identifier for each change
    change_id UUID DEFAULT generateUUIDv4() COMMENT 'Unique identifier for the change record'
)
ENGINE = MergeTree()
ORDER BY (timestamp, change_type, resource_type, resource_name)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 1 YEAR
COMMENT 'Audit trail of all TensorZero configuration changes';

-- Create indexes for common queries
-- Note: ClickHouse uses skip indexes for performance optimization

-- Index for querying by resource
ALTER TABLE tensorzero_config_changes
ADD INDEX idx_resource_type resource_type TYPE bloom_filter GRANULARITY 1;

ALTER TABLE tensorzero_config_changes
ADD INDEX idx_resource_name resource_name TYPE bloom_filter GRANULARITY 1;

-- Index for querying by author
ALTER TABLE tensorzero_config_changes
ADD INDEX idx_author author TYPE bloom_filter GRANULARITY 1;

-- Index for querying by change type
ALTER TABLE tensorzero_config_changes
ADD INDEX idx_change_type change_type TYPE set(3) GRANULARITY 1;

-- Materialized View: Validation Error Rate by Hour
-- Provides pre-aggregated metrics for monitoring

CREATE MATERIALIZED VIEW IF NOT EXISTS tensorzero_config_validation_metrics
ENGINE = SummingMergeTree()
ORDER BY (time_bucket, resource_type)
PARTITION BY toYYYYMM(time_bucket)
TTL time_bucket + INTERVAL 6 MONTH
POPULATE
AS SELECT
    toStartOfHour(timestamp) AS time_bucket,
    resource_type,
    count() AS total_changes,
    countIf(validation_result = 0) AS validation_failures,
    countIf(change_type = 'rollback') AS rollback_count,
    countIf(change_type = 'hot_reload' AND validation_result = 1) AS hot_reload_success,
    countIf(change_type = 'hot_reload' AND validation_result = 0) AS hot_reload_failure
FROM tensorzero_config_changes
GROUP BY time_bucket, resource_type;

-- Materialized View: Change Frequency by Author
-- Tracks configuration change activity by user

CREATE MATERIALIZED VIEW IF NOT EXISTS tensorzero_config_author_metrics
ENGINE = SummingMergeTree()
ORDER BY (time_bucket, author)
PARTITION BY toYYYYMM(time_bucket)
TTL time_bucket + INTERVAL 6 MONTH
POPULATE
AS SELECT
    toStartOfHour(timestamp) AS time_bucket,
    author,
    count() AS total_changes,
    countIf(change_type = 'create') AS creates,
    countIf(change_type = 'update') AS updates,
    countIf(change_type = 'delete') AS deletes,
    countIf(change_type = 'rollback') AS rollbacks
FROM tensorzero_config_changes
GROUP BY time_bucket, author;

-- View: Configuration Changes Summary
-- Provides easy access to recent configuration activity

CREATE VIEW IF NOT EXISTS tensorzero_config_changes_summary AS
SELECT
    timestamp,
    version,
    author,
    change_type,
    resource_type,
    resource_name,
    validation_result,
    substring(diff, 1, 200) AS diff_preview,
    metadata
FROM tensorzero_config_changes
ORDER BY timestamp DESC
LIMIT 1000;

-- Sample Queries for Monitoring

-- 1. Recent configuration changes
-- SELECT * FROM tensorzero_config_changes
-- ORDER BY timestamp DESC
-- LIMIT 50;

-- 2. Validation error rate over last 24 hours
-- SELECT
--     countIf(validation_result = 0) AS errors,
--     count(*) AS total,
--     (errors / total) * 100 AS error_rate
-- FROM tensorzero_config_changes
-- WHERE timestamp >= now() - INTERVAL 1 DAY;

-- 3. Hot reload success rate
-- SELECT
--     countIf(change_type = 'hot_reload' AND validation_result = 1) AS success,
--     countIf(change_type = 'hot_reload') AS total,
--     (success / total) * 100 AS success_rate
-- FROM tensorzero_config_changes
-- WHERE timestamp >= now() - INTERVAL 1 DAY;

-- 4. Rollback count by resource type
-- SELECT
--     resource_type,
--     count(*) AS rollback_count
-- FROM tensorzero_config_changes
-- WHERE change_type = 'rollback'
-- AND timestamp >= now() - INTERVAL 7 DAY
-- GROUP BY resource_type;

-- 5. Most changed resources
-- SELECT
--     resource_type,
--     resource_name,
--     count(*) AS change_count
-- FROM tensorzero_config_changes
-- WHERE timestamp >= now() - INTERVAL 7 DAY
-- GROUP BY resource_type, resource_name
-- ORDER BY change_count DESC
-- LIMIT 10;

-- 6. Configuration changes by author
-- SELECT
--     author,
--     count(*) AS change_count,
--     countIf(validation_result = 0) AS failed_changes
-- FROM tensorzero_config_changes
-- WHERE timestamp >= now() - INTERVAL 1 DAY
-- GROUP BY author
-- ORDER BY change_count DESC;
