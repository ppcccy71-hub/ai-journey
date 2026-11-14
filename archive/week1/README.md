# Week 1 · 环境与工程基础

> 目标：从"调用一个 API"到"做出一个能给别人用的命令行工具"，并学会用 Git 管理它。
> 时间：20–30 小时。产出物：流式 CLI 聊天工具 v0（多轮、可切模型、有成本统计）。

---

## 文件索引（按学习天数）

| 天 | 学习日志 | 代码 | 主题 | 状态 |
|---|---|---|---|---|
| Day 1 | `day1.md` | `day1_check_env.py`<br>`day1_first_call.py` | 环境自检、首次调用、手写 SSE、token / 温度 / 截断 | ✅ 完成 |
| Day 2 | `day2.md` | `day2_chat_skeleton.py`<br>`day2_chat_solution.py`<br>`day2_demos.py` | 生成器与惰性求值、多轮对话、上下文成本 | ✅ 完成 |
| Day 3 | `day3.md` | `day3_server.py`<br>`day3_client.py`<br>`day3_stateless_demo.py` | FastAPI、无状态、服务端 SSE、JSON 校验 | ✅ 完成 |
| Day 4 | `day4.md` | `day4_server.py`<br>`day4_bench.py`<br>`day4_path_demo.py` | 事件循环、`def` vs `async def`、会话存储（内存→文件）、pathlib | ✅ 完成 |
| Day 5–7 | — | — | 见下方任务清单 | ⏳ |

**通用文件**

| 文件 | 作用 |
|---|---|
| `.env` / `.env.example` | 密钥与模型配置（`.env` 不入库） |
| `curl-cheatsheet.md` | curl 速查，含 PowerShell 引号坑 |
| `_template.md` | 新一天日志的模板 |

**命名规则（以后照此扩展）**

- `dayN_xxx.py` = 第 N 天写的代码
- `dayN.md` = 第 N 天的学习日志（复习用）
- 跨天复用的工具函数放在最早需要它的那天文件里，后续 `import` 引用

---

## 任务清单

### Day 1（今天，2–3 小时）

- [ ] 跑 `python day1_check_env.py`，把每个 `[WARN]` / `[FAIL]` 处理掉
- [ ] 拿到一个 API Key（DeepSeek / 通义 / 智谱 / OpenAI 任选，OpenAI 兼容即可）
- [ ] 复制 `.env.example` 为 `.env`，填 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`
- [ ] `python day1_first_call.py --mock` —— 先看流式机制，不花钱
- [ ] `python day1_first_call.py "用一句话解释什么是 token"` —— 真机跑通
- [ ] 加 `--show-raw` 再跑一次，**看清每一帧长什么样**
- [ ] 加 `--think` 跑一个需要推理的问题（如"9.11 和 9.8 谁大"），对比有无思维链

### Day 2（2–3 小时）

- [ ] 通读 `day1_first_call.py`，用自己的话回答：
      1. `stream: true` 改变了什么？
      2. 为什么 `yield` 能实现"边生成边打印"？
      3. `TTFT` 和"总耗时"分别影响什么用户体验？
- [ ] 改 `--system` 和 `--temperature`（试 0 / 0.7 / 1.5），记录输出差异
      （注意：DeepSeek 思考模式下 temperature 不生效，要在普通模式下测）
- [ ] 把观察写进当天的 `dayN.md`（Day 1 就是 `day1.md`）

### Day 3（3–4 小时）

- [ ] 写 `chat.py` v0：多轮对话（`while True` 读输入，`/exit` 退出）
- [ ] 历史消息拼进 `messages`，观察"上下文越长，输入 token 越多"
- [ ] 处理空输入、Ctrl+C 中断、超长输入

### Day 4（3–4 小时）

- [ ] 给 `chat.py` 加流式输出（复用 `stream_real`）
- [ ] 每轮打印：本轮 token、累计 token、累计成本
- [ ] 加 `/clear` 清空上下文、`/model xxx` 切换模型

### Day 5（3–4 小时）

- [ ] 加健壮性：超时重试（最多 2 次，指数退避）、401/429 友好提示
- [ ] 把配置抽到 `config.py` 或命令行参数
- [ ] 用 `argparse` 支持 `--model`、`--temperature`、`--system`

### Day 6（2–3 小时）

- [ ] `git init`，写 `.gitignore`（必须含 `.env`、`__pycache__`、`.venv`）
- [ ] 写 `README.md`：怎么装、怎么配 key、怎么跑、截图
- [ ] 提交并推到 GitHub（仓库名建议 `llm-chat-cli`）

### Day 7（2 小时）

- [ ] 复盘：对照下方验收标准自评
- [ ] 写第一篇公开笔记《一次大模型请求的旅程：从 prompt 到逐字输出》
- [ ] 更新 `progress.md`

## 验收标准（能不能算过关）

1. 陌生人按 README 能在 5 分钟内跑起来
2. `chat.py` 支持多轮对话、流式输出、切模型、成本累计
3. 断网 / key 错误 / 余额不足时，有**人话**提示，而不是 Python 报错栈
4. 能准确说出：一次请求的输入 token 由什么决定，输出 token 由什么决定
5. 代码已推送 GitHub，`.env` 没有被提交

## 本周核心概念（学完要能讲清）

- **Token**：模型的最小计费与处理单位，中文约 1 字 ≈ 0.6–1 token
- **上下文窗口**：一次请求能塞进去的最大 token 数，超了就报错或截断
- **SSE（Server-Sent Events）**：`data: {...}\n\n` 的文本流协议，流式输出的底层
- **TTFT vs 总耗时**：首字延迟决定"感觉快不快"，总耗时决定"等多久"
- **temperature**：采样随机性，0 ≈ 确定，>1 ≈ 发散
- **system / user 消息**：角色不同，模型对待方式不同
- **成本公式**：`输入token × 单价 + 输出token × 单价`

## 卡住了怎么办

1. 先看 `--show-raw` 的原始帧，确认是网络问题还是解析问题
2. 查服务商官方文档的"错误码"章节
3. 2 小时还没解决，把报错原文贴给 AI 或同学，别硬扛
