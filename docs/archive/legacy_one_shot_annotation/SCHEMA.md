# Legacy One-Shot Annotation Schema Notes

本文档记录已归档的一次性标注相关数据库结构，供后续从 archive 恢复旧路径时参考。

---

## 1. 旧 frame-mode / mixed review storage

历史上一阶段直接标注与后续 review 混用过：

- `annotation/batch_<...>/ui_tasks/ui_review.sqlite3`

在旧实现中，相关表包括：

### `frames`

- `video_stem`
- `frame_index`
- `timestamp_ms`

用途：

- 表示可领取的逐帧样本池

### `frame_counts`

- `video_stem`
- `frame_index`
- `timestamp_ms`
- `annotation_count`

用途：

- 记录某帧已被标注多少次
- 旧 frame-mode 派单依赖它分桶

### `assignments`

- `assignment_id`
- `assigned_at`
- `annotator_id`
- `video_stem`
- `frame_index`
- `timestamp_ms`
- `count_before`
- `reason`

用途：

- 记录旧 frame-mode 的派单历史

### `annotations`

- `annotation_id`
- `video_stem`
- `frame_index`
- `timestamp_ms`
- `annotator_id`
- `submitted_at`
- `slots_json`

用途：

- 存储旧一次性标注提交结果
- 后续旧分析与旧复审结果栈也依赖它

### `track_person_stats`

- `video_stem`
- `track_id`
- `slot`
- `vote_count`

用途：

- 历史推荐统计

### `segment_reviews`

- `segment_id`
- `annotator_id`
- `review_type`
- `reviewed_at`

用途：

- 后期 segment-mode review 记录
- 与旧 frame-mode 同库共存过

---

## 2. 旧 review-result storage

历史上的复审结果栈使用：

- `annotation/batch_<...>/review_results/ui_review_result.sqlite3`

核心表：

### `review_decisions`

- `decision_id`
- `video_stem`
- `frame_index`
- `timestamp_ms`
- `reviewer_id`
- `reviewed_at`
- `decision_type`
- `accepted_side`
- `left_annotation_id`
- `right_annotation_id`
- `candidate_dice`
- `p1_bbox_x/y/w/h`
- `p1_source`
- `p2_bbox_x/y/w/h`
- `p2_source`

用途：

- 保存旧的左右候选裁决结果
- 被旧最终导出脚本读取

---

## 3. 相关归档代码

对应归档代码位于：

- `codes/archive/legacy_one_shot_annotation/application/`
- `codes/archive/legacy_one_shot_annotation/process/`
- `codes/archive/legacy_one_shot_annotation/test/`

如果需要恢复旧路径，建议顺序：

1. 先读本 schema 文档
2. 再读 [README.md](/home/hrli/data_annotation/docs/archive/legacy_one_shot_annotation/README.md)
3. 再按归档代码与旧需求文档逐步恢复
