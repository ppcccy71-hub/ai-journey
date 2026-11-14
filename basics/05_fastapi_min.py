#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念 05：FastAPI 最小服务——路由、请求体、校验、文档。

运行：
    python -m uvicorn 05_fastapi_min:app --port 8000
然后：
    http://127.0.0.1:8000/docs        自动文档
    POST /echo  {"name": "小明"}       校验 + 响应

看三件事：
1. @app.post("/echo") 定义路由
2. Pydantic 模型自动校验（name 为空会返回 422）
3. /docs 不需要写文档就自动生成
"""
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="最小服务")


class EchoRequest(BaseModel):
    name: str = Field(..., min_length=1, description="你的名字")
    times: int = Field(1, ge=1, le=5, description="重复几次")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/echo")
def echo(req: EchoRequest):
    return {"message": f"你好，{req.name}！" * req.times, "times": req.times}
