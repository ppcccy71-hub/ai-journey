#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自选股与异动告警的存储（按用户隔离）。"""
import os
import sqlite3
import time
from pathlib import Path

DB = Path(os.environ.get("ASSISTANT_DB") or (Path(__file__).resolve().parent / "assistant.db"))


def connect():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def init():
    with connect() as conn:
        cols = _columns(conn, "watchlist")
        if not cols:
            conn.execute("""CREATE TABLE watchlist (
                symbol TEXT NOT NULL,
                user_id INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                PRIMARY KEY(symbol, user_id)
            )""")
        elif "user_id" not in cols:
            conn.execute("""CREATE TABLE watchlist_v2 (
                symbol TEXT NOT NULL,
                user_id INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                PRIMARY KEY(symbol, user_id)
            )""")
            conn.execute("INSERT INTO watchlist_v2(symbol,user_id,name,created_at) "
                         "SELECT symbol,0,name,created_at FROM watchlist")
            conn.execute("DROP TABLE watchlist")
            conn.execute("ALTER TABLE watchlist_v2 RENAME TO watchlist")

        conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            user_id INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL,
            rule TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            change_pct REAL NOT NULL,
            analysis TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            ack INTEGER NOT NULL DEFAULT 0
        )""")
        if "user_id" not in _columns(conn, "alerts"):
            conn.execute("ALTER TABLE alerts ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id, created_at DESC)")


def add(symbol: str, name: str = "", user_id: int = 0):
    with connect() as conn:
        conn.execute("INSERT INTO watchlist(symbol,user_id,name,created_at) VALUES(?,?,?,?)",
                     (symbol, user_id, name, time.time()))


def remove(symbol: str, user_id: int = 0):
    with connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE symbol=? AND user_id=?", (symbol, user_id))


def list_watch(user_id=None):
    with connect() as conn:
        if user_id is None:
            rows = conn.execute("SELECT symbol,user_id,name,created_at FROM watchlist ORDER BY created_at").fetchall()
        else:
            rows = conn.execute("SELECT symbol,user_id,name,created_at FROM watchlist "
                                "WHERE user_id=? ORDER BY created_at", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def update_name(symbol: str, name: str):
    with connect() as conn:
        conn.execute("UPDATE watchlist SET name=? WHERE symbol=?", (name, symbol))


def last_alert_at(symbol: str, rule: str, user_id: int = 0):
    with connect() as conn:
        row = conn.execute("SELECT created_at FROM alerts WHERE symbol=? AND rule=? AND user_id=? "
                           "ORDER BY id DESC LIMIT 1", (symbol, rule, user_id)).fetchone()
    return row[0] if row else 0.0


def add_alert(symbol, name, rule, title, price, change_pct, analysis, user_id: int = 0):
    with connect() as conn:
        cur = conn.execute("""INSERT INTO alerts(symbol,user_id,name,rule,title,price,change_pct,analysis,created_at)
                              VALUES(?,?,?,?,?,?,?,?,?)""",
                           (symbol, user_id, name, rule, title, price, change_pct, analysis, time.time()))
        return cur.lastrowid


def list_alerts(limit=50, user_id=0):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT ?",
                            (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def ack(alert_id: int, user_id: int = 0):
    with connect() as conn:
        conn.execute("UPDATE alerts SET ack=1 WHERE id=? AND user_id=?", (alert_id, user_id))


def count_today(user_id: int = 0):
    start = time.time() - 86400
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM alerts WHERE created_at>? AND user_id=?",
                           (start, user_id)).fetchone()
    return row[0]
