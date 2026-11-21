# AI 应用学习 · 项目驱动

## 怎么学（就这三条）

1. **概念 → 一个可运行例子**：每个知识点在 `basics/` 里有一个 20–50 行的完整代码，跑起来看现象，不单独"上课"。
2. **主线 → 一个真项目**：所有项目在 `proj1_assistant/` 这类目录里，2–4 个半天做完，能跑、能用、能给别人看。
3. **验收 → 能跑 + 有数字 + 能解释**：不答题，看结果。

## 一次学习怎么进行

```
① 我给一个例子（或一段项目代码）  →  你跑起来
② 你改一个参数/变量，再看输出     →  我解释现象
③ 回到项目里用上它                →  立刻有产出
④ 卡住 → 先看例子 → 改 → 再跑     →  超过 2 小时换路
```

**不写长日志，不抄概念。** 每步只记三行：能跑吗？对几个？卡在哪？

## 目录

```
ai-journey/
├── README.md            # 学习方式与规则
├── PLAN.md              # 路线（项目驱动）
├── progress.md          # 做到哪了、数字多少
├── start.ps1            # 一键启动（构建前端 + 起服务）
├── .env                 # 密钥与模型配置（不入库）
│
├── basics/              # 知识示例库：6 个概念，逐个跑
│
├── build/               # ★ 后端：RAG + Agent + 会话 + 统计
│   ├── app.py
│   ├── llm.py / store.py
│   ├── step*.py
│   ├── docs/ eval/
│   └── README.md        # 项目说明（架构、接口、指标）
│
├── frontend/            # ★ 前端：React + Vite
│   ├── src/
│   ├── vite.config.js
│   └── package.json
│
└── archive/             # 归档，平时不用看
    ├── week1/
    └── reference_rag/
```

## 三条硬规则

1. **学到的概念，48 小时内必须用进代码**，否则等于没学。
2. **卡住超过 2 小时就换路**：官方文档 → 问 AI → 找人，不要死磕。
3. **`.env` 永不入库**（`.gitignore` 已排除）。

## 关于密钥

`.env` 在仓库根目录，格式：

```
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-flash
PRICE_IN=0.15
PRICE_OUT=0.6
```

换服务商只改这几行，代码不用动。

## 当前进度

- 路线：`PLAN.md`（12 周，6 个项目）
- 做到哪了：`progress.md`
- 项目细节：各自的 `README.md`
