# Documentation Status

本文档说明当前仓库里哪些文档应被当作**当前事实**阅读，哪些文档只是**历史记录**。

---

## 1. 当前事实文档

以下文档应优先视为当前主线的 source of truth：

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [REQUIREMENTS.md](/home/hrli/data_annotation/docs/REQUIREMENTS.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
- [REQUIREMENTS_PRELABEL.md](/home/hrli/data_annotation/docs/REQUIREMENTS_PRELABEL.md)
- [REQUIREMENTS_IMU_MAPPING.md](/home/hrli/data_annotation/docs/REQUIREMENTS_IMU_MAPPING.md)
- [BATCH_20260417_V01_SEGMENT_SUMMARY.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_SEGMENT_SUMMARY.md)
- [BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md)
- [codes/README.md](/home/hrli/data_annotation/codes/README.md)
- [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)

---

## 2. 历史文档

以下目录默认不应被当作当前实现事实：

- [archive/](/home/hrli/data_annotation/docs/archive)
- [superpowers/specs/](/home/hrli/data_annotation/docs/superpowers/specs)
- [superpowers/plans/](/home/hrli/data_annotation/docs/superpowers/plans)

其中：

- `archive/` 保存已归档的旧主线、旧下游或历史分析材料
- `superpowers/specs/` 与 `superpowers/plans/` 保存实现时的设计与执行记录

这些文档仍然有追溯价值，但不应优先覆盖当前实现文档。

---

## 3. 当前主线的最短口径

如果只记住最短版本，请记住：

1. 当前活跃代码在 `codes/`
2. 当前第一轮人工主线是 `human_stage_1`
3. `human_stage_1` 的核心目标是把 AI 逐帧框压缩成更少的人工工作单元
4. review 栈仍然保留并支持段模式，但当前优化重心不再是旧的逐帧/双人主线
5. 当前实际实现里，review 工作单元已不只包含 `stable_segment` 和 `non_simple_single_frame`，也包含 `repair_window`

---

## 4. 阅读建议

### 如果你要理解仓库全貌

1. [README.md](/home/hrli/data_annotation/docs/README.md)
2. [REQUIREMENTS.md](/home/hrli/data_annotation/docs/REQUIREMENTS.md)
3. [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)

### 如果你要理解 review 段模式

1. [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
2. [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
3. [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
4. [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)

### 如果你要理解 `human_stage_1`

1. [README.md](/home/hrli/data_annotation/docs/README.md)
2. [BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md)
3. [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)
