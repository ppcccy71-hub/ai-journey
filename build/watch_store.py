#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自选股与异动告警的存储。"""
import os
import sqlite3
import time
from pathlib import Path

DB = Path(os.environ.get("ASSISTANT_DB") or (Path(__file__).resolve().parent / "assistant.db"))


def connect():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            rule TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            change_pct REAL NOT NULL,
            analysis TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            ack INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)")


def add(symbol: str, name: str = ""):
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO watchlist(symbol,name,created_at) VALUES(?,?,?)",
                     (symbol, name, time.time()))


def remove(symbol: str):
    with connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))


def list_watch():
    with connect() as conn:
        rows = conn.execute("SELECT symbol,name,created_at FROM watchlist ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def update_name(symbol: str, name: str):
    with connect() as conn:
        conn.execute("UPDATE watchlist SET name=? WHERE symbol=?", (name, symbol))


def last_alert_at(symbol: str, rule: str):
    with connect() as conn:
        row = conn.execute("SELECT created_at FROM alerts WHERE symbol=? AND rule=? ORDER BY id DESC LIMIT 1",
                           (symbol, rule)).fetchone()
    return row[0] if row else 0.0


def add_alert(symbol, name, rule, title, price, change_pct, analysis):
    with connect() as conn:
        cur = conn.execute("""INSERT INTO alerts(symbol,name,rule,title,price,change_pct,analysis,created_at)
                              VALUES(?,?,?,?,?,?,?,?)""",
                           (symbol, name, rule, title, price, change_pct, analysis, time.time()))
        return cur.lastrowid


def list_alerts(limit=50):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def ack(alert_id: int):
    with connect() as conn:
        conn.execute("UPDATE alerts SET ack=1 WHERE id=?", (alert_id,))


def count_today():
    start = time.time() - 86400
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM alerts WHERE created_at>?", (start,)).fetchone()
    return row[0]
