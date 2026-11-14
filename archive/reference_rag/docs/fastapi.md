# FastAPI 速记

## 最小应用
用 FastAPI() 创建应用对象，用 @app.get 和 @app.post 装饰器定义路由，每个路由函数返回字典
就会被自动序列化成 JSON。

## 请求体校验
用 Pydantic 的 BaseModel 定义请求体，字段用 Field 声明类型、默认值和约束。
例如 message: str = Field(..., min_length=1) 表示必填且至少一个字符。
校验失败时 FastAPI 自动返回 422，不需要手写 if 判断。

## 自动文档
启动服务后访问 /docs 可以看到自动生成的接口文档，能直接点击 Try it out 调用接口。
文档内容来自路由定义和 Pydantic 模型，不需要额外编写。

## 流式响应
用 StreamingResponse 包装一个生成器即可实现流式返回。生成器每 yield 一次，就向客户端推送一帧。
媒体类型要设置为 text/event-stream。

## 并发模型
普通 def 路由会被放进线程池执行，阻塞代码不会卡住事件循环。
async def 路由直接在事件循环里执行，如果内部调用阻塞函数（如 time.sleep 或同步网络请求），
整个服务会被卡住，其他请求只能排队。

## 依赖与配置
启动命令是 python -m uvicorn 模块名:app --port 8000。加上 --reload 可以在代码修改后自动重启。
