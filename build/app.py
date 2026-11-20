import json
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import llm
import step9_vector as s9

ROOT = Path(__file__).resolve().parent

SYSTEM = ("你是知识库助手。只能依据给定资料回答，每句话后用 [编号] 标注依据。\n"
          "资料里没有答案时，直接回答：资料中没有相关信息。不要编造。")

app = FastAPI(title="个人知识助手 v1",version="0.1.0")
MODEL_V, CHUNKS = s9.load_vectors()# 启动时加载一次，别每次请求都读文件


class AskRequest(BaseModel):
    question: str = Field(...,min_length=1,max_length=500)
    top_k: int = Field(5,ge=1,le=8)
    min_score: float = Field(0.45,ge=0,le=.1)

def search(req):
    hits = s9.search(req.question, CHUNKS, MODEL_V, req.top_k)
    return hits,(hits[0][0]) if hits else 0.0

def messages_of(req,hits):
    ctx = "\n\n".join(f"[{i}] 来源: {c['source']}\n{c['text']}"
                      for i,(_,c) in enumerate(hits,1))
    return [{"role":"system","content":SYSTEM},
            {"role":"user","content":f"资料：\n{ctx}\n\n问题: {req.question}\n\n请依据资料回答并标注 [编号]。"}]

def sources_of(hits):
    return [{"index":i,"source":c["source"],"score":round(s,3)}
            for i,(s,c) in enumerate(hits,1)]

def sse(obj):
    return "data: " + json.dumps(obj,ensure_ascii=False) + "\n\n"

@app.get("/health")
def health():
    return {"status":"ok","model":llm.MODEL,"chunks":len(CHUNKS)}
@app.post("/ask")
def ask(req:AskRequest):
    t0= time.perf_counter()
    hits,best = search(req)
    if best < req.min_score:
        return {"answer":"资料中没有相关信息。","refused":"True","best":round(best,3),
                "source":[],"latency_ms":int((time.perf_counter()-t0)*1000)}
    text,usage = llm.stream_chat(messages_of(req,hits),temperature=0.2,max_tokens=400)
    return {"answer":text,"refused":False,"best":round(best,3),
            "source":sources_of(hits),"usage":usage or {},
            "cost":round(llm.cost(usage),8),
            "latency_ms":int((time.perf_counter()-t0)*1000)}
@app.post("/ask/stream")
def ask_stream(req:AskRequest):
    hits,best = search(req)


    def gen():
        if best < req.min_score:
            yield sse({"type":"sources","sources":[]})
            yield sse({"type":"refused","text": "资料中没有相关信息。"})
            yield "data: [DONE]\n\n"
            return
        yield sse({"type":"sources","sources":sources_of(hits)})
        holder = {}
        t0 = time.perf_counter()
        for piece in llm.iter_chat(messages_of(req,hits),temperature=0.2,
                                   max_tokens=400,usage_holder=holder):
            yield sse({"type":"delta","text":piece})
        usage = holder.get("usage") or {}
        yield sse({"type":"done","usage":usage,"cost":round(llm.cost(usage),8),
                   "latency_ms":int((time.perf_counter()-t0)*1000)})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(),media_type="text/event-stream")

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000)
