#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库元数据存储（SQLite）。

kbs     ：知识库基本信息与索引状态
kb_docs ：每个库里的文档与块数
向量文件本身按库存在 data/kbs/{kb_id}.json。
"""
import os
import sqlite3
import time
import uuid
from pathlib import Path

DB = Path(os.environ.get("ASSISTANT_DB") or (Path(__file__).resolve().parent / "assistant.db"))
DEFAULT_KB = "fastapi"


def connect():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS kbs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            message TEXT NOT NULL DEFAULT '',
            chunk_count INTEGER NOT NULL DEFAULT 0,
            doc_count INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS kb_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            chunks INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            UNIQUE(kb_id, filename)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kbdocs_kb ON kb_docs(kb_id)")


def new_id(name: str) -> str:
    ascii_slug = "".join(c for c in name.lower() if c.isalnum() or c == "-")[:20]
    return ascii_slug or uuid.uuid4().hex[:8]


def create_kb(name: str) -> dict:
    kb_id = new_id(name)
    with connect() as conn:
        exists = conn.execute("SELECT id FROM kbs WHERE id=?", (kb_id,)).fetchone()
        if exists:
            kb_id = uuid.uuid4().hex[:8]
        conn.execute("INSERT INTO kbs(id,name,created_at) VALUES(?,?,?)", (kb_id, name, time.time()))
    return get_kb(kb_id)


def get_kb(kb_id: str):
    with connect() as conn:
        row = conn.execute("SELECT * FROM kbs WHERE id=?", (kb_id,)).fetchone()
    return dict(row) if row else None


def list_kbs():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM kbs ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def update_kb(kb_id: str, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with connect() as conn:
        conn.execute(f"UPDATE kbs SET {cols} WHERE id=?", (*fields.values(), kb_id))


def delete_kb(kb_id: str):
    with connect() as conn:
        conn.execute("DELETE FROM kbs WHERE id=?", (kb_id,))
        conn.execute("DELETE FROM kb_docs WHERE kb_id=?", (kb_id,))


def upsert_doc(kb_id: str, filename: str, chunks: int):
    with connect() as conn:
        conn.execute("""INSERT INTO kb_docs(kb_id,filename,chunks,created_at) VALUES(?,?,?,?)
                        ON CONFLICT(kb_id,filename) DO UPDATE SET chunks=excluded.chunks,
                        created_at=excluded.created_at""",
                     (kb_id, filename, chunks, time.time()))
        docs = conn.execute("SELECT COUNT(*), COALESCE(SUM(chunks),0) FROM kb_docs WHERE kb_id=?",
                            (kb_id,)).fetchone()
    update_kb(kb_id, doc_count=docs[0], chunk_count=docs[1])


def list_docs(kb_id: str):
    with connect() as conn:
        rows = conn.execute("SELECT filename,chunks,created_at FROM kb_docs WHERE kb_id=? ORDER BY created_at",
                            (kb_id,)).fetchall()
    return [dict(r) for r in rows]
