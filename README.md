终端 1：启动后端 API
在项目根目录运行：
python scripts/run_api.py --port 8001

看到类似下面内容，就不要关闭这个终端：
Application startup complete.
Uvicorn running on http://127.0.0.1:8001
终端 2：启动前端页面


再打开一个新的终端，仍然进入项目根目录，运行：
python scripts/run_web_api.py --api-base-url http://127.0.0.1:8001

然后浏览器打开：
http://localhost:8502
这就是你现在应该使用的前端页面。

向量知识库：

构建文档分片、生成 text-embedding-v3 embedding，并写入 Chroma 向量库：

python scripts/build_vector_store.py --domain robot_vacuum --reset

单独测试 similarity search：

python scripts/vector_search_demo.py "机器人拖地时不出水怎么办" --top-k 5

相关环境变量见 .env.example：EMBEDDING_MODEL、EMBEDDING_API_KEY、EMBEDDING_BASE_URL。
