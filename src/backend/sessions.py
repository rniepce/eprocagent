"""Helpers for persisting chat conversations and listing past sessions."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.utils.db import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


async def save_message(
    session_id: str,
    role: str,
    content: str,
    sources: Optional[list[dict]] = None,
    structured: Optional[dict] = None,
    title: Optional[str] = None,
) -> None:
    """Persist a single chat message under a given session."""
    if not session_id:
        return
    conn = await get_db_connection()
    try:
        await conn.execute(
            """INSERT INTO conversations (session_id, role, content, sources, structured, title)
               VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)""",
            session_id,
            role,
            content[:20000],
            json.dumps(sources) if sources else None,
            json.dumps(structured) if structured else None,
            title,
        )
    except Exception as e:
        logger.warning(f"save_message failed (session={session_id}, role={role}): {e}")
    finally:
        await release_db_connection(conn)


async def fetch_history(session_id: str, limit: int = 6) -> list[dict[str, Any]]:
    """Return the last N messages of the session, oldest first."""
    if not session_id:
        return []
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """SELECT role, content
               FROM (
                 SELECT id, role, content
                 FROM conversations
                 WHERE session_id = $1
                 ORDER BY id DESC
                 LIMIT $2
               ) t
               ORDER BY id ASC""",
            session_id,
            limit,
        )
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    finally:
        await release_db_connection(conn)


async def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """Return distinct sessions with their first user message, last activity and count."""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """SELECT session_id,
                      MAX(created_at) AS last_at,
                      COUNT(*) AS msg_count,
                      COALESCE(
                        (
                          SELECT content
                          FROM conversations c2
                          WHERE c2.session_id = c.session_id AND c2.role = 'user'
                          ORDER BY c2.id ASC
                          LIMIT 1
                        ),
                        '(sem título)'
                      ) AS title
               FROM conversations c
               WHERE session_id IS NOT NULL AND session_id <> ''
               GROUP BY session_id
               ORDER BY last_at DESC
               LIMIT $1""",
            limit,
        )
        return [
            {
                "session_id": r["session_id"],
                "title": (r["title"] or "")[:120],
                "msg_count": r["msg_count"],
                "last_at": r["last_at"].isoformat() if r["last_at"] else None,
            }
            for r in rows
        ]
    finally:
        await release_db_connection(conn)


async def fetch_session_messages(session_id: str) -> list[dict[str, Any]]:
    """Return the full message list of a session in chronological order."""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """SELECT id, role, content, sources, structured, created_at
               FROM conversations
               WHERE session_id = $1
               ORDER BY id ASC""",
            session_id,
        )
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "sources": json.loads(r["sources"]) if r["sources"] else None,
                "structured": json.loads(r["structured"]) if r["structured"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            })
        return out
    finally:
        await release_db_connection(conn)
