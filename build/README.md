# 个人工作助手

> 一个本地可运行的个人工作助手：**文档问答（RAG）+ 工具调用（Agent）+ 使用统计**。
> 单端口部署，`start.ps1` 一键启动。

## 三个能力

| 能力 | 说明 | 关键指标 |
|---|---|---|
| 知识问答 | 从本地文档检索，带 `[编号]` 引用，无依据时拒答 | 准确率 **90%**（20 题改写集） |
| Agent | 会查资料、算数、读写文件，多步完成任务 | 任务成功率 **9/10** |
| 统计 | 会话/消息/问答量、token、成本、延迟看板 | 单次约 **$0.0001** |

## 架构

```
浏览器（React + Vite）
   │  /api/*
   ▼
FastAPI（build/app.py）
   ├── /ask, /ask/stream   检索 → 拼提示词 → DeepSeek → 流式返回 + 引用
   ├── /agent/run          工具循环：模型决定调哪个工具，代码执行
   ├── /sessions           会话与消息（SQLite）
   └── /stats, /stats/daily 用量与成本聚合
        │
        ├── DeepSeek API      生成（deepseek-flash）
        ├── 阿里云百炼         向量（text-embedding-v3，1024 维）
        └── SQLite            会话、消息、成本日志（assistant.db）
```

**一次问答的链路**：问题 → embedding → 和 N 个块算余弦 → top 5 →
拼上下文 → 模型带引用回答 → 写库 + 记成本。

## 快速开始

```powershell
cd C:\Users\20647\Desktop\AI_WorkPlace\ai-journey
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

脚本会：装前端依赖（首次）→ 构建前端 → 启动后端 → 打开浏览器。
服务地址 `http://127.0.0.1:8000`，接口文档 `/docs`。

**手动启动（开发模式，前后端分离）**

```powershell
# 窗口 1
cd build
python app.py

# 窗口 2
cd frontend
npm run dev        # http://localhost:5173，/api 自动代理到 8000
```

**配置**：仓库根目录 `.env`

```ini
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-flash
PRICE_IN=0.15
PRICE_OUT=0.6

BAILIAN_API_KEY=sk-xxx
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBED_MODEL=text-embedding-v3
```

## 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/ask` | 问答（可带 `session_id` 存历史） |
| POST | `/ask/stream` | 流式问答（SSE） |
| POST | `/agent/run` | 执行 Agent 任务 |
| POST | `/sessions` | 新建会话 |
| GET | `/sessions` | 会话列表 |
| GET | `/sessions/{id}` | 会话消息 |
| DELETE | `/sessions/{id}` | 删除会话 |
| GET | `/stats` | 总量统计 |
| GET | `/stats/daily?days=7` | 按天统计 |
| GET | `/health` | 健康检查 |

前端统一带 `/api` 前缀，后端用中间件剥掉——开发（Vite 代理）和生产（单端口）同一套代码。

## 评测

详见 [`RESULTS.md`](RESULTS.md)。

| 方案 | 阈值 | top-k | 准确率 |
|---|---|---|---|
| 关键词检索 | 0.1 | 3 | 70% |
| + 查询改写 | 0.1 | 3 | 75% |
| 向量检索 | 0.45 | 3 | 80% |
| **向量检索** | **0.45** | **5** | **90%** |

Agent 任务评测：10 个任务，9 个通过（越界写入被模型主动拒绝）。

## 代码结构

```
build/
├── app.py               FastAPI 服务（问答 / Agent / 会话 / 统计）
├── llm.py               模型调用与计费
├── store.py             SQLite 存储层
├── step1_load_docs.py   读文档
├── step2_chunks.py      切块
├── step3_retrieve.py    关键词检索
├── step8_embed.py       向量化
├── step9_vector.py      向量检索
├── step13_agent.py      Agent 循环 + 工具
├── step14_task_eval.py  任务评测
├── test_safety.py       路径安全单元测试
├── docs/                知识库（3 篇示例）
├── eval/                评测集（问答 20×2、任务 10）
├── vectors.json         向量索引
└── assistant.db         会话与成本（不入库）
```

## 已知限制

- 知识库只有 9 块，规模小；上千块需换向量库（pgvector / Qdrant）
- 单机 SQLite，不支持多实例部署
- Agent 无会话记忆，每次任务独立
- 没有鉴权，仅本机使用
- 向量模型调用是同步阻塞的，并发靠线程池

## 下一步

- Docker Compose 一键部署（B2）
- 真实文档替换示例（50+ 篇，500+ 块）
- 混合检索（BM25 + 向量）+ rerank
