#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 FastAPI 官方文档接入知识库。

处理三类干扰：frontmatter、{!...!} 引用、/// 指令与代码块。
按 H2 切节，超长的节再按段落拆。

用法：
    python ingest_docs.py --dry-run     # 只统计
    python ingest_docs.py               # 生成 vectors.json（支持断点续传）
"""
import argparse
import json
import re
import shutil
import time
import urllib.error
from pathlib import Path

DOCS_DIR = Path(r"C:\Users\20647\Desktop\AI_WorkPlace\fastapi-docs\docs\en\docs")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "vectors.json"
BACKUP = ROOT / "vectors_demo.json"
PARTIAL = ROOT / "vectors_partial.json"

FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)
CODE_BLOCK = re.compile(r"```.*?```", re.S)
INCLUDE = re.compile(r"^\{!.*?!\}\s*$", re.M)
DIRECTIVE = re.compile(r"^(///|===).*$", re.M)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
MULTI_NL = re.compile(r"\n{3,}")


def clean_text(text):
    """讲解块：去掉代码块，只留说明文字。"""
    text = FRONTMATTER.sub("", text)
    text = CODE_BLOCK.sub("\n", text)
    text = INCLUDE.sub("", text)
    text = DIRECTIVE.sub("", text)
    text = IMAGE.sub("", text)
    text = HTML_COMMENT.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    return MULTI_NL.sub("\n\n", text).strip()


def extract_code(body, head, rel, max_code=800):
    """代码块：带标题上下文单独成块，供“怎么用”类问题检索。"""
    out = []
    for m in CODE_BLOCK.finditer(body):
        code = m.group(0)
        if len(code.strip("`\n ")) < 30:
            continue
        if len(code) > max_code:
            code = code[:max_code] + "\n```"
        out.append({"text": f"{head}\n\n{code}", "source": rel, "title": head, "kind": "code"})
    return out


def split_sections(text):
    lines = text.splitlines()
    h1 = ""
    for line in lines:
        if line.startswith("# "):
            h1 = line.lstrip("# ").split("{")[0].strip()
            break

    sections, h2, buf = [], "", []
    for line in lines:
        if line.startswith("## "):
            if " ".join(buf).strip():
                sections.append((h1, h2, "\n".join(buf).strip()))
            h2 = line.lstrip("# ").split("{")[0].strip()
            buf = []
        elif line.startswith("# "):
            continue
        else:
            buf.append(line)
    if " ".join(buf).strip():
        sections.append((h1, h2, "\n".join(buf).strip()))
    return sections


def split_long(body, max_chars, overlap):
    if len(body) <= max_chars:
        return [body]
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) <= max_chars:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
                buf = (buf[-overlap:] + "\n\n" + p).strip() if overlap else p
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks


def build_chunks(max_chars=700, overlap=120):
    chunks = []
    files = [p for p in sorted(DOCS_DIR.rglob("*.md")) if not p.name.startswith("_")]
    for path in files:
        rel = path.relative_to(DOCS_DIR).as_posix()
        raw = path.read_text(encoding="utf-8")
        for h1, h2, body in split_sections(raw):
            head = f"{h1} / {h2}" if h2 else h1
            prose = clean_text(body)
            if len(prose) >= 80:
                for piece in split_long(prose, max_chars, overlap):
                    chunks.append({"text": f"{head}\n\n{piece}", "source": rel,
                                   "title": head, "kind": "prose"})
            chunks.extend(extract_code(body, head, rel))
    return files, chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chars", type=int, default=700)
    ap.add_argument("--overlap", type=int, default=120)
    ap.add_argument("--batch", type=int, default=10)
    args = ap.parse_args()

    files, chunks = build_chunks(args.max_chars, args.overlap)
    total_chars = sum(len(c["text"]) for c in chunks)
    print(f"文档 {len(files)} 篇 → {len(chunks)} 块，{total_chars} 字符，平均 {total_chars // len(chunks)} 字/块")
    if args.dry_run:
        return

    import step8_embed as s8

    done = {}
    if PARTIAL.exists():
        done = json.loads(PARTIAL.read_text(encoding="utf-8"))
        print(f"续传：已有 {len(done)} 块")
    elif OUT.exists() and not BACKUP.exists():
        shutil.copy(OUT, BACKUP)
        print(f"已备份旧向量到 {BACKUP.name}")

    pending = [(i, c) for i, c in enumerate(chunks) if str(i) not in done]
    print(f"待处理 {len(pending)} 块")
    t0 = time.perf_counter()
    bad = []

    for start in range(0, len(pending), args.batch):
        batch = pending[start:start + args.batch]
        texts = [c["text"] for _, c in batch]
        vecs = None
        for attempt in range(1, 4):
            try:
                vecs, _ = s8.embed(texts, s8.MODEL)
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:160]
                print(f"  HTTP {e.code} 第 {attempt} 次：{body}")
                time.sleep(2 * attempt)
            except Exception as e:
                print(f"  {type(e).__name__} 第 {attempt} 次：{e}")
                time.sleep(2 * attempt)

        if vecs is None:                       # 整批失败 → 逐条重试，跳过坏块
            for i, c in batch:
                try:
                    v, _ = s8.embed([c["text"]], s8.MODEL)
                    done[str(i)] = [round(x, 6) for x in v[0]]
                except Exception as e:
                    bad.append((i, c["source"], str(e)[:80]))
                    print(f"  跳过块 {i}（{c['source']}）：{e}")
        else:
            for (i, _), v in zip(batch, vecs):
                done[str(i)] = [round(x, 6) for x in v]

        if start % (args.batch * 10) == 0:
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"  {len(done)}/{len(chunks)}  {time.perf_counter() - t0:.0f}s")
        time.sleep(0.2)

    PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    kept = [c for i, c in enumerate(chunks) if str(i) in done]
    for i, c in enumerate(chunks):
        if str(i) in done:
            c["vector"] = done[str(i)]

    OUT.write_text(json.dumps({"model": s8.MODEL, "dim": len(kept[0]["vector"]),
                               "chunks": kept}, ensure_ascii=False), encoding="utf-8")
    print(f"完成：{len(kept)} 块（跳过 {len(bad)} 块），"
          f"{OUT.stat().st_size / 1024 / 1024:.1f}MB，{time.perf_counter() - t0:.0f}s")
    PARTIAL.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
