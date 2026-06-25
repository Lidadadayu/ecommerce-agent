# 快速复现指南

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

如果需要读取 PDF 知识文件：

```bash
pip install pypdf
```

## 2. 配置环境变量

复制：

```bash
copy .env.example .env
```

PowerShell 也可以：

```powershell
Copy-Item .env.example .env
```

默认领域：

```env
ACTIVE_DOMAIN=robot_vacuum
```

## 3. 导入扫地机器人知识库

把原始文件放入：

```text
domain_packs/robot_vacuum/raw/
```

然后运行：

```bash
python scripts/import_robot_vacuum_knowledge.py
```

生成后的知识库位于：

```text
data/knowledge/robot_vacuum/
```

## 4. 运行项目健康检查

```bash
python scripts/project_health_check.py
```

该脚本会检查：

- Python 版本
- 关键模块导入
- 当前领域包
- 商品数据库
- 工具注册表
- 路由
- RAG
- 完整 Agent 链路
- 数据库连接

数据库连接失败不会影响扫地机器人售前/RAG 演示。

## 5. 命令行快速演示

```bash
python scripts/quick_demo.py
```

## 6. 启动前端

```bash
python scripts/run_web.py
```

或者：

```bash
streamlit run app.py
```

## 7. 常用测试问题

```text
养宠家庭怎么选扫地机器人？
3000以内推荐一款扫拖一体机器人
RV4001 参数怎么样
对比 RV2001 和 RV4001
扫地机器人不回充怎么办
扫拖一体机器人拖地不出水怎么办
边刷多久换一次？
帮我查一下 O202605010001 这个订单
物流到哪了？
```

## 8. 数据库初始化

如果要测试订单、物流、售后工单：

```bash
python database/init_db.py
```

然后：

```bash
python database/test_query.py
```
