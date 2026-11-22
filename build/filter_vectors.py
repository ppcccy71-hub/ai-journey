#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已有向量里剔除元信息类文档（变更日志、贡献指南、营销页等）。

不需要重新调用 embedding，直接过滤 vectors.json。
"""
import json
import shutil
from pathlib import Path

V = Path(__file__).resolve().parent / "vectors.json"
BAK = Path(__file__).resolve().parent / "vectors_with_noise.json"

NOISE_PREFIX = ("about/", "learn/index.md")
NOISE_EXACT = {
    "release-notes.md", "contributing.md", "help-fastapi.md", "newsletter.md",
    "fastapi-people.md", "external-links.md", "management.md", "project-generation.md",
    "benchmarks.md", "alternatives.md", "history-design-future.md", "features.md",
    "editor-support.md", "agent-banner.md", "ai-development.md", "index.md",
}


def is_noise(src: str) -> bool:
    return src in NOISE_EXACT or src.startswith(NOISE_PREFIX)


def main():
    data = json.loads(V.read_text(encoding="utf-8"))
    chunks = data["chunks"]
    kept = [c for c in chunks if not is_noise(c["source"])]

    if len(kept) == len(chunks):
        print("没有需要过滤的内容")
        return

    if not BAK.exists():
        shutil.copy(V, BAK)
        print(f"已备份到 {BAK.name}")

    data["chunks"] = kept
    V.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"过滤 {len(chunks) - len(kept)} 块，剩余 {len(kept)} 块，"
          f"{V.stat().st_size / 1024 / 1024:.1f}MB")

    from collections import Counter
    c = Counter(x["source"] for x in kept)
    print("剩余文件数：", len(c))


if __name__ == "__main__":
    main()
