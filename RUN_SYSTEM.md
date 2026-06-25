# 系统启动说明

后续推荐统一使用“一键启动脚本”。

## 推荐启动方式

```bash
python scripts/run_system.py
```

默认地址：

```text
后端 API：http://127.0.0.1:8001
API 文档：http://127.0.0.1:8001/docs
前端页面：http://localhost:8502
```

如果端口被占用：

```bash
python scripts/run_system.py --auto-port
```

## Windows 双击启动

双击：

```text
start_system.bat
```

## 手动启动方式

终端 1：

```bash
python scripts/run_api.py --port 8001
```

终端 2：

```bash
python scripts/run_web_api.py --api-base-url http://127.0.0.1:8001
```

## 不推荐继续使用的旧启动方式

暂时不要使用：

```bash
streamlit run app.py
python scripts/run_web.py
```

它们是旧的本地直连模式，不走 FastAPI 服务层。

## 检查端口

```bash
python scripts/check_ports.py
```
