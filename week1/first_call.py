#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一次调用大模型：不用 SDK，手写 HTTP + SSE 流式解析。

为什么不用 openai 库？因为库里藏起来的东西，正是你要理解的东西：
一次请求 = 一个 HTTP POST，返回的不是 JSON，而是一串 "data: {...}" 文本行（SSE）。

用法：
    python first_call.py --mock                    # 没有 key 也能跑，看流式机制
    python first_call.py "用一句话解释什么是 RAG"
    python first_call.py --show-raw "你好"          # 打印服务端原始数据帧
    python first_call.py --think "9.11 和 9.8 谁大"  # 开启思考模式，看思维链
    python first_call.py --compat "你好"            # 换非 DeepSeek 服务商时用
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_payload(model, messages, temperature, max_tokens, think, compat):
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,          # 关键：让服务端边生成边推，而不是等全部生成完
        "temperature": temperature,   # 注意：思考模式下该参数不生效
        "max_tokens": max_tokens,
    }
    if not compat:
        # DeepSeek 专有参数：默认思考模式是开的，这里显式关掉，否则会先刷一大段思维链
        payload["thinking"] = {"type": "enabled" if think else "disabled"}
    return payload


def stream_mock(text):
    """假流式：模拟服务端一帧一帧推过来的样子，用来观察机制。"""
    yield {"choices": [{"delta": {"role": "assistant"}}]}
    for ch in text:
        time.sleep(0.02)
        yield {"choices": [{"delta": {"content": ch}}]}
    yield {
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 30, "completion_tokens": len(text)},
    }


def stream_real(base, key, payload, show_raw):
    """真流式：POST 之后逐行读响应体，每行是一个 SSE 事件。"""
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:                      # 一行一行读，不做整体缓冲
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            if show_raw:
                print(f"  << {line[:160]}")
            if not line.startswith("data:"):   # 跳过 event: / id: / 注释行
                continue
            data = line[5:].strip()
            if data == "[DONE]":               # 结束标记
                break
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", default="用三句话说明大模型的流式输出是什么")
    ap.add_argument("--system", default="你是一位简洁准确的老师，回答不超过 120 字。")
    ap.add_argument("--model", default=None)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--think", action="store_true", help="开启思考模式（先输出思维链）")
    ap.add_argument("--compat", action="store_true", help="不发 DeepSeek 专有参数")
    ap.add_argument("--mock", action="store_true", help="不调接口，模拟流式")
    ap.add_argument("--show-raw", action="store_true", help="打印原始 SSE 帧")
    args = ap.parse_args()

    load_dotenv()
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = args.model or os.environ.get("LLM_MODEL", "deepseek-flash")
    price_in = float(os.environ.get("PRICE_IN", "0") or 0)
    price_out = float(os.environ.get("PRICE_OUT", "0") or 0)
    currency = os.environ.get("CURRENCY", "USD")

    messages = [
        {"role": "system", "content": args.system},
        {"role": "user", "content": args.prompt},
    ]
    payload = build_payload(model, messages, args.temperature, args.max_tokens,
                            args.think, args.compat)

    if args.mock:
        print(f"[mock] model={model}  temperature={args.temperature}  （不消耗额度）\n")
        stream = stream_mock(f"[模拟输出] 你问的是：{args.prompt}。这就是流式：服务端把每个 token 单独推给你，所以看起来像打字机。")
    else:
        if not key or key.startswith("sk-在这里"):
            print("没有密钥。先用 --mock 看机制，然后复制 .env.example 为 .env 填入 key。")
            return 1
        mode = "思考模式" if args.think else "普通模式"
        print(f"[real] {base}  model={model}  {mode}  temperature={args.temperature}\n")
        stream = stream_real(base, key, payload, args.show_raw)

    t0 = time.perf_counter()
    ttft = None            # 首字延迟：用户体感的核心指标
    chars = 0
    reasoning_chars = 0
    usage = None
    phase = None           # 用来区分"思考中"和"正式回答"
    try:
        for obj in stream:
            if obj.get("usage"):
                usage = obj["usage"]
            for choice in obj.get("choices", []):
                delta = choice.get("delta") or {}
                # 思考模式下，思维链走 reasoning_content；普通模式只走 content
                rc = delta.get("reasoning_content")
                if rc:
                    if phase != "think":
                        print("\n--- 思考过程 ---\n")
                        phase = "think"
                    print(rc, end="", flush=True)
                    reasoning_chars += len(rc)
                piece = delta.get("content")
                if piece:
                    if phase == "think":
                        print("\n\n--- 正式回答 ---\n")
                    phase = "answer"
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    print(piece, end="", flush=True)
                    chars += len(piece)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"\n[HTTP {e.code}] {body}")
        if e.code == 401:
            print("→ key 无效，检查 .env")
        elif e.code == 402:
            print("→ 余额不足，去平台充值")
        elif e.code == 404:
            print("→ model 名称或 BASE_URL 不对")
        elif e.code == 429:
            print("→ 请求太频繁，等几秒再试")
        return 1
    except urllib.error.URLError as e:
        print(f"\n[网络错误] {e.reason}")
        return 1

    total = time.perf_counter() - t0
    pt = (usage or {}).get("prompt_tokens", 0)
    ct = (usage or {}).get("completion_tokens", 0)
    cost = pt / 1e6 * price_in + ct / 1e6 * price_out

    print("\n" + "-" * 52)
    print(f"首字延迟 TTFT : {ttft:.2f}s" if ttft else "首字延迟 TTFT : n/a")
    print(f"总耗时        : {total:.2f}s   正式输出 {chars} 字" +
          (f"，思维链 {reasoning_chars} 字" if reasoning_chars else ""))
    print(f"token         : 输入 {pt} + 输出 {ct} = {pt + ct}")
    print(f"本次成本      : 约 {cost:.6f} {currency}" +
          ("" if price_in else "（未配置单价，只统计 token）"))
    print("-" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())
