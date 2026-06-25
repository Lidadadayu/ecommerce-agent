"""
将下面内容合并到 tools/tool_registry.py。

1. 在 import 区域加入：

from tools.robot_vacuum_diagnosis import diagnose_robot_vacuum_fault

2. 在 TOOL_REGISTRY 字典中加入：

"robot_vacuum_diagnosis": ToolSpec(
    "robot_vacuum_diagnosis",
    "对扫地机器人/扫拖一体机器人故障进行结构化诊断，给出自查步骤、修复建议和售后建议。",
    diagnose_robot_vacuum_fault,
    {
        "query": "用户故障描述",
        "product_id": "扫地机器人商品 ID，可选",
        "order_id": "订单号，可选",
        "user_has_checked": "用户已经检查过的内容，可选",
        "want_repair": "是否明确想申请维修，可选",
    },
),

如果不想手动合并，可把下面完整替换逻辑加入现有 tool_registry.py。
"""
