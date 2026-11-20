#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step2：把文档切成块——RAG 的索引单位。

为什么要切：
1. 模型上下文有限，不能把整本资料塞进去
2. 块太大 → 噪声多、贵；块太小 → 语义被切碎、答不全
3. 300 字左右是常见起点，之后靠评测调
"""
import re
from pathlib import Path

from sqlalchemy.dialects.postgresql.operators import OVERLAP

DOCS_DIR = Path(__file__).parent / "docs"
CHUNK_SIZE = 600 # 目标块大小（字符）
OVERLAP = 60 # 相邻块重叠多少字，防止答案被切断

def load_docs():
    """读出所有 md，返回 [(文件名, 全文), ...]"""
    return [(p.name ,p.read_text(encoding="utf-8")) for p in sorted(DOCS_DIR.glob("*.md"))]
def splits_paragraghs(text):
    """按空行切段落，去掉空段。"""
    return [p.strip() for p in re.split(r"\n\s*\n",text) if p.strip()]

def chunk_text(text, size=CHUNK_SIZE,overlap=OVERLAP):
    """按段落合并成块：装得下就合，装不下就断开，新块带上一块尾巴。"""
    chunks = []
    buf = ""
    for para in splits_paragraghs(text):
        if len(buf) + len(para) <= size:
            buf = f"{buf}\n{para}".strip()
            continue
        if buf:
            chunks.append(buf)
            # 重叠：把上一块最后 overlap 个字带到新块开头
            buf = (buf[ - overlap:] + "\n" +para).strip() if overlap else para
        else:
            buf = para
    if buf:
        chunks.append(buf)
    return chunks

def main():
    total = 0
    for name, text in load_docs():
        chunks = chunk_text(text)
        total += len(chunks)
        avg = sum(len(c) for c in chunks) / len(chunks)
        print(f"{name:<20} {len(text):>4}字 → {len(chunks):>2} 块，平均 {avg:.0f}字")
        print(f"   第 1 块开头: {chunks[0][:50].replace(chr(10),'    ')}...")
    print("-" * 60)
    print(f"共{total} 块")

if __name__ == "__main__":
    main()
