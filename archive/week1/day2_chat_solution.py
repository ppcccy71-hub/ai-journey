#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chat.py v0（完整样例）：多轮对话，让模型记住上文。

这是 day2_chat_skeleton.py 的答案版，四个 TODO 的位置都标了「对应 TODO N」。

学习方式（很重要，别只读）：
    1. 先跑一遍，看到"记得上文"的效果
    2. 对照 TODO 标记读代码，理解每个空为什么这么填
    3. 合上文件，从骨架版重写那 4 处（10 分钟）
    4. 做文件末尾的三个改造练习

运行：
    python day2_chat_solution.py
"""
import os
import sys
import time

from day1_first_call import load_dotenv, stream_real

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    load_dotenv()
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "deepseek-flash")
    price_in = float(os.environ.get("PRICE_IN", "0") or 0)
    price_out = float(os.environ.get("PRICE_OUT", "0") or 0)

    # 【核心】整个对话历史都装在这个列表里。
    # 第 0 条永远是 system（人设），后面每轮追加 user 和 assistant。
    messages = [{"role": "system", "content": "你是一位简洁的老师，回答不超过 80 字。"}]

    total_in = 0
    total_out = 0
    prev_in = 0          # 上一轮输入 token，用来算"比上一轮多了多少"
    print("多轮对话已启动：/exit 退出，/clear 清空上下文")

    while True:
        # ---------- 读输入 ----------
        # input() 在用户按 Ctrl+C 时抛 KeyboardInterrupt，管道结束时抛 EOFError，
        # 两个都要接住，否则程序会带着报错栈退出。
        try:
            user = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break

        # ================== TODO 1：特殊命令 ==================
        # 对应 TODO 1：先处理命令，再处理正常对话，
        # 顺序很重要——如果把 append 写在前面，"/exit" 也会被发给模型。
        if user in ("/exit", "/quit"):
            break
        if user == "/clear":
            # 只保留 system 那条，否则人设也丢了
            messages = messages[:1]
            print("[已清空上下文]")
            continue
        if user == "/history":
            chars = sum(len(m["content"]) for m in messages)
            print(f"[调试] 当前 {len(messages)}条消息,共{chars}个字")
            continue

        if user == "/count":
            chars=sum(len(m["content"]) for m in messages)
            chars / 1.6
            print(f"当前上下文的输入 token 为{chars / 1.6:.0f}")
            continue

        if not user:
            continue
        # ======================================================

        # ================== TODO 2：追加用户消息 ==================
        # 对应 TODO 2：只有进了 messages，模型才"看得到"这句话
        messages.append({"role": "user", "content": user})
        # ==========================================================

        payload = {
            "model": model,
            "messages": messages,        # 注意：发的是"累积后的全部历史"
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 512,
            "thinking": {"type": "disabled"},
        }

        # ---------- 调接口，边打印边收集 ----------
        print("AI：", end="", flush=True)
        parts = []          # 收集完整回答
        usage = None
        try:
            for obj in stream_real(base, key, payload, False):
                if obj.get("usage"):
                    usage = obj["usage"]
                for choice in obj.get("choices", []):
                    piece = (choice.get("delta") or {}).get("content")
                    if piece:
                        print(piece, end="", flush=True)
                        # ============ TODO 3：收集 ============
                        # 对应 TODO 3：屏幕打印和存入 parts 是两件独立的事。
                        # 少了这一行，answer 就是空字符串，
                        # 下一轮模型只会看到"你问了，但你自己没回答过"。
                        parts.append(piece)
                        # ====================================
        except KeyboardInterrupt:
            # 用户中途 Ctrl+C：本轮回答不完整，直接丢弃，不写进上下文
            print("\n[已中断，本轮回答不完整，不计入上下文]")
            continue
        except Exception as e:
            # 网络错误、401、429 等都落在这里
            print(f"\n[出错] {e}")
            continue

        print()  # 回答结束，换行
        answer = "".join(parts)

        # ================== TODO 4：追加助手消息 ==================
        # 对应 TODO 4：把完整回答写回历史，下一轮才能"记得"自己说过什么
        messages.append({"role": "assistant", "content": answer})
        # ==========================================================

        # ---------- 统计 ----------
        pt = (usage or {}).get("prompt_tokens", 0)
        ct = (usage or {}).get("completion_tokens", 0)
        total_in += pt
        total_out += ct
        delta=pt - prev_in
        prev_in=pt
        cost = total_in / 1e6 * price_in + total_out / 1e6 * price_out
        print(f"[本轮 输入 {pt}(+{delta}) 输出 {ct} | 累计 输入{total_in} 输出{total_out} | 约 {cost:.6f} USD]")


if __name__ == "__main__":
    main()


# ============================================================
# 三个改造练习（按难度排序，做完就算真正掌握）
# ============================================================
# 练习 1（简单）：加一个 /history 命令，打印"当前有几条消息、多少字"。
#
# 练习 2（中等）：加一个 /count 命令，估算当前上下文的输入 token
#                （粗略算法：所有 content 的字符数 / 1.6）。
#
# 练习 3（较难）：把统计里的"本轮"输出改成"距离上一轮多了多少 token"，
#                这样你能直观看到历史在膨胀。
# ============================================================
