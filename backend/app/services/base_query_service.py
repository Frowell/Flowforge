"""Base Query Service — shared logic for preview and widget data services.

Extracted from preview_service.py and widget_data_service.py to eliminate
duplication (M1). Provides cache operations, SQL wrapping, and dtype propagation.
"""

import hashlib
import json
import logging
import time
from typing import Literal

import sqlglot
from redis.asyncio import Redis

from app.core.metrics import cache_operation_duration_seconds, cache_operations_total
from app.services.workflow_compiler import CompiledSegment

logger = logging.getLogger(__name__)


class BaseQueryService:
    """Base class for services that execute constrained queries with caching."""

    def __init__(self, redis: Redis, cache_key_prefix: str):
        """Initialize with Redis client and cache key prefix.

        Args:
            redis: Redis async client for caching
            cache_key_prefix: Prefix for cache keys (e.g., "flowforge:preview:")
        """
        self._redis = redis
        self._cache_key_prefix = cache_key_prefix

    def _compute_cache_key_hash(self, payload: dict) -> str:
        """Compute SHA256 hash of a payload for cache key.

        Args:
            payload: Dictionary to hash (must be JSON-serializable)

        Returns:
            Cache key with prefix + first 16 chars of hash
        """
        serialized = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return f"{self._cache_key_prefix}{digest}"

    async def _cache_get(
        self, key: str, cache_type: Literal["preview", "widget"]
    ) -> dict | None:
        """Read from Redis cache. Returns None on miss or error (fail-open).

        Args:
            key: Cache key to read
            cache_type: Type of cache for metrics ("preview" or "widget")

        Returns:
            Cached dict if hit, None if miss or error
        """
        try:
            start = time.monotonic()
            raw = await self._redis.get(key)
            elapsed = time.monotonic() - start

            cache_operation_duration_seconds.labels(
                cache_type=cache_type, operation="get"
            ).observe(elapsed)

            if raw is not None:
                cache_operations_total.labels(
                    cache_type=cache_type, operation="get", status="hit"
                ).inc()
                return json.loads(raw)

            cache_operations_total.labels(
                cache_type=cache_type, operation="get", status="miss"
            ).inc()
        except Exception:
            cache_operations_total.labels(
                cache_type=cache_type, operation="get", status="error"
            ).inc()
            logger.warning("Cache read failed for key %s", key, exc_info=True)

        return None

    async def _cache_set(
        self, key: str, value: dict, ttl: int, cache_type: Literal["preview", "widget"]
    ) -> None:
        """Write to Redis cache with TTL. Errors logged, not raised.

        Args:
            key: Cache key to write
            value: Dictionary to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds
            cache_type: Type of cache for metrics ("preview" or "widget")
        """
        try:
            start = time.monotonic()
            await self._redis.set(key, json.dumps(value), ex=ttl)
            elapsed = time.monotonic() - start

            cache_operation_duration_seconds.labels(
                cache_type=cache_type, operation="set"
            ).observe(elapsed)

            cache_operations_total.labels(
                cache_type=cache_type, operation="set", status="hit"
            ).inc()
        except Exception:
            cache_operations_total.labels(
                cache_type=cache_type, operation="set", status="error"
            ).inc()
            logger.warning("Cache write failed for key %s", key, exc_info=True)

    def _wrap_with_limit_offset(
        self,
        segment: CompiledSegment,
        limit: int,
        offset: int,
        subquery_alias: str,
        clickhouse_settings: dict[str, int] | None = None,
    ) -> CompiledSegment:
        """Wrap a segment's SQL with LIMIT, OFFSET, and optional SETTINGS.

        Uses SQLGlot to build the wrapping query instead of string
        interpolation, preventing SQL injection.

        Args:
            segment: Compiled segment to wrap
            limit: Maximum rows to return
            offset: Number of rows to skip
            subquery_alias: Alias for the subquery
            clickhouse_settings: Optional dict of ClickHouse SETTINGS (int values only)

        Returns:
            New CompiledSegment with wrapped SQL

        Raises:
            TypeError: If segment.sql doesn't parse to a SELECT statement
        """
        dialect = segment.dialect or "clickhouse"
        inner = sqlglot.parse_one(segment.sql, dialect=dialect)

        # M5 fix: Replace assert with proper type check
        if not isinstance(inner, sqlglot.exp.Select):
            raise TypeError(
                f"Expected SELECT statement, got {type(inner).__name__} "
                f"for SQL: {segment.sql}"
            )

        wrapped = (
            sqlglot.select("*")
            .from_(inner.subquery(subquery_alias))
            .limit(int(limit))
            .offset(int(offset))
        )
        constrained_sql = wrapped.sql(dialect=dialect)

        # ClickHouse SETTINGS — module-level int constants, safe to append
        if clickhouse_settings and segment.target == "clickhouse":
            settings_parts = [
                f"{key}={int(value)}" for key, value in clickhouse_settings.items()
            ]
            constrained_sql += f" SETTINGS {', '.join(settings_parts)}"

        return CompiledSegment(
            sql=constrained_sql,
            dialect=segment.dialect,
            target=segment.target,
            source_node_ids=segment.source_node_ids,
            params=segment.params,
            limit=limit,
            offset=offset,
        )

    def _infer_dtype_from_clickhouse_type(self, ch_type: str) -> str:
        """Infer frontend-compatible dtype from ClickHouse type string.

        M8 fix: Map ClickHouse types to frontend dtypes instead of hardcoding "String".

        Args:
            ch_type: ClickHouse type name (e.g., "String", "UInt64", "Float64")

        Returns:
            Frontend dtype ("string", "int64", "float64", "datetime", "boolean")
        """
        ch_type_lower = ch_type.lower()

        # Integer types
        if any(
            t in ch_type_lower
            for t in ["int8", "int16", "int32", "int64", "uint8", "uint16", "uint32"]
        ):
            return "int64"

        # Unsigned large integers (might overflow in JS, but keep as int64)
        if "uint64" in ch_type_lower:
            return "int64"

        # Float types
        if any(t in ch_type_lower for t in ["float32", "float64", "decimal"]):
            return "float64"

        # Boolean
        if "bool" in ch_type_lower:
            return "boolean"

        # Date/DateTime types
        if any(t in ch_type_lower for t in ["date", "datetime"]):
            return "datetime"

        # Default to string for everything else (String, Enum, UUID, etc.)
        return "string"

    def _build_columns_with_types(
        self, column_names: list[str], schema: list[dict] | None = None
    ) -> list[dict]:
        """Build column metadata with proper dtypes.

        M8 fix: Use schema information if available, otherwise infer from names.

        Args:
            column_names: List of column names from query result
            schema: Optional list of column schemas from schema engine or query metadata

        Returns:
            List of dicts with {"name": str, "dtype": str}
        """
        if schema:
            # Schema provided — use it
            schema_by_name = {col.get("name"): col for col in schema}
            return [
                {
                    "name": name,
                    "dtype": schema_by_name.get(name, {}).get("dtype", "string"),
                }
                for name in column_names
            ]

        # No schema — default to string (but this is better than hardcoded everywhere)
        return [{"name": name, "dtype": "string"} for name in column_names]
