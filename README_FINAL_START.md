# Ecommerce Agent 最终启动说明

## 一键启动

```bash
python scripts/run_system.py
```

端口被占用时：

```bash
python scripts/run_system.py --auto-port
```

开发调试模式：

```bash
python scripts/run_system.py --dev-mode
```

## 分别启动

后端：

```bash
python scripts/run_api.py --port 8001
```

前端：

```bash
python scripts/run_web_streaming.py --api-base-url http://127.0.0.1:8001
```

## 访问地址

```text
前端页面：http://localhost:8501
API 文档：http://127.0.0.1:8001/docs
流式接口：POST http://127.0.0.1:8001/api/chat/stream
```

## 入口检查

```bash
python scripts/entrypoint_health_check.py
```

## 流式接口测试

```bash
python scripts/streaming_api_smoke_test.py --query "扫地机器人不回充怎么办"
```

## 当前正式文件

```text
app_api_streaming.py              最终用户前端
frontend_stream_client.py         SSE 流式客户端
frontend_api_client.py            普通 API 客户端，用于 health/domain 等
api/server.py                     默认注册普通聊天和流式聊天
api/stream_routes.py              SSE 流式聊天路由
scripts/run_system.py             最终一键启动入口
```

## 不建议继续开发的旧入口

这些文件现在只是兼容入口或旧文档：

```text
app.py
app_api.py
app_api_humanized.py
scripts/run_system_streaming.py
scripts/run_api_streaming.py
scripts/run_web.py
scripts/run_web_api.py
scripts/run_web_api_humanized.py
README_REFACTOR.md
RUN_SYSTEM.md
```
