#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chat.py v0（填空版）：多轮对话，让模型记住上文。

只填 4 个 TODO，其余都写好了。

运行：
    python day2_chat_skeleton.py

预期效果：
    你：我叫小明
    AI：你好，小明！
    你：我叫什么？
    AI：你叫小明。          ← 证明"记忆"生效
    你：/clear
    AI：你叫什么？          ← 证明清空后"失忆"
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

    # 整个对话历史都装在这里。第 0 条永远是 system（人设）
    messages = [{"role": "system", "content": "你是一位简洁的老师，回答不超过 80 字。"}]

    total_in = 0
    total_out = 0
    print("多轮对话已启动：/exit 退出，/clear 清空上下文")

    while True:
        # ---------- 读输入 ----------
        try:
            user = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break

        # ================== TODO 1 ==================
        # 处理三种情况：
        #   user 是 "/exit" 或 "/quit"  -> break 退出
        #   user 是 "/clear"            -> 清空上下文但保留 system，打印提示，continue
        #   user 是空字符串              -> continue（什么都不做）
        #
        # 提示：保留 system 的写法是  messages = messages[:1]
        if user in ("/quit", "/exit"):
           break
        if user == "/clear":
            messages = messages[:1]
            print("[已清除上下文]")
            continue
        if not user:
            continue
        # ============================================

        # ================== TODO 2 ==================
        # 把用户这句话追加进 messages，格式：
        #   {"role": "user", "content": user}
        # 一行代码搞定。
        messages.append({"role":"user", "content": user})
        # ============================================
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 512,
            "thinking": {"type": "disabled"},
        }

        # ---------- 调接口，边打印边收集 ----------
        print("AI：", end="", flush=True)
        parts = []          # 收集完整回答，最后拼成字符串
        usage = None
        try:
            for obj in stream_real(base, key, payload, False):
                if obj.get("usage"):
                    usage = obj["usage"]
                for choice in obj.get("choices", []):
                    piece = (choice.get("delta") or {}).get("content")
                    if piece:
                        print(piece, end="", flush=True)
                        # ============ TODO 3 ============
                        # 同时把 piece 存进 parts，否则屏幕上有字、
                        # 但 messages 里没有回答，下一轮模型就"失忆"。
                        parts.append(piece)
                        # ===============================
        except KeyboardInterrupt:
            print("\n[已中断，本轮回答不完整，不计入上下文]")
            continue
        except Exception as e:
            print(f"\n[出错] {e}")
            continue

        print()  # 回答结束，换行
        answer = "".join(parts)

        # ================== TODO 4 ==================
        # 把完整回答追加进 messages，格式：
        #   {"role": "assistant", "content": answer}
        messages.append({"role": "assistant", "content": answer})
        # ============================================

        # ---------- 统计（不用改）----------
        pt = (usage or {}).get("prompt_tokens", 0)
        ct = (usage or {}).get("completion_tokens", 0)
        total_in += pt
        total_out += ct
        cost = total_in / 1e6 * price_in + total_out / 1e6 * price_out
        print(f"[本轮 输入{pt} 输出{ct} | 累计 输入{total_in} 输出{total_out} | 约 {cost:.6f} USD]")


if __name__ == "__main__":
    main()
