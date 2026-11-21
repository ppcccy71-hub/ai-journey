# 个人知识助手

基于 DeepSeek 的本地知识库问答与工具调用助手。支持带引用的文档问答、多步任务的 Agent、多会话记录和用量统计。

## 功能

- **文档问答**：向量检索 top-5 片段，模型依据片段回答并标注引用编号；没有相关资料时拒答
- **流式输出**：SSE 逐字返回，前端边收边显示
- **Agent**：5 个工具（检索、四则运算、读文件、写文件、列目录），模型自行决定调用顺序，最多 6 步
- **会话管理**：新建、切换、删除会话，历史消息持久化
- **用量统计**：问答次数、token、成本、平均延迟，按天聚合

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11、FastAPI、SQLite |
| 前端 | React 18、Vite |
| 生成模型 | DeepSeek `deepseek-flash` |
| 向量模型 | 阿里云百炼 `text-embedding-v3`（1024 维） |

## 目录结构

```
build/
├── app.py               FastAPI 应用（问答 / Agent / 会话 / 统计）
├── llm.py               模型调用与成本计算
├── store.py             SQLite 存储层
├── step1_load_docs.py   读取文档
├── step2_chunks.py      文本切块
├── step3_retrieve.py    关键词检索
├── step8_embed.py       生成向量索引
├── step9_vector.py      向量检索
├── step13_agent.py      Agent 循环与工具定义
├── step14_task_eval.py  Agent 任务评测
├── test_safety.py       路径安全单元测试
├── docs/                知识库文档
├── eval/                评测集
├── vectors.json         向量索引
└── assistant.db         会话与成本数据（不入库）

frontend/
├── src/api.js           接口封装
├── src/views/           问答 / Agent / 统计 三个页面
└── vite.config.js       开发代理配置
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 配置

在仓库根目录创建 `.env`：

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

### 启动

方式一：一键启动（会自动构建前端并托管，单端口）

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

访问 http://127.0.0.1:8000，接口文档 http://127.0.0.1:8000/docs。

方式二：开发模式（前后端分离，支持热更新）

```powershell
# 终端 1
cd build
python app.py

# 终端 2
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173，`/api` 由 Vite 代理到 8000。

### 重建索引

修改 `build/docs/` 后需要重新生成向量：

```powershell
cd build
python step8_embed.py
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/ask` | 问答，可带 `session_id` |
| POST | `/ask/stream` | 流式问答（SSE） |
| POST | `/agent/run` | 执行 Agent 任务 |
| POST | `/sessions` | 新建会话 |
| GET | `/sessions` | 会话列表 |
| GET | `/sessions/{id}` | 会话消息 |
| DELETE | `/sessions/{id}` | 删除会话 |
| GET | `/stats` | 汇总统计 |
| GET | `/stats/daily?days=7` | 按天统计 |
| GET | `/health` | 健康检查 |

前端请求统一带 `/api` 前缀，后端中间件负责剥离；开发环境由 Vite 代理，生产环境由同一服务处理。

## 评测

知识库 3 篇文档，切块 300 字，共 9 块；评测集 20 题（16 道可答、4 道应拒答）。

| 检索方式 | 阈值 | top-k | 准确率 |
|---|---|---|---|
| 关键词 | 0.1 | 3 | 70% |
| 关键词 + 查询改写 | 0.1 | 3 | 75% |
| 向量 | 0.45 | 3 | 80% |
| 向量 | 0.45 | 5 | 90% |

单次问答约 2.3 秒，成本约 $0.00012。

Agent 任务评测共 10 个任务，通过 9 个；越界写文件的请求被模型拒绝。

完整数据见 [RESULTS.md](RESULTS.md)。

## 已知限制

- 知识库规模小（9 块），上千块需要专用向量数据库
- SQLite 单机存储，不支持多实例部署
- Agent 每次任务独立，不带会话记忆
- 未实现鉴权，仅供本机使用
- 模型与向量调用为同步阻塞，并发依赖线程池

## License

MIT
