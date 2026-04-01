from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .schemas import Citation, FinalReport, ResearchPlanNode, ResearchRun, RunStep, SourceDocument, utc_now


class PostgresStore:
    def __init__(self, artifact_root: Path, database_url: str) -> None:
        self._artifact_root = artifact_root
        self._database_url = database_url
        self._pool: ConnectionPool | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    @property
    def artifact_root(self) -> Path:
        return self._artifact_root

    async def initialize(self) -> None:
        if self._pool is not None:
            return

        last_error: Exception | None = None
        for _ in range(20):
            try:
                self._pool = await asyncio.to_thread(self._open_pool)
                await asyncio.to_thread(self._ensure_schema_sync)
                return
            except Exception as exc:
                last_error = exc
                if self._pool is not None:
                    await asyncio.to_thread(self._pool.close)
                    self._pool = None
                await asyncio.sleep(1)

        raise RuntimeError(f"Failed to connect to PostgreSQL at {self._database_url}") from last_error

    async def close(self) -> None:
        if self._pool is None:
            return
        pool = self._pool
        self._pool = None
        await asyncio.to_thread(pool.close)

    async def save_run(self, run: ResearchRun) -> ResearchRun:
        async with self._lock:
            await asyncio.to_thread(self._upsert_run_sync, run)
            return run.model_copy(deep=True)

    async def replace_run(self, run: ResearchRun) -> ResearchRun:
        async with self._lock:
            await asyncio.to_thread(self._upsert_run_sync, run)
            return run.model_copy(deep=True)

    async def get_run(self, run_id: str) -> ResearchRun | None:
        return await asyncio.to_thread(self._get_run_sync, run_id)

    async def list_runs(self) -> list[ResearchRun]:
        return await asyncio.to_thread(self._list_runs_sync)

    async def save_plan_nodes(self, run_id: str, nodes: list[ResearchPlanNode]) -> list[ResearchPlanNode]:
        async with self._lock:
            await asyncio.to_thread(self._replace_rows_sync, "research_plan_nodes", run_id, nodes)
            return [node.model_copy(deep=True) for node in nodes]

    async def list_plan_nodes(self, run_id: str) -> list[ResearchPlanNode]:
        return await asyncio.to_thread(self._list_rows_sync, "research_plan_nodes", run_id, ResearchPlanNode)

    async def save_step(self, step: RunStep) -> RunStep:
        await asyncio.to_thread(self._upsert_row_sync, "research_steps", step.run_id, step.id, step.created_at, step)
        return step.model_copy(deep=True)

    async def list_steps(self, run_id: str) -> list[RunStep]:
        return await asyncio.to_thread(self._list_rows_sync, "research_steps", run_id, RunStep)

    async def replace_sources(self, run_id: str, sources: list[SourceDocument]) -> list[SourceDocument]:
        async with self._lock:
            await asyncio.to_thread(self._replace_rows_sync, "research_sources", run_id, sources)
            await self._sync_run_counts(run_id, source_delta=len(sources))
            return [source.model_copy(deep=True) for source in sources]

    async def list_sources(self, run_id: str) -> list[SourceDocument]:
        return await asyncio.to_thread(self._list_rows_sync, "research_sources", run_id, SourceDocument)

    async def list_all_sources(self, limit: int = 50) -> list[SourceDocument]:
        return await asyncio.to_thread(self._list_all_rows_sync, "research_sources", SourceDocument, limit)

    async def replace_citations(self, run_id: str, citations: list[Citation]) -> list[Citation]:
        async with self._lock:
            await asyncio.to_thread(self._replace_rows_sync, "research_citations", run_id, citations)
            await self._sync_run_counts(run_id, citation_delta=len(citations))
            return [citation.model_copy(deep=True) for citation in citations]

    async def list_citations(self, run_id: str) -> list[Citation]:
        return await asyncio.to_thread(self._list_rows_sync, "research_citations", run_id, Citation)

    async def save_report(self, report: FinalReport) -> FinalReport:
        await asyncio.to_thread(
            self._upsert_row_sync,
            "research_reports",
            report.run_id,
            report.run_id,
            report.created_at,
            report,
        )
        run = await self.get_run(report.run_id)
        if run:
            run.report_ready = True
            await self.replace_run(run)
        return report.model_copy(deep=True)

    async def get_report(self, run_id: str) -> FinalReport | None:
        return await asyncio.to_thread(self._get_row_sync, "research_reports", run_id, run_id, FinalReport)

    async def clear_run_outputs(
        self,
        run_id: str,
        *,
        clear_plan: bool = False,
        clear_sources: bool = True,
        clear_citations: bool = True,
        clear_report: bool = True,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._delete_run_bundle_sync,
                run_id,
                clear_plan,
                clear_sources,
                clear_citations,
                clear_report,
            )
            run = self._get_run_sync(run_id)
            if run:
                if clear_sources:
                    run.source_count = 0
                if clear_citations:
                    run.citation_count = 0
                if clear_report:
                    run.report_ready = False
                await asyncio.to_thread(self._upsert_run_sync, run)

    async def bind_task(self, run_id: str, task: asyncio.Task[None]) -> None:
        async with self._lock:
            self._tasks[run_id] = task

    async def pop_task(self, run_id: str) -> asyncio.Task[None] | None:
        async with self._lock:
            return self._tasks.pop(run_id, None)

    async def _sync_run_counts(self, run_id: str, *, source_delta: int | None = None, citation_delta: int | None = None) -> None:
        run = self._get_run_sync(run_id)
        if not run:
            return
        if source_delta is not None:
            run.source_count = source_delta
        if citation_delta is not None:
            run.citation_count = citation_delta
        await asyncio.to_thread(self._upsert_run_sync, run)

    def _open_pool(self) -> ConnectionPool:
        pool = ConnectionPool(
            conninfo=self._database_url,
            min_size=1,
            max_size=5,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        pool.wait()
        return pool

    def _ensure_schema_sync(self) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_runs (
                        id TEXT PRIMARY KEY,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        status TEXT NOT NULL,
                        payload JSONB NOT NULL
                    )
                    """
                )
                for table in (
                    "research_plan_nodes",
                    "research_steps",
                    "research_sources",
                    "research_citations",
                ):
                    cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {table} (
                            id TEXT PRIMARY KEY,
                            run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
                            created_at TIMESTAMPTZ NOT NULL,
                            payload JSONB NOT NULL
                        )
                        """
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_run_created ON {table} (run_id, created_at)"
                    )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_reports (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL UNIQUE REFERENCES research_runs(id) ON DELETE CASCADE,
                        created_at TIMESTAMPTZ NOT NULL,
                        payload JSONB NOT NULL
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_research_runs_created ON research_runs (created_at DESC)")

    def _upsert_run_sync(self, run: ResearchRun) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO research_runs (id, created_at, updated_at, status, payload)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET updated_at = EXCLUDED.updated_at,
                        status = EXCLUDED.status,
                        payload = EXCLUDED.payload
                    """,
                    (
                        run.id,
                        run.created_at,
                        utc_now(),
                        run.status.value,
                        Jsonb(run.model_dump(mode="json")),
                    ),
                )

    def _get_run_sync(self, run_id: str) -> ResearchRun | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT payload FROM research_runs WHERE id = %s", (run_id,))
                row = cursor.fetchone()
        if not row:
            return None
        return ResearchRun.model_validate(self._decode_payload(row["payload"]))

    def _list_runs_sync(self) -> list[ResearchRun]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT payload FROM research_runs ORDER BY created_at DESC")
                rows = cursor.fetchall()
        return [ResearchRun.model_validate(self._decode_payload(row["payload"])) for row in rows]

    def _upsert_row_sync(self, table: str, run_id: str, row_id: str, created_at: Any, model: Any) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {table} (id, run_id, created_at, payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET created_at = EXCLUDED.created_at,
                        payload = EXCLUDED.payload
                    """,
                    (row_id, run_id, created_at, Jsonb(model.model_dump(mode="json"))),
                )

    def _replace_rows_sync(self, table: str, run_id: str, rows: list[Any]) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE run_id = %s", (run_id,))
                for row in rows:
                    cursor.execute(
                        f"INSERT INTO {table} (id, run_id, created_at, payload) VALUES (%s, %s, %s, %s)",
                        (row.id, run_id, row.created_at, Jsonb(row.model_dump(mode="json"))),
                    )

    def _get_row_sync(self, table: str, run_id: str, row_id: str, model_type: Any) -> Any:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT payload FROM {table} WHERE run_id = %s AND id = %s",
                    (run_id, row_id),
                )
                row = cursor.fetchone()
        if not row:
            return None
        return model_type.model_validate(self._decode_payload(row["payload"]))

    def _list_rows_sync(self, table: str, run_id: str, model_type: Any) -> list[Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT payload FROM {table} WHERE run_id = %s ORDER BY created_at ASC",
                    (run_id,),
                )
                rows = cursor.fetchall()
        return [model_type.model_validate(self._decode_payload(row["payload"])) for row in rows]

    def _list_all_rows_sync(self, table: str, model_type: Any, limit: int) -> list[Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT payload FROM {table} ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [model_type.model_validate(self._decode_payload(row["payload"])) for row in rows]

    def _delete_run_bundle_sync(
        self,
        run_id: str,
        clear_plan: bool,
        clear_sources: bool,
        clear_citations: bool,
        clear_report: bool,
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                if clear_sources:
                    cursor.execute("DELETE FROM research_sources WHERE run_id = %s", (run_id,))
                if clear_citations:
                    cursor.execute("DELETE FROM research_citations WHERE run_id = %s", (run_id,))
                if clear_report:
                    cursor.execute("DELETE FROM research_reports WHERE run_id = %s", (run_id,))
                if clear_plan:
                    cursor.execute("DELETE FROM research_plan_nodes WHERE run_id = %s", (run_id,))

    def _decode_payload(self, payload: Any) -> Any:
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    def _connection(self):
        if self._pool is None:
            raise RuntimeError("PostgreSQL store has not been initialized")
        return self._pool.connection()
