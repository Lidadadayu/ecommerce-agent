# 重构说明（V1）

本版本把原项目从“补丁式增长”的结构整理为较稳定的中等粒度结构。

## 新目录结构

```text
ecommerce_agent/
├── app.py                         # Streamlit 前端入口
├── agent/                         # Agent 主流程、路由、记忆、审核、LLM 封装
│   ├── agent.py                   # 统一入口 run_agent()
│   ├── workflow.py                # LangGraph 工作流
│   ├── workflow_nodes.py          # LangGraph 节点
│   ├── workflow_edges.py          # LangGraph 条件分支
│   ├── legacy_agent.py            # 旧流程 fallback，不再作为主入口
│   ├── rule_router.py             # 规则路由
│   ├── llm_router.py              # LLM 兜底路由
│   ├── slot_filling.py            # 售后槽位补全
│   ├── tool_result_handler.py     # 工具结果闭环
│   ├── rag_policy_helper.py       # RAG 政策补充
│   ├── memory.py                  # 会话记忆
│   ├── domain_guard.py            # 领域边界
│   ├── human_review.py            # 人工审核判断
│   ├── human_review_queue.py      # 人工审核队列
│   ├── llm_client.py              # LLM 调用
│   ├── constants.py               # 常量
│   └── patterns.py                # 正则工具
├── tools/                         # 业务工具
├── rag/                           # RAG 检索与知识库服务
├── database/                      # 数据库连接和初始化
├── domain_packs/                  # 领域包，如 robot_vacuum
├── data/                          # 知识库、种子数据、运行数据
├── scripts/                       # 脚本工具
└── tests/                         # 测试/手动验证脚本
```

## 主要变化

1. 删除 `__pycache__`、旧归档代码、重复前端文件。
2. 删除 `.env`，改为 `.env.example`，避免泄露本地密钥。
3. 合并过碎的一级目录：`graph/`、`memory/`、`llm/`、`common/`、`guardrails/`、`ops/` 已并入 `agent/` 或 `scripts/`。
4. 保留 `tools/`、`rag/`、`database/`、`domain_packs/`，因为它们是明确边界模块。
5. 前端仍调用 `from agent.agent import run_agent`，不需要改前端业务调用方式。

## 运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

如需初始化数据库：

```bash
python database/init_db.py
```

如需导入扫地机器人知识库：

```bash
python scripts/import_robot_vacuum_knowledge.py
```

如需查看人工审核队列：

```bash
python scripts/review_console.py list
```
