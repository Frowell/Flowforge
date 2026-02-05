"""Query Router — dispatches compiled queries to the correct backing store.

This is the ONLY component (outside app/core/) that knows about backing stores.
Nodes and the compiler express intent, not destination. The router decides.

Routing rules:
- Live data (positions, P&L)    -> Materialize  (< 10ms)
- Point lookup (latest quote)   -> Redis         (< 1ms)
- Ad-hoc analytical query       -> ClickHouse    (< 500ms)
- Historical time-range query   -> ClickHouse    (< 500ms)
"""

import asyncio
import json
import time
from dataclasses import dataclass

import structlog
from redis.asyncio import Redis

from app.core.clickhouse import ClickHouseClient
from app.core.materialize import MaterializeClient
from app.core.metrics import query_execution_duration_seconds, query_result_rows
from app.services.workflow_compiler import CompiledSegment

logger = structlog.stdlib.get_logger(__name__)


@dataclass
class QueryResult:
    """Result from executing a compiled query segment."""

    columns: list[str]
    rows: list[dict]
    total_rows: int
    source: str  # which backing store answered


class QueryRouter:
    """Dispatches compiled query segments to the appropriate backing store."""

    def __init__(
        self,
        clickhouse: ClickHouseClient | None = None,
        redis: Redis | None = None,
        materialize: MaterializeClient | None = None,
    ):
        self._clickhouse = clickhouse
        self._redis = redis
        self._materialize = materialize

    async def execute(self, segment: CompiledSegment) -> QueryResult:
        """Route a compiled segment to the correct backing store and execute."""
        match segment.target:
            case "clickhouse":
                return await self._execute_clickhouse(segment)
            case "materialize":
                return await self._execute_materialize(segment)
            case "redis":
                return await self._execute_redis(segment)
            case _:
                raise ValueError(f"Unknown target: {segment.target}")

    async def execute_all(self, segments: list[CompiledSegment]) -> list[QueryResult]:
        """Execute multiple segments in parallel where possible."""
        if not segments:
            return []
        if len(segments) == 1:
            return [await self.execute(segments[0])]
        return list(await asyncio.gather(*(self.execute(seg) for seg in segments)))

    async def _execute_clickhouse(self, segment: CompiledSegment) -> QueryResult:
        """Execute against ClickHouse for analytical queries."""
        if not self._clickhouse:
            raise RuntimeError("ClickHouse client not configured")
        start = time.perf_counter()
        rows = await self._clickhouse.execute(segment.sql, segment.params)
        duration = time.perf_counter() - start
        columns = list(rows[0].keys()) if rows else []
        row_count = len(rows)

        query_execution_duration_seconds.labels(target="clickhouse").observe(duration)
        query_result_rows.labels(target="clickhouse").observe(row_count)
        logger.info(
            "query_executed",
            target="clickhouse",
            duration_ms=round(duration * 1000, 2),
            rows=row_count,
        )

        return QueryResult(
            columns=columns,
            rows=rows,
            total_rows=row_count,
            source="clickhouse",
        )

    async def _execute_materialize(self, segment: CompiledSegment) -> QueryResult:
        """Execute against Materialize for live data queries."""
        if not self._materialize:
            raise RuntimeError("Materialize client not configured")
        start = time.perf_counter()
        rows = await self._materialize.execute(
            segment.sql, list(segment.params.values()) if segment.params else None
        )
        duration = time.perf_counter() - start
        columns = list(rows[0].keys()) if rows else []
        row_count = len(rows)

        query_execution_duration_seconds.labels(target="materialize").observe(duration)
        query_result_rows.labels(target="materialize").observe(row_count)
        logger.info(
            "query_executed",
            target="materialize",
            duration_ms=round(duration * 1000, 2),
            rows=row_count,
        )

        return QueryResult(
            columns=columns,
            rows=rows,
            total_rows=row_count,
            source="materialize",
        )

    async def _execute_redis(self, segment: CompiledSegment) -> QueryResult:
        """Execute point lookups against Redis."""
        if not self._redis:
            raise RuntimeError("Redis client not configured")
        start = time.perf_counter()

        params = segment.params
        lookup_type = params.get("lookup_type", "GET")
        key = params.get("key", "")
        keys = params.get("keys", [])

        rows: list[dict] = []

        if lookup_type == "MGET" and keys:
            values = await self._redis.mget(keys)
            for k, v in zip(keys, values, strict=False):
                if v is not None:
                    try:
                        row = json.loads(v) if isinstance(v, str) else v
                        if isinstance(row, dict):
                            rows.append(row)
                    except (json.JSONDecodeError, TypeError):
                        rows.append({"key": k, "value": v})
        elif key:
            value = await self._redis.get(key)
            if value is not None:
                try:
                    row = json.loads(value) if isinstance(value, str) else value
                    if isinstance(row, dict):
                        rows.append(row)
                except (json.JSONDecodeError, TypeError):
                    rows.append({"key": key, "value": value})

        duration = time.perf_counter() - start
        columns = list(rows[0].keys()) if rows else []
        row_count = len(rows)

        query_execution_duration_seconds.labels(target="redis").observe(duration)
        query_result_rows.labels(target="redis").observe(row_count)
        logger.info(
            "query_executed",
            target="redis",
            duration_ms=round(duration * 1000, 2),
            rows=row_count,
        )

        return QueryResult(
            columns=columns,
            rows=rows,
            total_rows=row_count,
            source="redis",
        )
