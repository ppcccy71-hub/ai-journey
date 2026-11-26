#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step8：调用百炼 embedding，把每个块变成向量，存 vectors.json。

用法：
    python step8_embed.py --probe     # 探测哪个 embedding 模型可用
    python step8_embed.py             # 正式生成向量
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import step2_chunks as s2

ROOT = Path(__file__).resolve().parent #ROOT为该py文件的父级文件夹：build
ENV = ROOT.parent / ".env"
OUT = ROOT / "vectors.json" #在ROOT也就是build文件夹下输出json文件

CANDIDATES = ["text-embedding-v4","text-embedding-v3","text-embedding-v2","text-embedding-v1"]


def load_env():
    if not ENV.exists():          # Docker 里没有 .env，配置由环境变量注入
        return
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1)
            os.environ.setdefault(k.strip(),v.strip())


load_env()
BASE = os.environ.get("BAILIAN_BASE_URL","https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
KEY = os.environ.get("BAILIAN_API_KEY","")
MODEL = os.environ.get("EMBED_MODEL") or os.environ.get("BAILIAN_BASE_MODEL") or "text-embedding-v3"

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler())


def embed(texts,model,retries=3):
    """一次请求把一批文本转成向量，返回 (向量列表, usage)。

    网络抖动（SSL EOF、超时）重试，避免单次失败中断整个索引或查询。
    """
    body = {"model":model,"input":texts,"encoding_format":"float"}
    req = urllib.request.Request(
        f"{BASE}/embeddings",
        data=json.dumps(body).encode("utf8"),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {KEY}"},
        method = "POST"
    )
    last = None
    for attempt in range(retries):
        try:
            with _OPENER.open(req,timeout=120) as resp:
                data = json.loads(resp.read().decode("utf8"))
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise last
    # 有的服务返回顺序不定，按 index 排好
    items = sorted(data["data"],key=lambda d:d.get("index",0))
    return [it["embedding"] for it in items], data.get("usage",{})

def probe():
    print(f"接口: {BASE}\n")
    for m in CANDIDATES:
        try:
            vecs,usage = embed(["测试文本"],m)
            print(f"✅ {m:<22} 维度 {len(vecs[0])}  usage={usage}")
        except urllib.error.HTTPError as e:
            print(f"❌ {m:<22} HTTP {e.code}  {e.read().decode('utf-8', 'replace')[:80]}")
        except Exception as e:
            print(f"❌ {m:<22} {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe",action="store_true")
    ap.add_argument("--batch", type=int,default=10, help="每次请求发送几条")
    args = ap.parse_args()

    if args.probe:
        probe()
        return


    chunks = [{"text":t,"source":n}
              for n,text in s2.load_docs()
              for t in s2.chunk_text(text,size=300)]
    print(f"共{len(chunks)} 块，用模型{MODEL} 向量化......")

    t0 = time.perf_counter()
    for i in range(0, len(chunks), args.batch):
        batch = chunks[i:i + args.batch]
        vecs, usage = embed([c["text"] for c in batch], MODEL)
        for c, v in zip(batch, vecs):
            c["vector"] = v
        print(f"  {i + len(batch)}/{len(chunks)}  usage={usage}")

    dim = len(chunks[0]["vector"])
    OUT.write_text(json.dumps({"model":MODEL,"dim":dim,"chunks":chunks},
                              ensure_ascii=False),encoding="utf8")
    print(f"\n已保存{OUT.name}:{len(chunks)}块,维度{dim},"
          f"耗时 {time.perf_counter() - t0:.2f}s,文件 {OUT.stat().st_size / 1024:.0f}KB")

if __name__ == "__main__":
    main()
