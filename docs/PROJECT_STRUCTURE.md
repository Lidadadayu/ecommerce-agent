# 项目结构说明

当前项目采用中等粒度结构，避免目录过深，也避免所有代码耦合在一个文件中。

```text
ecommerce_agent/
├── app.py                         # Streamlit 前端入口
├── .env.example                   # 环境变量示例
├── requirements.txt
│
├── agent/                         # Agent 核心层
│   ├── agent.py                   # 统一入口：run_agent()
│   ├── workflow.py                # LangGraph 工作流构建
│   ├── workflow_nodes.py          # 工作流节点
│   ├── workflow_edges.py          # 工作流条件分支
│   ├── graph_state.py             # Graph State
│   ├── rule_router.py             # 规则路由
│   ├── llm_router.py              # LLM 兜底路由
│   ├── slot_filling.py            # 缺槽补全
│   ├── tool_result_handler.py     # 工具结果闭环
│   ├── rule_agent.py              # 模板答案
│   ├── rag_policy_helper.py       # RAG 与回答融合
│   ├── memory.py                  # 会话记忆
│   ├── domain_loader.py           # 领域包加载
│   ├── domain_guard.py            # 领域边界
│   ├── human_review.py            # 人工审核判断
│   ├── human_review_queue.py      # 人工审核队列
│   ├── llm_client.py              # LLM 调用与润色
│   ├── constants.py
│   └── patterns.py
│
├── tools/                         # 业务工具层
│   ├── tool_registry.py           # 工具注册表
│   ├── business_tools.py          # 通用电商订单/物流/售后工具
│   └── robot_vacuum_tools.py      # 扫地机器人售前与知识工具
│
├── rag/                           # 知识库检索层
│   ├── knowledge_loader.py
│   ├── retriever.py
│   ├── bm25_retriever.py
│   ├── hybrid_retriever.py
│   ├── query_expander.py
│   ├── reranker.py
│   └── rag_service.py
│
├── database/                      # 数据库层
│   ├── db.py
│   ├── init_db.py
│   ├── schema.sql
│   └── test_query.py
│
├── domain_packs/                  # 领域包
│   └── robot_vacuum/
│       ├── domain_config.yaml
│       ├── prompt.yaml
│       ├── products.json
│       └── raw/
│
├── data/
│   ├── knowledge/                 # RAG 知识库
│   │   └── robot_vacuum/
│   ├── review_queue/              # 人工审核队列
│   └── runtime/                   # 运行日志、健康检查结果
│
├── scripts/                       # 脚本
│   ├── import_robot_vacuum_knowledge.py
│   ├── project_health_check.py
│   ├── quick_demo.py
│   ├── review_console.py
│   └── run_web.py
│
├── tests/
└── docs/
```

## 分层原则

### 1. agent/

Agent 核心层。负责：

- 用户输入进入系统后的流程控制
- 路由判断
- 多轮记忆
- 工具调用决策
- RAG 融合
- 人工审核
- 最终回复生成

### 2. tools/

业务工具层。负责执行真实业务动作，例如：

- 查询订单
- 查询物流
- 售后资格判断
- 创建工单
- 商品推荐
- 型号对比

### 3. rag/

知识库检索层。只负责检索和构造上下文，不直接改变业务状态。

### 4. domain_packs/

领域包。决定当前系统演示领域，例如：

- robot_vacuum：扫地机器人
- shaver：剃须刀，后续可扩展
- clothing：服装，后续可扩展

### 5. database/

数据库层。负责连接数据库和初始化表结构。

## 为什么不拆得更细

当前项目是教学和展示型工程，不建议采用过深的 `src/ecommerce_agent/services/...` 结构。  
过度拆分会增加新手理解成本，也会让修改流程变复杂。

现在采用的是中等粒度：

- 一级目录数量可控
- 核心功能边界清晰
- 前端调用简单
- 后续可继续演进
