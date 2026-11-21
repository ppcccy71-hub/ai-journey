#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step16：存储层（SQLite）。

三张表：
    sessions   会话（id、标题、时间）
    messages   消息（属于哪个会话、角色、内容）
    usage_log  每次调用的成本与耗时（用于统计）
"""
import sqlite3
import time
import uuid
from pathlib import Path

DB = Path(__file__).resolve().parent / "assistant.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '新会话',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    kind        TEXT NOT NULL,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    cost        REAL DEFAULT 0,
    latency_ms  INTEGER DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_log(created_at);
"""


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)


def new_session(title="新会话"):
    sid = uuid.uuid4().hex[:12]
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions(id, title, created_at, updated_at) VALUES(?,?,?,?)",
            (sid, title, now, now),
        )
    return sid


def ensure_session(sid, title="新会话"):
    """会话不存在就创建；已存在则什么都不做。"""
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions(id, title, created_at, updated_at) VALUES(?,?,?,?)",
            (sid, title, now, now),
        )
    return sid


def list_sessions(limit=50):
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title, s.updated_at,
                      (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
               FROM sessions s ORDER BY s.updated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def touch_session(sid):
    with connect() as conn:
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (time.time(), sid))


def add_message(sid, role, content):
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
            (sid, role, content, now),
        )
    touch_session(sid)


def get_messages(sid, limit=200):
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id LIMIT ?",
            (sid, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_session(sid):
    with connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    return cur.rowcount > 0


def log_usage(sid, kind, tokens_in=0, tokens_out=0, cost=0.0, latency_ms=0):
    with connect() as conn:
        conn.execute(
            """INSERT INTO usage_log(session_id, kind, tokens_in, tokens_out, cost, latency_ms, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (sid, kind, tokens_in, tokens_out, cost, latency_ms, time.time()),
        )


def stats():
    with connect() as conn:
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0),"
            " COALESCE(SUM(cost),0), COALESCE(AVG(latency_ms),0) FROM usage_log"
        ).fetchone()
        return {
            "sessions": sessions,
            "messages": messages,
            "queries": row[0],
            "tokens_in": row[1],
            "tokens_out": row[2],
            "total_cost": round(row[3], 6),
            "avg_latency_ms": int(row[4]),
        }


def daily_stats(days=7):
    """最近 N 天，每天的问答次数、token、成本。"""
    since = time.time() - days * 86400
    with connect() as conn:
        rows = conn.execute(
            """SELECT date(created_at, 'unixepoch', 'localtime') AS day,
                      COUNT(*) AS queries,
                      COALESCE(SUM(tokens_in + tokens_out), 0) AS tokens,
                      COALESCE(SUM(cost), 0) AS cost
               FROM usage_log
               WHERE created_at >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()
    return [{"day": r["day"], "queries": r["queries"],
             "tokens": r["tokens"], "cost": round(r["cost"], 6)} for r in rows]


init()