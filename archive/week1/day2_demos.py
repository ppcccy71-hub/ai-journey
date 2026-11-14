#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day 2 三个可直接运行的小实验：看懂 day1_first_call.py 背后的机制。

运行：
    python day2_demos.py 1     # 列表 vs 生成器
    python day2_demos.py 2     # read() vs 逐行读
    python day2_demos.py 3     # 异常在什么时候抛出
    python day2_demos.py       # 全部跑一遍
"""
import io
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def demo1_generator():
    """列表要等全部做完；生成器是要一个给一个。"""
    print("=" * 56)
    print("实验 1：列表 vs 生成器 —— 为什么 yield 能边生成边打印")
    print("=" * 56)

    def make_list():
        out = []
        for i in range(5):
            time.sleep(0.3)
            out.append(i)
        return out

    def make_gen():
        for i in range(5):
            time.sleep(0.3)
            yield i

    t = time.perf_counter()
    print("① 列表方式：调用后要等全部算完才拿到结果……")
    data = make_list()
    print(f"   拿到 {data}，共等 {time.perf_counter() - t:.1f}s\n")

    t = time.perf_counter()
    print("② 生成器方式：每 yield 一次，立刻拿到一个值")
    for x in make_gen():
        print(f"   拿到 {x}，已耗时 {time.perf_counter() - t:.1f}s")

    print("\n结论：yield 把「一次算完」变成「分次交付」，所以能边收边打印。\n")


def demo2_read():
    """read() 要等连接结束；逐行读可以立刻处理。"""
    print("=" * 56)
    print("实验 2：read() vs 逐行读 —— for raw in resp 读的是什么")
    print("=" * 56)

    text = "data: 第一帧\n\ndata: 第二帧\n\ndata: 第三帧\n\n"

    buf = io.StringIO(text)
    print("① read()：一次性全拿走")
    print(repr(buf.read()))

    buf = io.StringIO(text)
    print("\n② 逐行读：来一行处理一行")
    for line in buf:
        print("  ", repr(line))

    print("\n结论：resp 是还在流动的管子，read() 会等到管子关闭；")
    print("      逐行迭代才能做到「收到一帧、处理一帧」。\n")


def demo3_exception():
    """异常在迭代时才抛出，所以 try 必须包住循环。"""
    print("=" * 56)
    print("实验 3：异常在什么时候抛出 —— try 该包住哪里")
    print("=" * 56)

    def bad_stream():
        yield "第一帧"
        yield "第二帧"
        raise ValueError("网络在第 3 帧断了")

    print("① try 只包住「创建生成器」：")
    try:
        stream = bad_stream()        # 这一步什么都不会发生
        print("   创建成功，没报错（因为还没开始要数据）")
    except ValueError as e:
        print("   捕获到：", e)
    print("   ↑ 注意：真正的错误发生在下面迭代的时候，这里根本没捕获到\n")

    print("② try 包住整个 for 循环：")
    try:
        for frame in bad_stream():
            print("   收到", frame)
    except ValueError as e:
        print("   捕获到：", e)
    print("\n结论：生成器是懒惰的，错误在「取数据」时才发生，")
    print("      所以 try 必须包住 for 循环，而不是包住创建那一行。\n")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("1", "all"):
        demo1_generator()
    if which in ("2", "all"):
        demo2_read()
    if which in ("3", "all"):
        demo3_exception()
