# ai-journey

面向金融场景的 AI 助手：金融合规问答（RAG）+ 行情监控（K 线 / 板块 / 异动解读）+ 金融计算（Agent），附带 MCP 与多知识库能力。

在线 Demo：https://earn-all-you-want.up.railway.app（访问口令 PCAI1907）

![CI](https://github.com/ppcccy71-hub/ai-journey/actions/workflows/ci.yml/badge.svg)

## 目录

```
ai-journey/
├── build/            后端（RAG / Agent / MCP / 监控）
├── frontend/         React 前端
├── docs/             架构图与 logo
├── Dockerfile
├── docker-compose.yml
├── railway.json
└── start.ps1
```

## 运行

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

需要先在根目录创建 `.env`（配置项见 `build/README.md`）。

## 文档

| 材料 | 路径 |
|---|---|
| 架构图 | `docs/architecture.svg` |
| 项目说明 | `build/README.md` |
| 评测数据 | `build/RESULTS.md` |

## 说明

- 仓库只保留运行所需的代码与文档，学习材料和过程文件已移除
- `.env` 不入库；数据库、向量索引之外的数据均被忽略
