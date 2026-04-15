# 需求文档入口说明

当前文档体系里，最重要的已经不是旧的单阶段说明，而是：

- 当前系统现在长什么样
- 当前段模式主线推进到了哪里
- 当前稳定段 / 非简单帧是怎么工作的

如果你只想最快建立全局理解，推荐阅读顺序如下。

---

## 推荐阅读顺序

1. [README.md](/home/hrli/data_annotation/docs/README.md)
   - 当前仓库入口、目录、命令和正式 batch
2. [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
   - 当前段模式主需求文档
3. [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
   - 稳定段与非简单帧的数学定义
4. [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
   - 当前 review/admin 栈的实际运行形态
5. [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
   - 给标注员的界面使用说明

---

## 其余文档按主题分组

### 当前主线

- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)

### A 阶段 / 预标注

- [REQUIREMENTS_PRELABEL.md](/home/hrli/data_annotation/docs/REQUIREMENTS_PRELABEL.md)

### C 阶段 / IMU 映射辅助

- [REQUIREMENTS_IMU_MAPPING.md](/home/hrli/data_annotation/docs/REQUIREMENTS_IMU_MAPPING.md)
- [C_STAGE_IMU_MAPPING_ANALYSIS.md](/home/hrli/data_annotation/docs/C_STAGE_IMU_MAPPING_ANALYSIS.md)

### 其他增强与下游

- [REQUIREMENTS_TRACK_RECOMMENDATION.md](/home/hrli/data_annotation/docs/REQUIREMENTS_TRACK_RECOMMENDATION.md)
- [REQUIREMENTS_ANNOTATION_ANALYSIS.md](/home/hrli/data_annotation/docs/REQUIREMENTS_ANNOTATION_ANALYSIS.md)
- [REQUIREMENTS_REVIEW_ANNOTATION_RESULTS.md](/home/hrli/data_annotation/docs/REQUIREMENTS_REVIEW_ANNOTATION_RESULTS.md)
- [REQUIREMENTS_FINAL_ANNOTATION.md](/home/hrli/data_annotation/docs/REQUIREMENTS_FINAL_ANNOTATION.md)

---

## 当前最需要记住的事实

1. 当前统一代码目录是 `./codes/`
2. 当前正式 batch 是 `./annotation/batch_20260413_v01`
3. 当前默认 review 工作单位是“标注段”，不是单帧
4. 当前 review 重点是：
   - 稳定段
   - 单帧非简单帧
   - 代表帧标注
   - 段级身份映射
   - 逐帧 `p1-p7` 结果生成

如果你发现某份旧文档还在强烈强调：

- 固定双人 `P1/P2`
- 纯逐帧工作流
- `codes/` 以外的旧代码目录名称
- 旧 batch 路径

请优先以：

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)

为准。
