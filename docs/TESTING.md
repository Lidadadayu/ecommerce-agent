# 测试说明

本项目增加了一组轻量级回归测试，目标不是做复杂评测，而是保证后续修改时核心功能不被改坏。

## 1. 安装测试依赖

```bash
pip install -r requirements-dev.txt
```

## 2. 运行全部测试

```bash
python scripts/run_tests.py
```

或者直接：

```bash
python -m pytest -q tests
```

## 3. 当前测试覆盖范围

```text
tests/
├── test_domain_pack.py          # 领域包加载
├── test_robot_rule_router.py    # 扫地机器人路由
├── test_robot_tools.py          # 商品推荐/详情/对比工具
├── test_tool_registry.py        # 工具注册与执行
├── test_rag_robot_vacuum.py     # RAG 检索
└── test_agent_smoke.py          # 完整 Agent 冒烟测试
```

## 4. 测试重点

### 领域包

确认当前：

```env
ACTIVE_DOMAIN=robot_vacuum
```

可以正确加载：

```text
domain_packs/robot_vacuum/domain_config.yaml
domain_packs/robot_vacuum/products.json
data/knowledge/robot_vacuum/
```

### 路由

确认这些问题不会被错误路由：

```text
养宠家庭怎么选扫地机器人 -> robot_vacuum_search
扫地机器人不回充怎么办 -> robot_vacuum_knowledge_query
对比 RV2001 和 RV4001 -> robot_vacuum_compare
RV4001 参数怎么样 -> robot_vacuum_detail
```

### 工具

确认扫地机器人商品工具可用：

```text
search_robot_vacuum_products
get_robot_vacuum_product_detail
compare_robot_vacuum_products
```

### RAG

确认知识库能检索到扫地机器人故障内容。

如果没有导入知识库，RAG 测试会自动跳过。

### 完整 Agent

确认：

```text
3000以内推荐一款扫拖一体机器人
扫地机器人不回充怎么办
```

能够经过主 Agent 返回非空答案。

## 5. 和 project_health_check.py 的区别

`project_health_check.py` 是运行环境检查，适合快速判断项目能不能跑。

`pytest tests/` 是回归测试，适合后续改代码前后确认功能没有被破坏。

推荐顺序：

```bash
python scripts/project_health_check.py
python scripts/run_tests.py
python scripts/quick_demo.py
```
