# 需求文档入口说明

当前文档体系里，最重要的已经不是旧的单阶段说明，而是：

- 当前系统现在长什么样
- 当前段模式主线推进到了哪里
- 当前稳定段 / 非简单帧是怎么工作的

如果你只想最快建立全局理解，推荐阅读顺序如下。

---

## 推荐阅读顺序

1. [README.md](/home/hrli/data_annotation/docs/README.md)
   - 当前仓库入口、目录、推荐端口与主线阶段
2. [DOCUMENTATION_STATUS.md](/home/hrli/data_annotation/docs/DOCUMENTATION_STATUS.md)
   - 哪些文档是当前事实，哪些只是历史记录
3. [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
   - 当前 review 段模式需求与当前实现边界
4. [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
   - 稳定段、非简单帧与 first-pass 的数学基础
5. [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
   - 当前 review/admin 栈的实际运行形态
6. [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
   - 当前 review UI 的标注员使用说明
7. [BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md)
   - 当前 `human_stage_1` 优化方向与配置结论

---

## 其余文档按主题分组

### 当前主线

- [DOCUMENTATION_STATUS.md](/home/hrli/data_annotation/docs/DOCUMENTATION_STATUS.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
- [BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md)
- [codes/README.md](/home/hrli/data_annotation/codes/README.md)
- [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)

### A 阶段 / 预标注

- [REQUIREMENTS_PRELABEL.md](/home/hrli/data_annotation/docs/REQUIREMENTS_PRELABEL.md)

### C 阶段 / IMU 映射辅助

- [REQUIREMENTS_IMU_MAPPING.md](/home/hrli/data_annotation/docs/REQUIREMENTS_IMU_MAPPING.md)

### 其他增强与下游

- 旧下游分析、旧复审结果 UI 和旧最终导出需求，现已归档到：
  - [archive/legacy_downstream/](/home/hrli/data_annotation/docs/archive/legacy_downstream)
- 旧批次 IMU 分析报告，现已归档到：
  - [archive/historical_reports/](/home/hrli/data_annotation/docs/archive/historical_reports)

---

## 当前最需要记住的事实

1. 当前统一代码目录是 `./codes/`
2. 当前活跃代码继续分成：
   - `codes/application/`
   - `codes/process/`
   - `codes/test/`
3. 当前离线处理顺序见：
   - [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)
4. 当前活跃优化重点已经转到 `human_stage_1`
5. 当前 review 默认工作单位是“标注段”，不是单帧
6. 当前 review 在线工作单元已经不只包含：
   - `stable_segment`
   - `non_simple_single_frame`
   - 也包含 `repair_window`
7. 旧 `P1/P2` 双人下游文档不再是当前主线 source of truth

如果你发现某份旧文档还在强烈强调：

- 固定双人 `P1/P2`
- 纯逐帧工作流
- `codes/` 以外的旧代码目录名称
- 旧 batch 路径

请优先以：

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [DOCUMENTATION_STATUS.md](/home/hrli/data_annotation/docs/DOCUMENTATION_STATUS.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)

为准。
