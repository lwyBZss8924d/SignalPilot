# Copyright 2026 SignalPilot. All rights reserved.
"""Durable storage for agent chat traces."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from signalpilot._server.api.deps import AppStateBase

ChatSource = Literal["user", "notion"]
ThreadStatus = Literal["active", "done", "failed"]


@dataclass(frozen=True)
class ChatThread:
    thread_id: str
    session_id: str
    source: ChatSource
    title: str = ""
    status: ThreadStatus = "active"
    notebook_path: str = ""
    notion_request_page_id: str | None = None
    notion_discussion_id: str | None = None
    metadata: dict[str, Any] | None = None


def chat_store_path_for_app(app_state: AppStateBase) -> Path:
    workspace = app_state.session_manager.workspace
    root = workspace.directory
    if root is None:
        single_file = workspace.single_file()
        if single_file is not None:
            root = str(Path(single_file.path).parent)
    root_path = Path(root) if root is not None else Path.cwd()
    return root_path / "__sp__" / "chat.sqlite"


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, default=str)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class ChatTraceStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                thread_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                notebook_path TEXT NOT NULL DEFAULT '',
                notion_request_page_id TEXT,
                notion_discussion_id TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_events (
                thread_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                role TEXT,
                content TEXT NOT NULL DEFAULT '',
                tool_name TEXT NOT NULL DEFAULT '',
                tool_input_json TEXT,
                tool_call_id TEXT NOT NULL DEFAULT '',
                is_error INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL,
                turn INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                metadata_json TEXT,
                PRIMARY KEY (thread_id, idx),
                FOREIGN KEY (thread_id) REFERENCES chat_threads(thread_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chat_threads_session
                ON chat_threads(session_id);
            CREATE INDEX IF NOT EXISTS idx_chat_events_thread_idx
                ON chat_events(thread_id, idx);
            """
        )

    def upsert_thread(self, thread: ChatThread) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_threads (
                    thread_id, session_id, source, title, status, notebook_path,
                    notion_request_page_id, notion_discussion_id, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    source = excluded.source,
                    title = CASE
                        WHEN excluded.title != '' THEN excluded.title
                        ELSE chat_threads.title
                    END,
                    status = excluded.status,
                    notebook_path = CASE
                        WHEN excluded.notebook_path != '' THEN excluded.notebook_path
                        ELSE chat_threads.notebook_path
                    END,
                    notion_request_page_id = COALESCE(
                        excluded.notion_request_page_id,
                        chat_threads.notion_request_page_id
                    ),
                    notion_discussion_id = COALESCE(
                        excluded.notion_discussion_id,
                        chat_threads.notion_discussion_id
                    ),
                    metadata_json = COALESCE(
                        excluded.metadata_json,
                        chat_threads.metadata_json
                    ),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (
                    thread.thread_id,
                    thread.session_id,
                    thread.source,
                    thread.title,
                    thread.status,
                    thread.notebook_path,
                    thread.notion_request_page_id,
                    thread.notion_discussion_id,
                    _dumps(thread.metadata),
                ),
            )

    def clear_events(self, thread_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_events WHERE thread_id = ?", (thread_id,))
            conn.execute(
                """
                UPDATE chat_threads
                SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE thread_id = ?
                """,
                (thread_id,),
            )

    def append_event(
        self,
        thread_id: str,
        event: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(idx), -1) + 1 AS next_idx "
                "FROM chat_events WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            idx = int(row["next_idx"])
            conn.execute(
                """
                INSERT INTO chat_events (
                    thread_id, idx, event_type, role, content, tool_name,
                    tool_input_json, tool_call_id, is_error, cost_usd, turn,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    idx,
                    str(event.get("type", "")),
                    event.get("role"),
                    str(event.get("content", "") or ""),
                    str(event.get("tool_name", "") or ""),
                    _dumps(event.get("tool_input")),
                    str(event.get("tool_call_id", "") or ""),
                    1 if event.get("is_error") else 0,
                    event.get("cost_usd"),
                    int(event.get("turn", 0) or 0),
                    _dumps(metadata or event.get("metadata")),
                ),
            )
            conn.execute(
                """
                UPDATE chat_threads
                SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE thread_id = ?
                """,
                (thread_id,),
            )
            return idx

    def get_events(
        self, thread_id: str, after_index: int = -1
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT idx, event_type, role, content, tool_name,
                    tool_input_json, tool_call_id, is_error, cost_usd, turn,
                    metadata_json, created_at
                FROM chat_events
                WHERE thread_id = ? AND idx > ?
                ORDER BY idx ASC
                """,
                (thread_id, after_index),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            event = {
                "idx": row["idx"],
                "type": row["event_type"],
                "content": row["content"],
                "tool_name": row["tool_name"],
                "tool_input": _loads(row["tool_input_json"], None),
                "tool_call_id": row["tool_call_id"],
                "is_error": bool(row["is_error"]),
                "cost_usd": row["cost_usd"],
                "turn": row["turn"],
                "created_at": row["created_at"],
            }
            if row["role"]:
                event["role"] = row["role"]
            metadata = _loads(row["metadata_json"], None)
            if metadata is not None:
                event["metadata"] = metadata
            events.append(event)
        return events

    def list_threads(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT thread_id, session_id, source, title, status,
                    notebook_path, notion_request_page_id,
                    notion_discussion_id, created_at, updated_at,
                    metadata_json
                FROM chat_threads
                WHERE session_id = ?
                ORDER BY updated_at DESC
                LIMIT 100
                """,
                (session_id,),
            ).fetchall()
        return [self._thread_row(row) for row in rows]

    def list_threads_by_source(
        self, source: ChatSource, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT thread_id, session_id, source, title, status,
                    notebook_path, notion_request_page_id,
                    notion_discussion_id, created_at, updated_at,
                    metadata_json
                FROM chat_threads
                WHERE source = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (source, limit),
            ).fetchall()
        return [self._thread_row(row) for row in rows]

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT thread_id, session_id, source, title, status,
                    notebook_path, notion_request_page_id,
                    notion_discussion_id, created_at, updated_at,
                    metadata_json
                FROM chat_threads
                WHERE thread_id = ?
                """,
                (thread_id,),
            ).fetchone()
        if row is None:
            return None
        return self._thread_row(row)

    @staticmethod
    def _thread_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "thread_id": row["thread_id"],
            "session_id": row["session_id"],
            "source": row["source"],
            "title": row["title"],
            "status": row["status"],
            "notebook_path": row["notebook_path"],
            "notion_request_page_id": row["notion_request_page_id"],
            "notion_discussion_id": row["notion_discussion_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": _loads(row["metadata_json"], {}),
        }


def get_chat_trace_store(db_path: Path | str) -> ChatTraceStore:
    return ChatTraceStore(db_path)
