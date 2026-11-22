# ai-journey

AI 应用开发的练习仓库，包含一个可运行的本地知识库助手（RAG + Agent），以及学习过程中的示例代码和笔记。

## 目录

```
ai-journey/
├── build/         后端应用与学习步骤脚本（详见 build/README.md）
├── frontend/      React 前端
├── basics/        基础概念的可运行示例
├── archive/       早期练习与参考实现
├── start.ps1      一键启动脚本
├── PLAN.md        学习路线
└── progress.md    进度与指标
```

## 运行

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

需要先在根目录创建 `.env`（配置项见 `build/README.md`）。

## 示例代码

`basics/` 下的六个脚本分别演示：API 调用与计费、SSE 流式、生成器、异步阻塞、最小 FastAPI 服务、文件存储。均为独立可运行脚本。

## 项目材料

| 材料 | 路径 |
|---|---|
| 架构图 | `docs/architecture.svg` |
| 简历条目与面试追问 | `docs/resume.md` |
| 评测数据 | `build/RESULTS.md` |
| 项目说明 | `build/README.md` |

## 说明

- `archive/` 为过程材料，不参与运行
- 数据库、向量索引之外的数据均不入库，敏感配置见 `.gitignore`
