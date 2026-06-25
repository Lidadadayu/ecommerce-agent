# 运行日志与可观测性

系统现在会在每次调用 `agent.agent.run_agent()` 时自动写入一条运行日志。

日志文件位置：

```text
data/runtime/conversation_logs/agent_runs_YYYYMMDD.jsonl
```

每一行是一条 JSON，包含：

- run_id
- created_at
- elapsed_ms
- user_query
- intent
- tool_name
- arguments
- tool_result 摘要
- human_review 摘要
- human_review_task 摘要
- graph_error
- llm_error
- memory_brief
- final_answer_preview

## 查看最近日志

```bash
python scripts/show_agent_logs.py list
```

查看最近 50 条：

```bash
python scripts/show_agent_logs.py list --limit 50
```

查看某一天：

```bash
python scripts/show_agent_logs.py list --date 20260623
```

## 查看单条日志详情

```bash
python scripts/show_agent_logs.py show RUN20260623180000ABCDEF
```

## 查看统计信息

```bash
python scripts/show_agent_logs.py stats
```

输出示例：

```json
{
  "total": 20,
  "intent_count": {
    "robot_vacuum_search": 8,
    "robot_vacuum_knowledge_query": 5
  },
  "tool_count": {
    "robot_vacuum_search": 8,
    "robot_vacuum_knowledge_query": 5
  },
  "avg_elapsed_ms": 1280.52,
  "error_count": 0
}
```

## 为什么需要这个模块

之前系统虽然能跑，但如果前端回答异常，排查成本比较高。现在每次调用都会留下可追踪记录，可以快速判断：

1. 用户问题被识别成了哪个 intent。
2. 调用了哪个 tool。
3. 工具参数是否正确。
4. 工具返回是否成功。
5. 是否触发人工审核。
6. LLM 是否报错。
7. 是否发生 LangGraph fallback。
8. 本轮耗时是否过高。

这比在前端临时 print 更适合项目复现和后续调试。

## 注意

日志中只保存摘要，不完整保存超长工具结果，避免日志过大。  
如果不想保留历史日志，可以直接删除：

```text
data/runtime/conversation_logs/
```
