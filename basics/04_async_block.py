#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念 04：为什么 async def 里放阻塞代码会卡死（不用起服务器）。

同一个"耗时 1 秒"的任务，三种写法，总耗时完全不同：

    A. 顺序执行三个 time.sleep(1)     → 约 3 秒
    B. asyncio.gather + time.sleep    → 也是约 3 秒（事件循环被占住）
    C. asyncio.gather + await sleep   → 约 1 秒（真正并发）

运行：python 04_async_block.py
"""
import asyncio
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def blocking_task(name):
    """模拟一次同步网络请求：占着线程不动。"""
    time.sleep(1)
    return name


async def async_blocking_task(name):
    """错误示范：async 函数里调用阻塞代码。"""
    time.sleep(1)          # ← 事件循环停在这里，别的协程都动不了
    return name


async def async_ok_task(name):
    """正确示范：await 让出控制权。"""
    await asyncio.sleep(1)
    return name


def run_a():
    t0 = time.perf_counter()
    [blocking_task(f"A{i}") for i in range(3)]
    return time.perf_counter() - t0


def run_b():
    async def main():
        return await asyncio.gather(*[async_blocking_task(f"B{i}") for i in range(3)])
    t0 = time.perf_counter()
    asyncio.run(main())
    return time.perf_counter() - t0


def run_c():
    async def main():
        return await asyncio.gather(*[async_ok_task(f"C{i}") for i in range(3)])
    t0 = time.perf_counter()
    asyncio.run(main())
    return time.perf_counter() - t0


if __name__ == "__main__":
    print(f"A 顺序执行        ：{run_a():.2f}s  ← 3 秒")
    print(f"B async + 阻塞    ：{run_b():.2f}s  ← 还是 3 秒，事件循环被占")
    print(f"C async + await   ：{run_c():.2f}s  ← 1 秒，三个同时跑")
    print("\n结论：async 不会自动变快；关键是阻塞代码有没有让出控制权。")
