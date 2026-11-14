# DeepSeek API 速记

## 基本调用
接口地址是 https://api.deepseek.com，使用 OpenAI 兼容格式。请求发到 /chat/completions，
请求体包含 model、messages、stream 三个关键字段。

## 模型
当前主力模型是 deepseek-flash，上下文长度 1M，支持思考模式与非思考模式。
思考模式默认开启，会先输出 reasoning_content 思维链，再输出 content 正文。
关闭方式是在请求体里传 thinking: {"type": "disabled"}。

## 计费
输入 token 与输出 token 分开计价。deepseek-flash 非高峰时段输入约 0.15 美元每百万 token，
输出约 0.6 美元每百万 token，高峰时段翻倍。缓存命中的输入价格极低。

## 流式输出
stream 为 true 时，服务端通过 SSE 逐帧推送 data: {...} 文本行，最后一帧是 [DONE]。
每一帧里的 choices[0].delta.content 就是新增的文字。

## 常见错误码
401 表示 key 无效，402 表示余额不足，404 表示模型名或地址不对，429 表示请求过于频繁，
422 表示参数校验失败。
