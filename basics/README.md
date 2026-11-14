# basics · 用代码学概念

每个文件就是一个可运行的最小例子，对应一个知识点。**不要只读，要跑、要改。**

| 文件 | 概念 | 跑完你应该能回答 |
|---|---|---|
| `01_call_and_cost.py` | 一次 API 调用 + 计费 | 输入/输出 token 怎么变成钱？ |
| `02_stream_frames.py` | SSE 流式 | `data: {...}` 一帧一帧长什么样？ |
| `03_generator.py` | 生成器 yield | 为什么能边生成边显示？ |
| `04_async_block.py` | 事件循环与阻塞 | 为什么 async 里 sleep 会卡死？ |
| `05_fastapi_min.py` | 最小 Web 服务 | 422 是谁返回的？`/docs` 哪来的？ |
| `06_file_session.py` | 状态存文件 | 重启为什么不该丢历史？ |

## 怎么用

```powershell
cd C:\Users\20647\Desktop\AI_WorkPlace\ai-journey\basics
python 01_call_and_cost.py
python 03_generator.py
```

`05_fastapi_min.py` 需要启动服务：

```powershell
python -m uvicorn 05_fastapi_min:app --port 8000
```

## 每个例子的固定套路

1. **先跑**，看输出
2. **改一个数字**，再跑，看差异（比如 `03` 里的 `time.sleep(0.3)` 改成 `0`）
3. **关掉文件**，用一句话说出它证明了什么

改不动、跑不起来，就把报错贴给 AI——但先自己看最后一行。
