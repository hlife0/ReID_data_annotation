# 标注需求入口说明

本项目需求已拆分为八份主文档 + 一份补充设计文档：

1. 预标注批处理规范  
   `~/data_annotation/docs/REQUIREMENTS_PRELABEL.md`
2. UI 双人标注与复标分发规范  
   `~/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md`
3. 双 IMU 静止/运动比值分析与人物对应辅助规范  
   `~/data_annotation/docs/REQUIREMENTS_IMU_MAPPING.md`
4. 基于历史 AI Track ID 的自动推荐规范  
   `~/data_annotation/docs/REQUIREMENTS_TRACK_RECOMMENDATION.md`
5. 标注结果分析与 Dice 折线图规范  
   `~/data_annotation/docs/REQUIREMENTS_ANNOTATION_ANALYSIS.md`
6. 标注结果复审 UI 规范  
   `~/data_annotation/docs/REQUIREMENTS_REVIEW_ANNOTATION_RESULTS.md`
7. 最终 Annotation 融合导出规范  
   `~/data_annotation/docs/REQUIREMENTS_FINAL_ANNOTATION.md`
8. 轨迹级问题驱动标注提效规范（规划与执行跟踪版）
   `~/data_annotation/docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`

推荐阅读顺序：

1. `README.md`（快速上手与脚本入口）
2. `REQUIREMENTS_PRELABEL.md`
3. `REQUIREMENTS_UI_REVIEW.md`
4. `REQUIREMENTS_IMU_MAPPING.md`
5. `REQUIREMENTS_TRACK_RECOMMENDATION.md`
6. `REQUIREMENTS_ANNOTATION_ANALYSIS.md`
7. `REQUIREMENTS_REVIEW_ANNOTATION_RESULTS.md`
8. `REQUIREMENTS_FINAL_ANNOTATION.md`
9. `REQUIREMENTS_TRAJECTORY_REVIEW.md`

流程顺序：

1. 先执行预标注阶段（A）
2. 再执行 UI 标注阶段（B）
3. 最后执行 IMU 映射分析阶段（C）
4. D 阶段作为 B 阶段增强功能，独立开关
5. F 阶段用于对 B 阶段产出的多标注结果做离线一致性分析
6. G 阶段用于对多标注结果做人工复审与最终裁决
7. H 阶段用于融合多标注结果并导出最终 annotation
8. X 文档用于指导 B/G 阶段从逐帧复核逐步升级到轨迹级、风险驱动复核流程
