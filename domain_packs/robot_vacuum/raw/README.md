把你的原始知识文件放到这个目录，文件名建议如下：

- 故障排除.txt
- 扫地机器人100问.pdf
- 扫地机器人100问2.txt
- 扫拖一体机器人100问.txt
- 维修保养.txt
- 选购指南.txt

然后在项目根目录运行：

python scripts/import_robot_vacuum_knowledge.py

脚本会自动把这些原始文档转换成 data/knowledge/robot_vacuum/*.md，供 RAG 混合检索使用。
