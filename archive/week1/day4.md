# W1 · Day 4 ｜ 2026-11-14 ｜ 并发、异步与会话存储

> 状态：已完成 ✅
> 用时：约 5 小时

---

## 一、今日目标

1. 亲眼看到「一个阻塞调用如何卡死整个服务」
2. 分清 `def` / `async def` / `await` 各自解决什么问题
3. 把 `history` 从客户端搬到服务端：内存 → 文件，重启不丢

---

## 二、核心知识（复习版）

### 1. 事件循环：一个人值班的收银台

uvicorn 默认**单进程、单事件循环**。可以想成只有一个收银员：

| 写法 | 收银员在干什么 |
|---|---|
| `def` + `time.sleep` | FastAPI 额外叫了个临时工（线程池），收银员继续接待 |
| `async def` + `time.sleep` | 收银员亲自去后面数钱，**队伍全卡住** |
| `async def` + `await asyncio.sleep` | 收银员说"您稍等"，转头接待下一位，2 秒后回来 |

**关键区别**：`await` 是"主动让出"，`time.sleep` 是"占着不放"。

### 2. 三种写法对照

```python
@app.get("/a")
def a():                 # 线程池执行（默认 40 线程），阻塞不影响别人
    time.sleep(2)

@app.get("/b")
async def b():           # 事件循环执行，time.sleep 会卡死全服务
    time.sleep(2)

@app.get("/c")
async def c():           # 事件循环执行，await 时让出，别的请求能进来
    await asyncio.sleep(2)
```

### 3. 那为什么 `day4_server.py` 的 `/chat` 用 `def`？

因为它内部调用的是**阻塞**的 `urllib`。放线程池里，10 个并发就用 10 个线程，互不阻塞。
如果写成 `async def` 却直接调 `urllib`，就会变成 `/slow/async-block` 那种灾难。

**规则：阻塞代码要么放在 `def` 里，要么用异步库（httpx/aiohttp）配 `async def`。**

### 4. 会话存储：历史从客户端搬到服务端

| 方案 | 重启后 | 多机共享 | 并发安全 |
|---|---|---|---|
| 进程内存字典 | ❌ 丢 | ❌ | ✅ |
| **JSON 文件**（今天） | ✅ 在 | ❌ | ⚠️ 同文件并发写会覆盖 |
| 数据库 / Redis | ✅ | ✅ | ✅ |

今天的接口：

```
POST /chat            {"session_id": "test1", "message": "我叫小明"}
GET  /session/test1   查看该会话完整历史
GET  /sessions        列出所有会话
```

历史落在 `sessions/test1.json`，服务重启后仍在。

---

## 三、动手实验

```powershell
cd C:\Users\20647\Desktop\AI_WorkPlace\ai-journey\week1
python -m uvicorn day4_server:app --port 8000
```

### 实验 1：三个接口，同样耗时 2 秒

开另一个窗口：

```powershell
python day4_bench.py /slow/def 3
python day4_bench.py /slow/async-block 3
python day4_bench.py /slow/async-ok 3
```

**预期结果（已实测）：**

| 接口 | 3 并发总耗时 | 说明 |
|---|---|---|
| `/slow/def` | **2.04s** | 线程池，三个同时睡 |
| `/slow/async-block` | **6.02s** | 事件循环被占，排队 |
| `/slow/async-ok` | **2.02s** | `await` 让出，三个同时计时 |

再把并发改成 10 跑一遍，观察 `async-block` 是否变成约 20 秒。

### 实验 2：会话存储 + 重启不丢

```powershell
# 两轮对话（同一个 session_id）
curl.exe -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" --data-binary "@c1.json"   # {"session_id":"test1","message":"我叫小明"}
curl.exe -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" --data-binary "@c2.json"   # {"session_id":"test1","message":"我叫什么？"}

# 查看历史
curl.exe -s http://127.0.0.1:8000/session/test1
```

然后 **Ctrl+C 停掉服务 → 重新启动 → 再查一次** `/session/test1`。
历史还在，就说明状态真的外置到文件了。

---

## 四、改造作业

1. **并发放大**：把 `day4_bench.py` 的并发数改成 10，分别跑三个接口，记录总耗时并解释差异。
2. **清空会话**：新增 `DELETE /session/{sid}`，删除对应的 JSON 文件，返回删除结果。
3. **会话列表增强**：`GET /sessions` 现在只返回名字，改成返回 `{session_id, turns, updated_at}`（文件修改时间）。

---

## 五、复盘题

1. 为什么 `async def` 里用 `time.sleep` 会卡死整个服务，而 `def` 里不会？
2. `await asyncio.sleep` 和 `time.sleep` 的本质区别是什么？
3. 既然 `def` 能靠线程池并发，为什么还要用 `async def`？
4. 会话存 JSON 文件有什么风险？什么场景必须换成数据库？
5. 如果服务部署到两台机器上，`sessions/` 目录会发生什么？

---

## 六、答案与批改

### Q1 为什么 `async def` + `time.sleep` 会卡死 —— ⚠️ 方向对，机制没说到

你的答案：「time.sleep 是阻塞代码，async def 是异步函数，用阻塞代码会卡死服务」。

**精确版本**：`async def` 由**事件循环（单线程）**直接执行。`time.sleep` 让这唯一的线程停下来，期间**所有协程都无法推进**——包括其他请求。
`def` 会被 FastAPI 丢进**线程池**，阻塞的只是一个工作线程，事件循环继续接待别人。

一句话：**一个卡的是“唯一的收银员”，一个卡的是“临时工”。**

### Q2 `await asyncio.sleep` 与 `time.sleep` 的本质区别 —— ⚠️ 表述模糊

你的答案：「await 前的 await 本就能让函数异步并发」。

**精确版本**：区别不在“函数是不是异步的”，而在**是否交还执行权**：

- `time.sleep(2)`：线程原地停 2 秒，同时**死死占着**事件循环
- `await asyncio.sleep(2)`：向事件循环注册一个 2 秒定时器，**立刻交出控制权**，循环去处理别的请求，2 秒后再回来

`await` 是“我先让开”，`sleep` 是“我占着不动”。

### Q3 既然 `def` 能并发，为什么还要 `async def` —— ⚠️ 只说对了一小半

你答“请求过多线程池不够”，这是对的，但只是一部分：

1. **线程池有上限**（默认 40），超过就排队——只是把“卡死”换成了“排长队”
2. **线程开销大**：每个线程默认约 8MB 栈 + 上下文切换成本，几千并发扛不住
3. **IO 密集型场景异步更划算**：单线程可支撑上万并发连接
4. **异步能干净地取消/超时**：`asyncio.wait_for` 可以中断，线程做不到
5. 生态有原生异步库（httpx / aiohttp），不会阻塞循环

### Q4 JSON 文件存储的风险 —— ✅ 对

你答出两个核心：**无法多机共享、并发写会覆盖**。补充：

- 无锁、无事务：并发写可能写坏文件
- 无查询能力：文件一多只能全量遍历
- 无权限/审计/备份机制
- 适用场景：单机、低频、个人项目；一旦多用户并发或多机部署，必须换数据库/Redis

### Q5 部署到两台机器会怎样 —— ❌ 概念偏了

你说“目录紊乱、sid 可能重复”。**真正的问题是：两台机器各自有本地 `sessions/` 目录，互不可见。**

- 请求被负载均衡轮到另一台 → 同一个 `session_id` 读不到历史 → **“失忆”**
- 两台各写各的 → 数据分叉，再也对不上

解决方式：
1. **共享存储**（Redis / 数据库 / 网络文件系统）—— 推荐
2. **粘性会话**：把同一用户固定到同一台机器 —— 临时方案，机器挂了照样丢

---

## 七、踩坑记录

1. **跑错接口**：并发测速时连续跑了两次同一个接口，误以为是“第二个接口变快了”。教训：脚本要打印路径，人要看第一行
2. **`history.pop()` 误解**：以为能删会话，实际删的是列表最后一条消息；且空列表会抛 `IndexError` → 500
3. **删文件前没检查存在**：`unlink()` 对不存在的文件抛 `FileNotFoundError`，正确做法是先 `exists()` 返回 404
4. **时间戳不是给人看的**：`st_mtime` 是 1970 年起的秒数，接口应返回 ISO 字符串
5. **改代码没生效**：`uvicorn` 不加 `--reload` 不会自动重载，必须重启

---

## 八、今日验收

- [x] 三个接口的并发耗时符合预期：3 并发 2.04 / 6.02 / 2.02
- [x] 并发改 10 后，`async-block` 线性增长：2.03 / **20.05** / 2.04
- [x] `/chat` 两轮能记住上文（同 session_id）
- [x] 重启服务后 `/session/test1` 历史仍在
- [x] 三个改造作业完成（并发放大、`DELETE` 用 `unlink`、`/sessions` 返回 turns/updated_at）
- [x] 五道复盘题作答（Q4 对；Q1/Q2/Q3 需补精确表述；Q5 需重答）

---

## 九、明日预告（Day 5）

健壮性与工程化：超时、重试、限流、统一错误结构、日志、pytest 测试。
