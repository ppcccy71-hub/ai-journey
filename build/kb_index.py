#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多知识库的索引：每个库一个 vectors JSON，支持上传文档后增量追加。"""
import json
import os
import threading
import time
from pathlib import Path

import ingest_docs as ing
import rerank
import step8_embed as s8
import step9_vector as s9

ROOT = Path(__file__).resolve().parent
KB_DIR = Path(os.environ.get("KB_DIR") or (ROOT / "data" / "kbs"))
KB_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SOURCE = ROOT / "vectors.json"
EMBED_MODEL = s8.MODEL
LOCK = threading.Lock()
CACHE = {}


def path_of(kb_id: str) -> Path:
    return KB_DIR / f"{kb_id}.json"


def ensure_default(kb_id: str = "fastapi", name: str = "FastAPI 官方文档"):
    """内置知识库：每次启动从镜像里的 vectors.json 强制恢复，保证只读且不被污染。"""
    import kb_store

    target = path_of(kb_id)
    if DEFAULT_SOURCE.exists():
        target.write_bytes(DEFAULT_SOURCE.read_bytes())
    if not target.exists():
        return
    data = load(kb_id)
    if kb_store.get_kb(kb_id) is None:
        with kb_store.connect() as conn:
            conn.execute(
                "INSERT INTO kbs(id,name,created_at,chunk_count,doc_count) VALUES(?,?,?,?,?)",
                (kb_id, name, time.time(), len(data["chunks"]),
                 len({c["source"] for c in data["chunks"]})),
            )
    # 把内置文档记录补进 kb_docs，避免上传后统计被覆盖
    with kb_store.connect() as conn:
        existing = {r[0] for r in conn.execute(
            "SELECT filename FROM kb_docs WHERE kb_id=?", (kb_id,)).fetchall()}
        counts = {}
        for c in data["chunks"]:
            counts[c["source"]] = counts.get(c["source"], 0) + 1
        for src, cnt in counts.items():
            if src not in existing:
                conn.execute(
                    "INSERT OR IGNORE INTO kb_docs(kb_id,filename,chunks,created_at) VALUES(?,?,?,?)",
                    (kb_id, src, cnt, time.time()))
    kb_store.update_kb(kb_id, chunk_count=len(data["chunks"]), doc_count=len(counts))


def load(kb_id: str):
    p = path_of(kb_id)
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    cached = CACHE.get(kb_id)
    if cached and cached[0] == mtime:
        return cached[1]
    data = json.loads(p.read_text(encoding="utf-8"))
    CACHE[kb_id] = (mtime, data)
    return data


def save(kb_id: str, chunks, model=EMBED_MODEL, dim=1024):
    p = path_of(kb_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"model": model, "dim": dim, "chunks": chunks},
                              ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    CACHE.pop(kb_id, None)


def chunk_text(text: str, filename: str):
    """复用 ingest_docs 的清洗与切块逻辑。"""
    cleaned = ing.clean_text(text)
    chunks = []
    for h1, h2, body in ing.split_sections(cleaned):
        head = f"{h1} / {h2}" if h2 else h1
        if len(body) < 20:          # 上传的短文档也要能进库
            continue
        for piece in ing.split_long(body, 700, 120):
            chunks.append({"text": f"{head}\n\n{piece}", "source": filename,
                           "title": head, "kind": "prose"})
    if not chunks and cleaned:      # 没有标题结构的纯文本兜底
        for piece in ing.split_long(cleaned, 700, 120):
            chunks.append({"text": piece, "source": filename,
                           "title": filename, "kind": "prose"})
    return chunks


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    raw = path.read_bytes()
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def ingest(kb_id: str, filename: str, text: str):
    """切块 → 向量化 → 追加到该库（同文件名会先移除旧块）。"""
    import kb_store

    kb_store.update_kb(kb_id, status="indexing", message=f"正在索引 {filename}")
    try:
        chunks = chunk_text(text, filename)
        if not chunks:
            kb_store.update_kb(kb_id, status="ready", message="文件内容为空或过短")
            return
        for start in range(0, len(chunks), 10):
            batch = chunks[start:start + 10]
            vecs, _ = s8.embed([c["text"] for c in batch], EMBED_MODEL)
            for c, v in zip(batch, vecs):
                c["vector"] = [round(x, 6) for x in v]

        with LOCK:
            data = load(kb_id) or {"model": EMBED_MODEL, "dim": 1024, "chunks": []}
            kept = [c for c in data["chunks"] if c.get("source") != filename]
            save(kb_id, kept + chunks)

        kb_store.upsert_doc(kb_id, filename, len(chunks))
        kb_store.update_kb(kb_id, status="ready", message=f"{filename}：{len(chunks)} 块")
    except Exception as exc:
        kb_store.update_kb(kb_id, status="error", message=f"{type(exc).__name__}: {exc}")


def ingest_file(kb_id: str, path: Path, display_name: str | None = None):
    try:
        text = read_file(path)
        ingest(kb_id, display_name or path.name, text)
    finally:
        path.unlink(missing_ok=True)


def delete_doc(kb_id: str, filename: str):
    import kb_store

    with LOCK:
        data = load(kb_id)
        if not data:
            return
        kept = [c for c in data["chunks"] if c.get("source") != filename]
        save(kb_id, kept)
    with kb_store.connect() as conn:
        conn.execute("DELETE FROM kb_docs WHERE kb_id=? AND filename=?", (kb_id, filename))
        docs = conn.execute("SELECT COUNT(*), COALESCE(SUM(chunks),0) FROM kb_docs WHERE kb_id=?",
                            (kb_id,)).fetchone()
    kb_store.update_kb(kb_id, doc_count=docs[0], chunk_count=docs[1])


def total_chunks():
    """把全部知识库的块合并，用于默认的“全部库”检索。

    前提：所有库用同一个 embedding 模型（当前都是 text-embedding-v3）。
    """
    import kb_store

    merged = []
    for kb in kb_store.list_kbs():
        data = load(kb["id"])
        if not data:
            continue
        for c in data["chunks"]:
            item = dict(c)
            item["source"] = f'{kb["name"]} / {c["source"]}'
            item["kb"] = kb["id"]
            merged.append(item)
    return merged


def search(kb_id: str, question: str, top_k=5, mode="quality", use_translate=True):
    if kb_id == "all":
        chunks, model = total_chunks(), EMBED_MODEL
    else:
        data = load(kb_id)
        if not data or not data["chunks"]:
            return [], 0.0
        chunks, model = data["chunks"], (data.get("model") or EMBED_MODEL)
    if not chunks:
        return [], 0.0

    depth = 20 if mode == "quality" else top_k
    cand = s9.search_plus(question, chunks, model, depth, use_translate)
    best = cand[0][0] if cand else 0.0
    if mode == "quality" and cand:
        hits = rerank.rerank(question, cand, top_k)
    else:
        hits = cand[:top_k]
    return hits, best
