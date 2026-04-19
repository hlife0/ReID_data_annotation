# Documentation Status

本文档说明当前仓库里哪些文档应被当作**当前事实**阅读，哪些文档只是**历史记录**。

---

## 1. 当前事实文档

以下文档应优先视为当前主线的 source of truth：

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [ACTIVE_WORKFLOW.md](/home/hrli/data_annotation/docs/ACTIVE_WORKFLOW.md)
- [ACTIVE_SERVICES.md](/home/hrli/data_annotation/docs/ACTIVE_SERVICES.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
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
4. 当前 active 主线按 `Step 0` 到 `Step 5` 组织，但真正已经跑通的重点是 `Step 0 -> Step 3`
5. `Step 4` 当前是显式保留的主线缺口
6. `Step 5` 资源仍在 active 仓库中，但按主线口径属于后续阶段
7. 活跃仓库已不再支持旧的一次性标注
8. IMU 映射辅助已归档，不再属于 active 主线

---

## 4. 阅读建议

### 如果你要理解仓库全貌

1. [README.md](/home/hrli/data_annotation/docs/README.md)
2. [ACTIVE_WORKFLOW.md](/home/hrli/data_annotation/docs/ACTIVE_WORKFLOW.md)
3. [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)

### 如果你要理解 review 段模式

1. [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
2. [ACTIVE_WORKFLOW.md](/home/hrli/data_annotation/docs/ACTIVE_WORKFLOW.md)
3. [ACTIVE_SERVICES.md](/home/hrli/data_annotation/docs/ACTIVE_SERVICES.md)
4. [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)

### 如果你要理解 `human_stage_1`

1. [README.md](/home/hrli/data_annotation/docs/README.md)
2. [BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md)
3. [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)

### 如果你要找已下线的一次性标注资源

1. [archive/legacy_one_shot_annotation/](/home/hrli/data_annotation/docs/archive/legacy_one_shot_annotation)
2. [archive/README.md](/home/hrli/data_annotation/docs/archive/README.md)

### 如果你要找已下线的辅助支线

1. [archive/legacy_auxiliary/](/home/hrli/data_annotation/docs/archive/legacy_auxiliary)
2. [archive/README.md](/home/hrli/data_annotation/docs/archive/README.md)

### 如果你要找已归档的旧 requirements 文档

1. [archive/legacy_requirements/](/home/hrli/data_annotation/docs/archive/legacy_requirements)
2. [archive/README.md](/home/hrli/data_annotation/docs/archive/README.md)
