# 标注需求入口说明

本项目需求已拆分为四份“实现对齐版”文档：

1. 预标注批处理规范  
   `~/data_annotation/docs/REQUIREMENTS_PRELABEL.md`
2. UI 双人标注与复标分发规范  
   `~/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md`
3. 双 IMU 静止/运动比值分析与人物对应辅助规范  
   `~/data_annotation/docs/REQUIREMENTS_IMU_MAPPING.md`
4. 基于历史 AI Track ID 的自动推荐规范  
   `~/data_annotation/docs/REQUIREMENTS_TRACK_RECOMMENDATION.md`

推荐阅读顺序：

1. `README.md`（快速上手与脚本入口）
2. `REQUIREMENTS_PRELABEL.md`
3. `REQUIREMENTS_UI_REVIEW.md`
4. `REQUIREMENTS_IMU_MAPPING.md`
5. `REQUIREMENTS_TRACK_RECOMMENDATION.md`

流程顺序：

1. 先执行预标注阶段（A）
2. 再执行 UI 标注阶段（B）
3. 最后执行 IMU 映射分析阶段（C）
4. D 阶段作为 B 阶段增强功能，独立开关
