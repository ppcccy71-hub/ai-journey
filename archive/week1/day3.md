# W1 · Day 3 ｜ 2026-11-13 ｜ 把脚本变成 Web 服务

> 状态：已完成 ✅
> 用时：约 5 小时

---

## 一、今日目标

1. 理解 Web 服务的三个基本概念：路由、请求体、状态码
2. 把 `chat.py` 改造成 HTTP 接口，别人能通过网络调用
3. 理解「服务端无状态」：为什么历史必须由客户端带
4. 复用手写 SSE 的知识，做出浏览器里逐字出现的聊天页

---

## 二、核心知识（复习版）

### 1. CLI → HTTP 的映射

| 命令行版 | Web 版 |
|---|---|
| `input("你：")` | HTTP 请求体 `{"message": "..."}` |
| `print(piece)` | HTTP 响应（一次性 JSON 或流式 SSE） |
| 程序里 `messages` 变量 | **不能存**，必须客户端每次传上来 |
| 一个用户 | 同时 N 个用户，彼此隔离 |
| Ctrl+C 退出 | 服务常驻，重启就丢内存 |

### 2. FastAPI 三件套

```python
app = FastAPI()                       # 1. 应用对象

class ChatRequest(BaseModel):         # 2. 请求体模型（自动校验 + 自动文档）
    message: str = Field(..., min_length=1)

@app.post("/chat")                    # 3. 路由装饰器：路径 + 方法
def chat(req: ChatRequest):
    return {"reply": "..."}
```

`/docs` 页面是自动生成的，可以直接点 "Try it out" 调接口——**这是 FastAPI 最大的效率优势**。

### 3. 无状态（今天最重要的一条）

`chat.py` 里 `messages` 是**进程内存里的一个列表**，所以它能"记住"上下文。
Web 服务不能这么做，因为：

- 同时有 100 个用户，一个全局列表会**互相串台**
- 多进程部署（uvicorn workers）时，各进程内存**互不可见**
- 服务重启，内存**全部丢失**

所以标准做法：**历史由客户端保存并每次带上**，服务端只做无状态计算。

```json
{"message": "我叫什么？", "history": [{"role":"user","content":"我叫小明"},
                                      {"role":"assistant","content":"你好，小明！"}]}
```

### 4. StreamingResponse = 生成器 + HTTP

```python
def event_generator():
    for piece in iter_reply(...):
        yield f"data: {json.dumps({'content': piece})}\n\n"
    yield "data: [DONE]\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- 生成器每 `yield` 一次 → 向客户端推一帧
- Day 2 你是**解析** SSE 的一方，今天你是**生产** SSE 的一方
- 格式必须一模一样：`data: {...}` + 两个换行

### 5. 状态码：谁错了，看数字

| 码 | 含义 | 谁的问题 |
|---|---|---|
| 200 | 成功 | — |
| 400 | 请求格式不对（如 JSON 写错） | 客户端 |
| 401 | 没认证 / key 错 | 客户端 |
| 422 | 字段校验失败（如 message 为空） | 客户端 |
| 429 | 请求太频繁 | 客户端 |
| 500 | 服务端内部错误（如没配 key） | 服务端 |

422 是 FastAPI 根据 Pydantic 模型**自动**返回的，不用写一行判断。

### 6. 并发的伏笔（Day 4 展开）

```python
@app.post("/chat")
def chat(...):          # def：FastAPI 丢到线程池执行，能并发

@app.post("/chat/stream")
async def chat_stream(...):   # async def：跑在事件循环里
```

如果把**阻塞**的 `urllib` 调用直接写进 `async def`，整个服务会被一个请求卡住——这就是 Day 4 要解决的问题。

---

## 三、动手实验

```powershell
cd C:\Users\20647\Desktop\AI_WorkPlace\ai-journey\week1
python -m uvicorn day3_server:app --reload --port 8000
```

然后依次验证：

| 验证 | 操作 | 期望 |
|---|---|---|
| 健康检查 | 浏览器打开 `http://127.0.0.1:8000/health` | `{"status":"ok","model":"deepseek-flash"}` |
| 聊天页 | 打开 `http://127.0.0.1:8000/` | 输入问题，文字**逐字出现** |
| 自动文档 | 打开 `http://127.0.0.1:8000/docs` | 能看到三个接口，可点 Try it out |
| JSON 接口 | Swagger 里调 `/chat` | 返回完整 reply |
| 校验 | message 传空字符串 | 返回 **422** |

**curl 测试（注意 Windows 下 JSON 要用文件传，否则引号会被吃掉）：**

```powershell
'{"message":"Say hi in five words."}' | Out-File -Encoding utf8 _body.json
curl.exe -s -X POST "http://127.0.0.1:8000/chat" -H "Content-Type: application/json" --data-binary "@_body.json"
curl.exe -s -N -X POST "http://127.0.0.1:8000/chat/stream" -H "Content-Type: application/json" --data-binary "@_body.json"
```

---

## 四、改造作业（三个，由易到难）

1. **加参数**：给 `ChatRequest` 加 `max_tokens: int = Field(200, ge=1, le=2000)`，并传进 payload。
   验证：在 `/docs` 里能看到新字段，且不传时有默认值。

2. **加接口**：新增 `GET /models`，返回 `{"model": MODEL, "base": BASE}`。
   验证：`/docs` 里出现第四个接口。

3. **带历史**：用 curl 给 `/chat` 传一段 `history`，让模型说出"你上一轮告诉它的名字"。
   验证：不传 history 时它不知道名字；传了就知道。

---

## 五、复盘题

1. 为什么服务端不能像 `chat.py` 那样把 `messages` 存成全局变量？说出三个理由。
2. 两个用户同时请求 `/chat`，为什么不会看到对方的历史？
3. `StreamingResponse` 里的生成器，是在哪一刻开始执行的？
4. 422 错误是谁返回的？它为什么不需要你手写校验？
5. 浏览器里为什么能逐字显示？中间经过了哪几步？

---

## 六、答案与批改

### Q1 为什么不能存全局变量 —— ✅ 对

你答出了三条：**用户串台、多进程内存隔离、重启丢失**。补充第四条：**无法水平扩容**——加机器后每台各存各的，用户请求打到不同机器就"失忆"。

### Q2 为什么不会串台 —— ✅ 对

因为历史在客户端，服务端每次只做无状态计算。补充：真实产品把历史存在**浏览器 localStorage 或后端数据库（按 user_id）**，但都不在"模型内存"里。

### Q3 生成器何时执行 —— ⚠️ 半对

"从输出第一个字开始执行"混淆了两件事：

- 调用 `event_generator()` **只创建对象**，函数体一行都不执行
- `StreamingResponse` 在**开始向客户端发送响应**时才开始迭代它（第一次 `next()`）
- 而**第一帧内容**要等模型产出第一个 token 才有

准确说法：**生成器函数体在第一次被迭代时执行；Starlette 开始发送响应体时迭代它。**

### Q4 422 谁返回 —— ✅ 对

Pydantic 校验失败 → FastAPI 转成 422 + `detail` 数组。声明式：写规则，不写 if。补充：具体是由 FastAPI 的 `RequestValidationError` 异常处理器统一生成的。

### Q5 浏览器为何逐字显示 —— ❌ 未答

完整链路：

1. 浏览器 `fetch('/chat/stream')` 发 POST
2. FastAPI 返回 `StreamingResponse`，`media_type=text/event-stream`
3. 服务端每 `yield` 一帧 `data: {...}\n\n`，**立即**通过网络发出（不攒批）
4. 浏览器 `response.body.getReader()` 增量读取字节流
5. `TextDecoder` 解码 → 按行切分 → `JSON.parse` → 追加到 DOM

**中间任何一环做了"攒完再发"，逐字效果立刻消失。**


---

## 七、踩坑记录

1. **`max_tokens` 三处只改两处**：漏了调用处传参 → `TypeError: missing 1 required positional argument` → 接口 500。**语法检查发现不了，必须真的调一次**
2. **JSON 少逗号**：数组里两个对象直接相邻 → 解析失败
3. **PowerShell 里 `curl` 不是 curl**：5.1 里它是 `Invoke-WebRequest` 别名，参数不认 → 必须写 `curl.exe`
4. **PowerShell 吃引号**：命令行内联 JSON 会被改坏 → 中文一律用文件 + `--data-binary "@file"`
5. **`Set-Content -Encoding utf8` 带 BOM**：请求体开头多出隐藏字节 → JSON 解析失败
6. **空格能通过 `min_length=1`**：需求是"非空"，但空格长度是 1 → 需要 `strip()` 后校验
7. **500 不是用户输入的问题**：500 = 服务端 bug；4xx 才是客户端错

---

## 八、今日验收

- [x] 服务能启动，`/health` 返回 ok
- [x] 浏览器聊天页能逐字输出
- [x] `/docs` 能调通 `/chat`
- [x] 空 message 返回 422（空格返回 200，暴露 `min_length` 的局限）
- [x] 三个改造作业完成（`max_tokens`、`/model`、`history` 对照实验）
- [x] 五道复盘题作答（Q3 半对、Q5 需补）

---

## 九、明日预告（Day 4）

并发与异步：为什么 `async def` + 阻塞调用会卡死整个服务；怎么用 `asyncio` 或者线程池解决；顺便给服务加一个"会话存储"（内存字典版）。

---

## 附录 A：无状态，再讲一遍（当天答疑）

### 一句话定义

**服务端不记住「你是谁、你之前说过什么」；每个请求自带全部必要信息，算完就忘。**

### 对照实验（`day3_stateless_demo.py`）

| 场景 | 有状态（全局变量） | 无状态（历史随请求） |
|---|---|---|
| 小红问「我叫什么」 | 答"你叫小明" —— **串台** | 答"我不知道" —— 正确 |
| 服务重启后小明再问 | 记忆随进程消失 | 历史在客户端，照常回答 |

### 必须无状态的五个理由

1. **并发串台**：多人共用一个列表
2. **多进程隔离**：进程 A 的内存进程 B 读不到
3. **重启丢失**：内存清零
4. **无法扩容**：加机器后用户被分到新机器就失忆 ← 生产环境最致命
5. **无法测试/缓存**：结果依赖"之前发生过什么"，不可复现

### 三个常见误解

- **无状态 ≠ 不存数据**：数据库照样存；区别是存"数据"而非"会话状态"
- **无状态 ≠ 不能登录**：靠每次请求带 Cookie/Token，验完就忘
- **状态不是消失，是被外置**：客户端 / 集中存储 / 签名凭证，三选一

### 状态放哪里

| 位置 | 例子 | 特点 |
|---|---|---|
| 客户端 | localStorage 存聊天记录 | 简单，换设备就丢 |
| 集中存储 | Redis / 数据库按 user_id | 换设备能续，需额外组件 |
| 凭证里 | JWT | 零存储，但无法主动失效 |

### 判断三问

1. 重启会丢吗？ 2. 多台机器能随便切吗？ 3. 两个用户会互相影响吗？
三个都"不会"，才是无状态。

### 为什么 AI 服务天生无状态

模型每次推理独立，不记得上一次。OpenAI / DeepSeek 的 API 都要求每次重发 `messages`。
ChatGPT 网页版"记得你"，是**产品层**把历史存进数据库、请求前拼进去——模型本身没有记忆。

### 什么时候可以有状态

WebSocket 长连接、游戏房间、实时语音——这类靠"粘性会话"把用户固定到同一台机器。
除此之外，默认无状态。

---

## 附录 B：FastAPI 能直接读 JSON 文件吗

能。JSON 只是数据，谁读都行：

| 谁读 | 用途 |
|---|---|
| `curl` 读 | 当作请求体发出去（`h.json`） |
| Python/FastAPI 读 | 当作数据源：会话持久化、测试数据、评测集、配置、知识库 |

**最小示例（会话存文件）：**

```python
import json
from pathlib import Path

def load_history(user):
    p = Path(f"sessions/{user}.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

def save_history(user, history):
    Path("sessions").mkdir(exist_ok=True)
    Path(f"sessions/{user}.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
```

**三个注意点：**

1. 读写都指定 `encoding="utf-8"`
2. 文件带 BOM 会解析失败，可用 `utf-8-sig` 兼容
3. 并发写同一文件会互相覆盖——文件适合低频/单用户，高并发要用数据库

**三级进化**：内存变量 → JSON 文件 → 数据库/Redis，本质都是把状态从进程里搬出去，搬得越远越可靠。
