#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day 4 并发测速器：同时打 N 个请求，看总耗时。

用法：
    python day4_bench.py /slow/def           # 默认 3 并发
    python day4_bench.py /slow/async-block 5 # 5 并发
    python day4_bench.py /slow/async-ok 10

原理：用线程池同时发出 N 个请求，记录从开始到全部返回的总耗时。
"""
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:8000"


def hit(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(BASE + path, timeout=120) as r:
        return r.read()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/slow/def"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    print(f"同时发 {n} 个请求到 {path} ……")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n) as pool:
        list(pool.map(hit, [path] * n))
    dt = time.perf_counter() - t0
    print(f"总耗时：{dt:.2f}s   （单个约 2s，串行应是 {n * 2}s）")


if __name__ == "__main__":
    main()
