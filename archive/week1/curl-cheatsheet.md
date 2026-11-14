# curl 速查（针对本项目）

> 一句话：curl 就是"命令行里的浏览器 + 表单提交工具"。发一个 HTTP 请求，把响应打印出来。

## 0. Windows 第一坑：必须写 `curl.exe`

PowerShell 5.1 里 `curl` 是 `Invoke-WebRequest` 的别名，参数完全不兼容。
**所以本机一律写 `curl.exe`。**

## 1. 基本结构

```
curl.exe [选项] URL
```

| 选项 | 作用 | 什么时候用 |
|---|---|---|
| `-X POST` | 指定方法 | 提交数据 |
| `-H "Content-Type: application/json"` | 加请求头 | 发 JSON 必带 |
| `-d '...'` | 请求体（短、无中文时） | 简单测试 |
| `--data-binary "@file.json"` | 从文件读请求体 | **中文一律用这个** |
| `-s` | 静默，不显示进度条 | 几乎总是加 |
| `-N` | 关闭缓冲，边收边显示 | 测流式接口 |
| `-i` | 显示响应头（含状态码） | 排查问题 |
| `-o NUL` | 丢弃响应体 | 只看状态码 |
| `-w "%{http_code}"` | 打印状态码 | 只看状态码 |

## 2. 本项目的四个接口

```powershell
# GET：健康检查
curl.exe -s http://127.0.0.1:8000/health

# GET：模型信息
curl.exe -s http://127.0.0.1:8000/model

# POST：普通对话（单引号 + 内层双引号加反斜杠）
curl.exe -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{\"message\":\"hi\"}'

# POST：流式（-N 让输出不缓冲）
curl.exe -N -s -X POST http://127.0.0.1:8000/chat/stream -H "Content-Type: application/json" --data-binary "@h.json"

# 只看状态码
curl.exe -s -o NUL -w "%{http_code}`n" -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" --data-binary "@h.json"
```

## 3. PowerShell 的引号规则（最容易翻车）

PowerShell 5.1 把参数传给**原生程序**（curl.exe）时，会剥掉参数里的双引号——
这是它出了名的老 bug。实测：

```powershell
# 传给 python 的 argv[1] 实际是 {message:hi}，引号没了
python -c "import sys; print(sys.argv[1])" '{"message":"hi"}'
```

| 写法 | 结果 |
|---|---|
| `-d "{\"message\":\"hi\"}"` | ❌ 双引号在 PS 解析阶段就结束字符串，收到残渣 |
| `-d '{"message":"hi"}'` | ❌ 内层双引号被剥掉 → `{message:hi}` |
| `-d '{\"message\":\"hi\"}'` | ✅ **单引号 + 内层双引号前加 `\`**，推荐 |
| `-d "{\`"message\`":\`"hi\`"}"` | ✅ 用反引号转义也行，但难读 |

**结论：PS 5.1 里简单 JSON 用 `'{\"...\":\"...\"}'`；中文或复杂 JSON 一律走文件。**

（PowerShell 7 修正了这个行为，行为接近 bash；所以网上教程的写法经常对不上你的 5.1。）

另外：单引号里不能有单引号（JSON 里一般也不用），中文也可能受控制台代码页影响——**所以中文仍然走文件**。

## 4. 中文 JSON 的正确姿势（重点）

**永远不要**把中文 JSON 直接写在命令行里。用 Python 生成文件，再让 curl 读：

```powershell
python -c "import json;open('h.json','w',encoding='utf-8').write(json.dumps({'message':'我叫小明'},ensure_ascii=False))"

curl.exe -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" --data-binary "@h.json"
```

原因有三：
1. PowerShell 会先解析引号，JSON 被改得面目全非
2. 中文在命令行里可能被转成 GBK
3. `Set-Content -Encoding utf8` 在旧版 PowerShell 会加 BOM，导致 JSON 解析失败

用 Python 的 `open(..., 'w', encoding='utf-8')` 写出来的文件**没有 BOM**，最安全。

## 4. 常见报错对照

| 现象 | 原因 |
|---|---|
| `无法将"curl"项识别为...` | 没装 curl，或写了别名环境 |
| `Invoke-WebRequest : 参数 -X 无法识别` | 你敲的是 `curl` 而不是 `curl.exe` |
| `{"detail":[{"type":"json_invalid"...}]}` | JSON 被 PowerShell 改坏了 |
| `JSON decode error: Expecting value` | 请求体带 BOM 或为空 |
| `HTTP 422` | 校验失败（字段缺失/为空） |
| `HTTP 500` | 服务端代码崩了，看服务窗口的 traceback |

## 5. 什么时候不必用 curl

| 场景 | 更好的选择 |
|---|---|
| 第一次试接口 | 浏览器 `/docs`，点按钮 |
| 调试自己的服务 | `python day3_client.py` |
| 复杂请求、要保存历史 | Postman / VS Code REST Client 插件 |
| **读别人的 API 文档** | 必须看得懂 curl 示例 |

**结论**：日常调试不用死磕 curl，但**看得懂**是刚需——因为绝大多数 API 文档只给 curl 示例。

## 6. 看到文档里的 curl 怎么翻译成 Python

```text
curl -X POST https://api.xxx.com/v1/chat \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"m","messages":[...]}'
```

对照关系：

| curl | Python（urllib） |
|---|---|
| `-X POST` | `method="POST"` |
| `-H "Key: Value"` | `headers={"Key": "Value"}` |
| `-d '{...}'` | `data=json.dumps(...).encode()` |
| URL | 同一个 URL |
