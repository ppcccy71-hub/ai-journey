# W1 · Day 2 ｜ 2026-11-12 ｜ 读懂流式代码，写出多轮对话

> 状态：已完成 ✅
> 用时：约 5 小时（含三轮代码返工）

---

## 一、今日目标

1. 看懂 `day1_first_call.py` 背后的四个机制：生成器、逐行读、异常边界、TTFT
2. 能用自己的话解释"为什么 `yield` 能实现边生成边打印"
3. 动手写 `chat.py` v0：多轮对话，让模型"记得"上一句

---

## 二、核心知识（复习版）

### 1. 生成器与惰性求值

普通函数 `return` 一次交全部；生成器函数用 `yield` **交一个、暂停、等下次要**。

```python
def make_gen():
    for i in range(3):
        yield i          # 每 yield 一次就暂停在这里
```

- 调用 `make_gen()` **不会执行函数体**，只创建一个生成器对象
- 只有 `for x in ...` / `next()` 时才开始执行
- 好处：**内存恒定**（不装整个列表）、**首字节延迟低**（不用等全部算完）

这就是流式的根基：服务端一边生成、客户端一边收，而不是等全部生成完再一次性返回。

### 2. HTTP 流式响应：`resp` 是"还在流动的管子"

```python
with urllib.request.urlopen(req, timeout=180) as resp:
    for raw in resp:          # 逐行迭代
```

- `resp` 是类文件对象，**迭代它 = 读一行处理一行**
- `resp.read()` 会**阻塞到连接关闭**才返回全部内容——流式场景下等于把流式变回非流式
- 每行形如 `data: {...}`，空行是 SSE 的帧分隔符

### 3. 异常的传播边界

```python
try:
    stream = stream_real(...)   # 只是创建生成器，不执行
    for obj in stream:          # 真正执行在这里
        ...
except urllib.error.HTTPError:
    ...
```

生成器是**懒惰**的：HTTP 错误发生在**迭代时**（第一次 `next`），不在创建时。
所以 `try` 必须包住 `for` 循环——只包 `urlopen` 那一行等于没包。

### 4. TTFT 的测量口径

```python
if piece:                       # 只有真的拿到正文
    if ttft is None:
        ttft = time.perf_counter() - t0
```

TTFT 定义是"**第一个用户可见的字**"，不是"连接建立"、也不是"第一帧到达"。
第一帧往往只有 `role`，没有正文，所以必须在 `content` 分支里计时。

### 5. 多轮对话的本质

模型**没有记忆**。所谓"记得"，是客户端每次把整个 `messages` 重发一遍：

```python
messages.append({"role": "user", "content": user})
messages.append({"role": "assistant", "content": answer})   # 必须存完整回答
```

代价：第 N 轮的输入 token ≈ 前 N-1 轮的总和。

---

## 三、动手实验：三个小 demo

```powershell
python day2_demos.py        # 全部
python day2_demos.py 1      # 生成器
python day2_demos.py 2      # read() vs 逐行读
python day2_demos.py 3      # 异常何时抛出
```

**预期看到：**

| demo | 现象 | 说明 |
|---|---|---|
| 1 | 列表等 1.5s 才出结果；生成器每 0.3s 出一个 | yield 是分次交付 |
| 2 | `read()` 一次吐出全部；迭代逐行吐出 | 流式必须逐行 |
| 3 | 创建时不报错，迭代时才报错 | try 要包住循环 |

---

## 四、四问自测（先答，再看讲解）

### Q1

`stream_real` 里为什么用 `yield`，而不是 `return` 一个装好所有内容的列表？

**我的回答**：因为根据流式的本质知道流式本质是SSE协议，即边生成边输出，不会因为网络中断而丢失已打印的内容，而yield符合流式或者说SSE的性质
            yield就像是return和generator的结合体，他是生成一个再输出一个，例如返回列表内容，return是直接将整个列表内容全部返回出去
            但是yeild是生成一个列表内容再输出一个列表内容，当然加入sleep函数能控制好每次yield语句的暂停时间。

### Q2

`for raw in resp:` 读的到底是什么？为什么不用 `resp.read()`？

**我的回答**：读的是每一帧内容，他也和yield相类似，读取一帧内容然后处理一帧内容，resp.read()是一次性读完所有帧内容然后处理结束所有内容再发送给用
            户。

### Q3

`try/except` 为什么包住整个 `for` 循环，而不是只包 `urlopen`？

**我的回答**：因为生成器是懒惰的，错误通常发生在读取数据的时候，而不是在创建的时候出现错误，所以需要包住for循环。

### Q4

`ttft` 为什么在 `piece` 判断内部才记录，而不是循环一开始就记录？

**我的回答**：因为第一帧是role而不是content，所以一开始就记录偏早

---

## 五、动手任务：`chat.py` v0

**要求：**

- `while True` 读输入，`/exit` 退出，`/clear` 清空上下文
- 每轮：追加 user → 调接口流式打印 → 追加 assistant 完整回答
- 每轮打印：本轮 token、累计 token、累计成本

**骨架（只给结构）：**

```python
messages = [{"role": "system", "content": "你是一位简洁的老师。"}]
while True:
    user = input("你：")
    # 1. 处理 /exit /clear
    # 2. messages.append({"role": "user", "content": user})
    # 3. 流式打印，同时收集完整回答
    # 4. messages.append({"role": "assistant", "content": 完整回答})
    # 5. 累计统计
```

**三个必踩的坑：**

1. **边打印边收集**：`print(piece, end="")` 的同时要 `parts.append(piece)`，最后 `"".join(parts)`
2. **Ctrl+C 处理**：`KeyboardInterrupt` 要捕获，否则直接抛栈
3. **`/clear` 不是清空 messages**：要保留 system 那条

---

## 六、复盘题

1. 多轮对话时，`messages` 每轮会多出几条消息？
2. 为什么必须存 assistant 的**完整**回答，而不是只存打印出来的部分？
3. 不做 `/clear` 聊到第 50 轮，会发生什么？
4. 流式输出时，怎么"边打印"又"收集完整回答"？

---

## 七、答案与批改

### 代码四问

| 题 | 结果 | 点评 |
|---|---|---|
| Q1 `yield` vs `return` | ⚠️ 半对 | 抓住了"一个一个给"，但有两处概念错误 |
| Q2 `for raw in resp` | ✅ 对 | "读一帧处理一帧、read 一次性读完"——本质正确，只是表述口语化 |
| Q3 `try` 的范围 | ✅ 对 | "生成器是懒惰的，错误在读取时才发生"——准确 |
| Q4 TTFT 计时位置 | ⚠️ 方向对 | 说得出道理，但没说清机制 |

**Q1 正确说法**：`return` 交出结果并**结束函数**；`yield` 交出一个值后**暂停**，下次从暂停处继续。
- `yield` 不是"生成一个列表再输出"——它交的是**单个值**，列表只是接收容器
- `yield` 不是"return 和生成器的结合体"，而是**它让函数变成生成器**

**Q2 补充**：你的回答是对的——迭代 `resp` 就是"读一帧、处理一帧"，`read()` 是一次性读完。
两点可以更精确：

- 所谓"一帧"在传输层其实是**一行**（`data: {...}`），帧与帧之间靠**空行**分隔，这就是代码里 `if not line: continue` 的原因
- `read()` 的准确行为是**阻塞到连接关闭**才返回；流式连接可能持续几十秒，用它等于主动放弃流式

**Q3 补充**：HTTP 错误在第一次 `next()` 时才抛出（创建生成器不执行函数体），所以 `try` 必须包住 `for`。

**Q4 精确说法**：TTFT 量的是"**第一个用户可见的字**"。SSE 第一帧往往只有 `role`、`content` 为空，
所以在循环开始记时间会偏早；必须在 `if piece:` 分支里记。

### 复盘题答案

1. **每轮 +2 条**：一条 user、一条 assistant。system 始终 1 条，所以第 N 轮后共 `1 + 2N` 条。
2. **因为下一轮要把全部历史重发**。只存屏幕上的字不够——中断时的半句、换行、以及"打印了但没进 parts"都会造成上下文与实际不符，模型就会"记得一半"。
3. **上下文线性膨胀**：输入 token 每轮增长（第 50 轮可能要几千 token），后果是：成本飙升、延迟变高、最终撞上下文上限报错、模型注意力被稀释。
4. **打印的同时 append**：`print(piece, end="")` 与 `parts.append(piece)` 并行，循环结束后 `"".join(parts)`。

---

## 八、踩坑记录

1. **漏写 `.append()`**：`messages{"role": "user"}` → `SyntaxError: invalid syntax`
2. **变量写成字符串**：`"content": "user"` → 模型收到字面量 `user`，说不出用户的名字
3. **`/clear` 放进退出元组**：`if user in ("/clear", "/exit"): break` → 永远清不了空
4. **命令分支漏 `continue`**：`/history` 被当成普通消息发给模型，模型回"我是你的历史老师"，白花 token
5. **三个计数器写在 `while` 里**：`total_in` 每轮归零，累计与增量全部失效
6. **系统代理导致 SSL EOF**：`127.0.0.1:7897` 代理未启动，Python 自动读系统代理被拦；curl 直连正常。已改为默认直连，`LLM_PROXY` 可开关

---

## 九、今日验收

- [x] 三个 demo 跑通，能解释每个现象
- [x] 四问全部作答（Q2、Q3 正确；Q1、Q4 方向对、表述可再精确）
- [x] `chat.py` 连续对话 3 轮以上，模型记得上文
- [x] `/clear` 后模型"失忆"，输入 token 从 39 回到 19
- [x] 每轮能看到累计 token 与成本
- [x] 三个改造练习完成（`/history`、`/count`、增量统计）

---

## 十、明日预告（Day 3）

FastAPI：把 `chat.py` 变成 HTTP 接口，浏览器能访问；引入并发与流式响应。
