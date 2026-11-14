#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念 03：生成器（yield）—— 流式输出的底层机制。

对比两个函数：
    make_list() 全部算完才返回 → 调用者干等
    make_gen()  每算一个就交出  → 调用者立刻能用

运行：python 03_generator.py
"""
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def make_list(n=5):
    out = []
    for i in range(n):
        time.sleep(0.3)          # 模拟"模型生成一个字需要时间"
        out.append(i)
    return out                   # 一次性交全部


def make_gen(n=5):
    for i in range(n):
        time.sleep(0.3)
        yield i                  # 交一个，暂停，等下次要


def main():
    print("① 列表方式：")
    t0 = time.perf_counter()
    print("   等待中……（什么都不会显示）")
    data = make_list()
    print(f"   全部拿到 {data}，总耗时 {time.perf_counter() - t0:.1f}s")

    print("\n② 生成器方式：")
    t0 = time.perf_counter()
    for x in make_gen():
        print(f"   拿到 {x}，已耗时 {time.perf_counter() - t0:.1f}s")

    print("\n结论：yield 把「一次算完」变成「分次交付」，所以能边生成边显示。")
    print("      流式接口就是把模型返回的每个 token 用生成器交出去。")


if __name__ == "__main__":
    main()
