"""
TensorZero Configuration Change Logger

Logs all configuration changes to ClickHouse for observability and auditing.
"""
import os
import re
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from clickhouse_driver import Client as ClickHouseClient
from difflib import unified_diff


# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# SQL Injection Prevention
# ============================================================================

# Valid table name pattern: alphanumeric, underscore, must start with letter
VALID_TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
VALID_DATABASE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')


def _validate_identifier(identifier: str, identifier_type: str = "table") -> str:
    """
    Validate a SQL identifier to prevent SQL injection.

    Only allows alphanumeric characters and underscores, must start with a letter.
    This prevents SQL injection while still allowing legitimate table/database names.

    Args:
        identifier: The identifier to validate.
        identifier_type: Type of identifier for error messages ('table' or 'database').

    Returns:
        The validated identifier.

    Raises:
        ValueError: If the identifier contains invalid characters.
    """
    if not identifier:
        raise ValueError(f"{identifier_type} name cannot be empty")

    if not VALID_TABLE_NAME_PATTERN.match(identifier):
        raise ValueError(
            f"Invalid {identifier_type} name '{identifier}'. "
            "Only alphanumeric characters and underscores are allowed, "
            "and must start with a letter."
        )

    return identifier


def _validate_positive_integer(value: int, param_name: str = "parameter") -> int:
    """
    Validate that a value is a positive integer for use in SQL queries.

    Args:
        value: The value to validate.
        param_name: Name of the parameter for error messages.

    Returns:
        The validated integer.

    Raises:
        ValueError: If the value is not a positive integer.
    """
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{param_name} must be a positive integer, got {value}")

    return value


@dataclass
class ConfigChangeRecord:
    """Represents a configuration change record."""
    timestamp: datetime
    version: str
    author: str
    change_type: str  # 'create', 'update', 'delete', 'rollback', 'hot_reload'
    resource_type: str  # 'function', 'variant', 'tool', 'global_config'
    resource_name: str
    previous_config: Optional[str]
    new_config: Optional[str]
    diff: Optional[str]
    validation_result: bool
    validation_errors: Optional[List[str]]
    metadata: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ClickHouse insertion."""
        return {
            'timestamp': self.timestamp,
            'version': self.version,
            'author': self.author,
            'change_type': self.change_type,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'previous_config': self.previous_config,
            'new_config': self.new_config,
            'diff': self.diff,
            'validation_result': self.validation_result,
            'validation_errors': json.dumps(self.validation_errors) if self.validation_errors else None,
            'metadata': json.dumps(self.metadata) if self.metadata else None,
        }


class ConfigChangeLogger:
    """
    Logs TensorZero configuration changes to ClickHouse.

    Provides observability for:
    - Configuration change history
    - Validation success/failure rates
    - Rollback tracking
    - Author attribution
    - Change diffs for debugging
    """

    def __init__(
        self,
        clickhouse_host: str = None,
        clickhouse_port: int = None,
        database: str = None,
        table: str = "tensorzero_config_changes",
    ):
        """
        Initialize the configuration change logger.

        Args:
            clickhouse_host: ClickHouse server host
            clickhouse_port: ClickHouse server port
            database: Database name
            table: Table name for config changes

        Raises:
            ValueError: If database or table name contains invalid characters.
        """
        self.clickhouse_host = clickhouse_host or os.getenv(
            "CLICKHOUSE_HOST", "tensorzero-clickhouse"
        )
        self.clickhouse_port = clickhouse_port or int(
            os.getenv("CLICKHOUSE_PORT", "9000")
        )

        # Validate and set database name (prevent SQL injection)
        raw_database = database or os.getenv("CLICKHOUSE_DATABASE", "tensorzero")
        self.database = _validate_identifier(raw_database, "database")

        # Validate and set table name (prevent SQL injection)
        self.table = _validate_identifier(table, "table")

        # Initialize ClickHouse client
        self.client = ClickHouseClient(
            host=self.clickhouse_host,
            port=self.clickhouse_port,
            database=self.database,
        )

        # Ensure table exists
        self._ensure_table_exists()

        logger.info(
            f"ConfigChangeLogger initialized: {self.clickhouse_host}:{self.clickhouse_port}/{self.database}.{self.table}"
        )

    def _ensure_table_exists(self):
        """Create the config_changes table if it doesn't exist."""
        # Use backtick quoting for ClickHouse identifiers (safe after validation)
        quoted_table = f"`{self.table}`"

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {quoted_table} (
            timestamp DateTime,
            version String,
            author String,
            change_type String,
            resource_type String,
            resource_name String,
            previous_config Nullable(String),
            new_config Nullable(String),
            diff Nullable(String),
            validation_result Bool,
            validation_errors Nullable(String),
            metadata Nullable(String),
            change_id UUID DEFAULT generateUUIDv4()
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, change_type, resource_type, resource_name)
        PARTITION BY toYYYYMM(timestamp)
        TTL timestamp + INTERVAL 1 YEAR
        """

        try:
            self.client.execute(create_table_sql)
            logger.info(f"Table {self.table} ensured")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def log_change(self, record: ConfigChangeRecord) -> str:
        """
        Log a configuration change.

        Args:
            record: ConfigChangeRecord to log

        Returns:
            change_id: UUID of the logged change
        """
        try:
            data = record.to_dict()
            quoted_table = f"`{self.table}`"

            # Insert into ClickHouse (table name is validated and quoted)
            self.client.execute(
                f"INSERT INTO {quoted_table} VALUES",
                [data],
            )

            # Get the generated change_id (using parameters for values)
            result = self.client.execute(
                f"SELECT change_id FROM {quoted_table} "
                f"WHERE timestamp = %(timestamp)s "
                f"AND resource_name = %(resource_name)s "
                f"ORDER BY change_id DESC LIMIT 1",
                {
                    'timestamp': data['timestamp'],
                    'resource_name': data['resource_name'],
                }
            )

            change_id = result[0][0] if result else None

            logger.info(
                f"Logged config change: {record.change_type} {record.resource_type}/{record.resource_name} "
                f"by {record.author} (valid={record.validation_result})"
            )

            return change_id

        except Exception as e:
            logger.error(f"Failed to log config change: {e}")
            raise

    def log_configuration_update(
        self,
        version: str,
        author: str,
        resource_type: str,
        resource_name: str,
        previous_config: Dict[str, Any],
        new_config: Dict[str, Any],
        validation_result: bool,
        validation_errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log a configuration update with diff.

        Args:
            version: Configuration version
            author: Username or service account
            resource_type: Type of resource (function, variant, tool, etc.)
            resource_name: Name of the resource
            previous_config: Previous configuration
            new_config: New configuration
            validation_result: Whether validation passed
            validation_errors: List of validation errors
            metadata: Additional metadata

        Returns:
            change_id: UUID of the logged change
        """
        # Generate diff
        diff = self._generate_diff(
            previous_config,
            new_config,
            fromfile=f"{resource_type}/{resource_name}@{version}~",
            tofile=f"{resource_type}/{resource_name}@{version}",
        )

        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            version=version,
            author=author,
            change_type="update",
            resource_type=resource_type,
            resource_name=resource_name,
            previous_config=json.dumps(previous_config, indent=2),
            new_config=json.dumps(new_config, indent=2),
            diff=diff,
            validation_result=validation_result,
            validation_errors=validation_errors,
            metadata=metadata,
        )

        return self.log_change(record)

    def log_configuration_create(
        self,
        version: str,
        author: str,
        resource_type: str,
        resource_name: str,
        config: Dict[str, Any],
        validation_result: bool,
        validation_errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a configuration creation."""
        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            version=version,
            author=author,
            change_type="create",
            resource_type=resource_type,
            resource_name=resource_name,
            previous_config=None,
            new_config=json.dumps(config, indent=2),
            diff=None,
            validation_result=validation_result,
            validation_errors=validation_errors,
            metadata=metadata,
        )

        return self.log_change(record)

    def log_configuration_delete(
        self,
        version: str,
        author: str,
        resource_type: str,
        resource_name: str,
        previous_config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a configuration deletion."""
        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            version=version,
            author=author,
            change_type="delete",
            resource_type=resource_type,
            resource_name=resource_name,
            previous_config=json.dumps(previous_config, indent=2),
            new_config=None,
            diff=None,
            validation_result=True,
            validation_errors=None,
            metadata=metadata,
        )

        return self.log_change(record)

    def log_configuration_rollback(
        self,
        version: str,
        author: str,
        resource_type: str,
        resource_name: str,
        from_version: str,
        config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a configuration rollback."""
        rollback_metadata = metadata or {}
        rollback_metadata['rolled_back_from_version'] = from_version

        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            version=version,
            author=author,
            change_type="rollback",
            resource_type=resource_type,
            resource_name=resource_name,
            previous_config=None,
            new_config=json.dumps(config, indent=2),
            diff=f"Rolled back from version {from_version}",
            validation_result=True,
            validation_errors=None,
            metadata=rollback_metadata,
        )

        return self.log_change(record)

    def log_hot_reload(
        self,
        version: str,
        author: str,
        success: bool,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a hot reload event."""
        reload_metadata = metadata or {}
        reload_metadata['hot_reload_success'] = success
        if error_message:
            reload_metadata['error_message'] = error_message

        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            version=version,
            author=author,
            change_type="hot_reload",
            resource_type="global_config",
            resource_name="tensorzero.toml",
            previous_config=None,
            new_config=None,
            diff=None,
            validation_result=success,
            validation_errors=[error_message] if error_message else None,
            metadata=reload_metadata,
        )

        return self.log_change(record)

    def _generate_diff(
        self,
        previous: Dict[str, Any],
        new: Dict[str, Any],
        fromfile: str = "previous",
        tofile: str = "new",
        context_lines: int = 3,
    ) -> str:
        """
        Generate a unified diff between two configurations.

        Args:
            previous: Previous configuration
            new: New configuration
            fromfile: Label for previous configuration
            tofile: Label for new configuration
            context_lines: Number of context lines in diff

        Returns:
            Unified diff as string
        """
        prev_lines = json.dumps(previous, indent=2).splitlines(keepends=True)
        new_lines = json.dumps(new, indent=2).splitlines(keepends=True)

        diff = unified_diff(
            prev_lines,
            new_lines,
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
            n=context_lines,
        )

        return "".join(diff)

    def get_change_history(
        self,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve configuration change history.

        Args:
            resource_type: Filter by resource type
            resource_name: Filter by resource name
            limit: Maximum number of records to return

        Returns:
            List of change records
        """
        where_clauses = []
        params = {}

        if resource_type:
            where_clauses.append("resource_type = %(resource_type)s")
            params['resource_type'] = resource_type

        if resource_name:
            where_clauses.append("resource_name = %(resource_name)s")
            params['resource_name'] = resource_name

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        quoted_table = f"`{self.table}`"
        query = f"""
        SELECT
            timestamp,
            version,
            author,
            change_type,
            resource_type,
            resource_name,
            validation_result,
            diff,
            metadata
        FROM {quoted_table}
        {where_sql}
        ORDER BY timestamp DESC
        LIMIT %(limit)s
        """

        params['limit'] = _validate_positive_integer(limit, "limit")

        try:
            results = self.client.execute(query, params)
            return [
                {
                    'timestamp': r[0],
                    'version': r[1],
                    'author': r[2],
                    'change_type': r[3],
                    'resource_type': r[4],
                    'resource_name': r[5],
                    'validation_result': r[6],
                    'diff': r[7],
                    'metadata': json.loads(r[8]) if r[8] else None,
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve change history: {e}")
            return []

    def get_validation_error_rate(
        self,
        time_window_hours: int = 24,
    ) -> float:
        """
        Calculate validation error rate over time window.

        Args:
            time_window_hours: Time window in hours

        Returns:
            Error rate as percentage (0-100)
        """
        validated_hours = _validate_positive_integer(time_window_hours, "time_window_hours")
        quoted_table = f"`{self.table}`"

        query = f"""
        SELECT
            countIf(validation_result = 0) AS errors,
            count(*) AS total,
            (errors / total) * 100 AS error_rate
        FROM {quoted_table}
        WHERE timestamp >= now() - INTERVAL {validated_hours} HOUR
        """

        try:
            results = self.client.execute(query)
            if results and results[0]:
                return float(results[0][2]) if results[0][1] > 0 else 0.0
            return 0.0
        except Exception as e:
            logger.error(f"Failed to calculate error rate: {e}")
            return 0.0

    def get_hot_reload_success_rate(
        self,
        time_window_hours: int = 24,
    ) -> float:
        """
        Calculate hot reload success rate over time window.

        Args:
            time_window_hours: Time window in hours

        Returns:
            Success rate as percentage (0-100)
        """
        validated_hours = _validate_positive_integer(time_window_hours, "time_window_hours")
        quoted_table = f"`{self.table}`"

        query = f"""
        SELECT
            countIf(change_type = 'hot_reload' AND validation_result = 1) AS success,
            countIf(change_type = 'hot_reload') AS total,
            (success / total) * 100 AS success_rate
        FROM {quoted_table}
        WHERE timestamp >= now() - INTERVAL {validated_hours} HOUR
        """

        try:
            results = self.client.execute(query)
            if results and results[0]:
                return float(results[0][2]) if results[0][1] > 0 else 0.0
            return 0.0
        except Exception as e:
            logger.error(f"Failed to calculate reload success rate: {e}")
            return 0.0

    def get_rollback_count(
        self,
        time_window_hours: int = 24,
    ) -> int:
        """
        Count rollbacks over time window.

        Args:
            time_window_hours: Time window in hours

        Returns:
            Number of rollbacks
        """
        validated_hours = _validate_positive_integer(time_window_hours, "time_window_hours")
        quoted_table = f"`{self.table}`"

        query = f"""
        SELECT count(*)
        FROM {quoted_table}
        WHERE change_type = 'rollback'
        AND timestamp >= now() - INTERVAL {validated_hours} HOUR
        """

        try:
            results = self.client.execute(query)
            return results[0][0] if results else 0
        except Exception as e:
            logger.error(f"Failed to count rollbacks: {e}")
            return 0
