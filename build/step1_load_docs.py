#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step1：读出 docs 下所有 md，打印名字、大小、前 80 字。"""
from pathlib import Path

def main() :
    # 定位到"本文件所在目录 / docs"，而不是写死 C:\...
    docs_dir=Path(__file__).resolve().parent / "docs"
    # 找出所有 .md 文件，排序保证每次输出顺序一致
    files = sorted(docs_dir.glob("*.md"), key=lambda p: -p.stat().st_size)
    for file in files :
        print(file)

    total_bytes = 0
    total_chars = 0

    for p in files:
        text = p.read_text(encoding="utf-8")
        size_kb = p.stat().st_size / 1024
        preview = text.replace("\n", " ")[:120] # 换行压成空格，取前 80 字

        print(f"{p.name:<22} {size_kb:6.2f}KB {preview}")

        total_bytes += p.stat().st_size
        total_chars += len(text)
    print("_" * 70)
    print(f"共 {len(files)} 个文件，{total_bytes/1024:.2f} KB,{total_chars}个字符")
if __name__ == "__main__":
    main()