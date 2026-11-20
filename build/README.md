# 个人工作助手 · 阶段 1（RAG）

> 从零构建的本地知识库问答服务：切块 → 向量检索 → 带引用回答 → 网页可用。
> 评测准确率 **90%**（20 题同义改写集），单次成本约 **0.001 元**。

## 能做什么

- 提问后从 `docs/` 里检索最相关的 5 个块
- 模型只依据资料回答，并标注 `[编号]` 出处
- 资料里没有的问题**直接拒答**（阈值 + 提示词两层），不花钱、不编造
- 浏览器里逐字显示，带相似度、耗时、token、成本

## 怎么跑

```powershell
cd C:\Users\20647\Desktop\AI_WorkPlace\ai-journey\build

# 1. 重建向量（改过 docs 才需要）
python step8_embed.py

# 2. 启动服务
python app.py

# 3. 打开
#    http://127.0.0.1:8000/        网页
#    http://127.0.0.1:8000/docs    接口文档
```

## 文件结构

```
build/
├── step1_load_docs.py    读文档
├── step2_chunks.py       切块（300 字，重叠 60）
├── step3_retrieve.py     关键词检索（二元组打分）
├── step4_answer.py       检索 + 生成 + 引用（命令行）
├── step6_eval.py         评测脚本（keyword / vector 双模式）
├── step7_rewrite.py      查询改写（实验，默认不启用）
├── step8_embed.py        调 embedding，生成 vectors.json
├── step9_vector.py       余弦相似度检索
├── llm.py                模型调用（iter_chat / stream_chat / cost）
├── app.py                FastAPI 服务（/ask、/ask/stream、网页）
├── static/index.html     前端
├── vectors.json          9 块 × 1024 维
├── eval/
│   ├── questions.json        20 题（简单版）
│   └── questions_hard.json   20 题（同义改写版）
└── RESULTS.md            评测数据
```

## 一次请求的链路

```
问题
 ├─ embedding（百炼 text-embedding-v3）
 ├─ 和 9 个块算余弦 → top 5
 ├─ 最高分 < 0.45 → 直接拒答（0 token）
 └─ 拼上下文 → deepseek-flash → 流式返回 + 出处
```

## 评测（详见 RESULTS.md）

| 方案 | 准确率 |
|---|---|
| 关键词检索 | 70% |
| 关键词 + 改写 | 75% |
| 向量 + top5 | **90%** |

## 已知局限

- 库只有 9 块，规模小；上千块要换向量库（pgvector / Qdrant）
- 阈值 0.45 是在本数据集标定的，换文档要重标
- 没有 rerank、没有多轮对话、没有多用户隔离

## 下一步（阶段 2）

工具调用：让它能查文件、算数、抓网页，从“回答问题”变成“完成任务”。
