#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step16：存储层（SQLite）。

三张表：
    sessions   会话（id、标题、时间）
    messages   消息（属于哪个会话、角色、内容）
    usage_log  每次调用的成本与耗时（用于统计）
"""
import os
import sqlite3
import time
import uuid
from pathlib import Path

# 默认放在代码目录，Docker 里用环境变量指到挂载卷
DB = Path(os.environ.get("ASSISTANT_DB") or (Path(__file__).resolve().parent / "assistant.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '新会话',
    user_id     INTEGER NOT NULL DEFAULT 0,
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
    user_id     INTEGER NOT NULL DEFAULT 0,
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


def _ensure_column(conn, table, column, ddl):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "sessions", "user_id", "user_id INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "usage_log", "user_id", "user_id INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_log(user_id)")


def new_session(title="新会话", user_id=0):
    sid = uuid.uuid4().hex[:12]
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions(id, title, user_id, created_at, updated_at) VALUES(?,?,?,?,?)",
            (sid, title, user_id, now, now),
        )
    return sid


def ensure_session(sid, title="新会话", user_id=0):
    """会话不存在就创建；已存在则什么都不做。"""
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions(id, title, user_id, created_at, updated_at) VALUES(?,?,?,?,?)",
            (sid, title, user_id, now, now),
        )
    return sid


def list_sessions(limit=50, user_id=0):
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title, s.updated_at,
                      (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
               FROM sessions s WHERE s.user_id=? ORDER BY s.updated_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def owns_session(sid, user_id):
    with connect() as conn:
        row = conn.execute("SELECT user_id FROM sessions WHERE id=?", (sid,)).fetchone()
    return bool(row) and row[0] == user_id


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


def delete_session(sid, user_id=0):
    with connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        cur = conn.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (sid, user_id))
    return cur.rowcount > 0


def log_usage(sid, kind, tokens_in=0, tokens_out=0, cost=0.0, latency_ms=0, user_id=0):
    with connect() as conn:
        conn.execute(
            """INSERT INTO usage_log(session_id, user_id, kind, tokens_in, tokens_out, cost, latency_ms, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (sid, user_id, kind, tokens_in, tokens_out, cost, latency_ms, time.time()),
        )


def stats(user_id=0):
    with connect() as conn:
        sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id=?", (user_id,)).fetchone()[0]
        messages = conn.execute(
            "SELECT COUNT(*) FROM messages m JOIN sessions s ON s.id=m.session_id WHERE s.user_id=?",
            (user_id,)).fetchone()[0]
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0),"
            " COALESCE(SUM(cost),0), COALESCE(AVG(latency_ms),0) FROM usage_log WHERE user_id=?",
            (user_id,),
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


def daily_stats(days=7, user_id=0):
    """最近 N 天，每天的问答次数、token、成本。"""
    since = time.time() - days * 86400
    with connect() as conn:
        rows = conn.execute(
            """SELECT date(created_at, 'unixepoch', 'localtime') AS day,
                      COUNT(*) AS queries,
                      COALESCE(SUM(tokens_in + tokens_out), 0) AS tokens,
                      COALESCE(SUM(cost), 0) AS cost
               FROM usage_log
               WHERE created_at >= ? AND user_id = ?
               GROUP BY day ORDER BY day""",
            (since, user_id),
        ).fetchall()
    return [{"day": r["day"], "queries": r["queries"],
             "tokens": r["tokens"], "cost": round(r["cost"], 6)} for r in rows]


init()