#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无状态 vs 有状态：一个不需要网络的对照实验。

运行：
    python day3_stateless_demo.py

它模拟两个用户轮流提问，分别打到"有状态服务"和"无状态服务"上，
观察两件事：
    1. 用户之间会不会串台
    2. 服务重启后历史还在不在
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SYSTEM = {"role": "system", "content": "你是一位简洁的老师。"}


def extract_name(history):
    """假装是模型的"记忆"：从历史里找用户说过「我叫X」。"""
    for m in history:
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        if "我叫" in c and "什么" not in c:
            return c.split("我叫")[-1].strip("。！! ？?")
    return None


# ============================================================
# 版本 A：有状态 —— 把对话历史存在服务端进程的全局变量里
# ============================================================
GLOBAL_HISTORY = [SYSTEM]          # ← 所有用户共用一个列表


def chat_stateful(user, message):
    """不管谁来的请求，都往同一个列表里追加。"""
    GLOBAL_HISTORY.append({"role": "user", "content": f"[{user}] {message}"})
    name = extract_name(GLOBAL_HISTORY)
    reply = f"你叫{name}。" if name else "我不知道你叫什么。"
    GLOBAL_HISTORY.append({"role": "assistant", "content": reply})
    return reply


# ============================================================
# 版本 B：无状态 —— 服务端不存任何东西，历史由请求带上来
# ============================================================
def chat_stateless(history, message):
    """每次请求自带 history，服务端算完就忘。"""
    name = extract_name(history)             # 只在"我这次带来的历史"里找
    reply = f"你叫{name}。" if name else "我不知道你叫什么。"
    # 返回给客户端，由它保存；服务端自己不存
    return reply, history + [{"role": "user", "content": message},
                             {"role": "assistant", "content": reply}]


def main():
    print("=" * 60)
    print("场景：小明先说「我叫小明」，小红接着问「我叫什么」")
    print("=" * 60)

    print("\n【版本 A：有状态（全局变量）】")
    chat_stateful("小明", "我叫小明")
    print("  小红问：我叫什么？ →", chat_stateful("小红", "我叫什么？"))
    print("  ↑ 小红得到了小明的名字 —— 串台了")

    print("\n【版本 B：无状态（历史随请求带）】")
    xiaoming_history = []
    _, xiaoming_history = chat_stateless(xiaoming_history, "我叫小明")
    xiaohong_history = []
    reply_hong, _ = chat_stateless(xiaohong_history, "我叫什么？")
    print("  小红问：我叫什么？ →", reply_hong)
    print("  ↑ 小红没有历史，所以不知道 —— 正确")

    print("\n【版本 A：服务重启】")
    global GLOBAL_HISTORY
    GLOBAL_HISTORY = [SYSTEM]           # 进程重启，内存清空
    print("  小明问：我叫什么？ →", chat_stateful("小明", "我叫什么？"))
    print("  ↑ 小明的记忆跟着进程一起没了")

    print("\n【版本 B：服务重启】")
    print("  小明问：我叫什么？ →", chat_stateless(xiaoming_history, "我叫什么？")[0])
    print("  ↑ 历史在客户端手里，服务怎么重启都不影响")

    print("\n" + "=" * 60)
    print("结论：无状态不是「不存数据」，而是「服务进程不持有会话状态」。")
    print("      历史被外置到客户端（或数据库），服务端只做纯计算。")
    print("=" * 60)


if __name__ == "__main__":
    main()
