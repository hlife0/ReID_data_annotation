# 需求文档 H：最终 Annotation 融合导出（实现对齐版）

## 1. 目标

本阶段目标：综合原始多标注结果、Dice 分析结果与人工复审结果，生成每个视频一份最终定稿 annotation CSV。

交付目标：

1. 每个视频输出 1 份最终 CSV。
2. 每一行代表 1 帧。
3. 每一行同时包含 `P1` 与 `P2` 两个人的最终结果。
4. 每个 `(帧, 人)` 都必须给出最终信源说明。

---

## 2. 当前实现入口

主脚本：`./codex/process_final_annotation_batch.py`

---

## 3. 输入范围

主输入：

1. `./annotation/batch_<YYYYMMDD>_<vNN>/ui_tasks/ui_review.sqlite3`
2. `annotations` 表
3. `review_decisions` 表
4. `frames` 表

说明：

1. 逐 `(frame, person)` 处理。
2. `P1` 与 `P2` 独立融合。

---

## 4. 输出目录与文件规范

```text
./annotation/batch_<YYYYMMDD>_<vNN>/
├── final_annotations/
│   ├── <video_stem>.final.csv
│   └── final_annotation_summary.json
└── logs/
    ├── run.log
    └── errors.log
```

---

## 5. 核心融合算法（强制）

### 5.1 三条及以上标注的参考对选取

对每个 `(video_stem, frame_index, person_slot)`：

1. 若有 2 条标注，直接使用这 2 条作为参考来源。
2. 若有 3 条或更多标注，则两两计算该 `person_slot` 的 Dice。
3. 取 Dice **最大** 的那一对作为最终参考来源。
4. 若存在并列，按稳定规则打破并列：
   - `submitted_at` 升序
   - `annotation_id` 升序

### 5.2 两条参考标注的最终融合规则

对选出的两条参考标注，按以下优先级处理：

1. **复审优先**
   - 若 `review_decisions` 中存在该 `(frame, person)` 的结果，则直接输出复审结果。
   - 最终信源记为：`review`

2. **Dice=1 优先**
   - 若两条参考标注该 `person_slot` 的 Dice = `1`，则直接输出该一致结果。
   - 最终信源记为：`dice=1`

3. **human vs AI conflict**
   - 若一条来源为人工画框，另一条来源为 AI 推荐框，则直接取人工画框。
   - 人工来源包括：`manual_draw`、`manual_param`
   - AI 来源包括：`ai`
   - 最终信源记为：
     - `human_ai_conflict_{被采纳的标注者}-AI`

4. **human vs human conflict**
   - 若两条来源均为人工画框，则对两种标注取平均作为最终结果。
   - 平均方式：对 `bbox_x/y/w/h` 分别取算术平均。
   - 最终信源记为：
     - `human_human_conflict_{标注者1}-{标注者2}-{dice}`

5. **AI vs AI conflict**
   - 若两条来源均为 AI 推荐框，则对两种标注取平均作为最终结果。
   - 最终信源记为：
     - `AI_AI_conflict_{dice}`

6. **存在性冲突**
   - 若一条认为不存在，另一条认为存在，则直接取“认为存在”的那一条。
   - 最终信源记为：
     - `existance_conflict`

---

## 6. 最终信源枚举（强制）

最终 CSV 中每个 `(帧, 人)` 必须给出以下之一：

1. `review`
2. `dice=1`
3. `human_ai_conflict_{被采纳的标注者}-AI`
4. `human_human_conflict_{标注者1}-{标注者2}-{dice}`
5. `AI_AI_conflict_{dice}`
6. `existance_conflict`

---

## 7. 最终 CSV 字段规范（强制）

每个 `<video_stem>.final.csv` 必须包含：

1. `video_stem`
2. `frame_index`
3. `timestamp_ms`
4. `p1_bbox_x`
5. `p1_bbox_y`
6. `p1_bbox_w`
7. `p1_bbox_h`
8. `p1_is_absent`
9. `p1_final_source`
10. `p1_ref_annotation_ids`
11. `p1_ref_annotators`
12. `p1_ref_dice`
13. `p2_bbox_x`
14. `p2_bbox_y`
15. `p2_bbox_w`
16. `p2_bbox_h`
17. `p2_is_absent`
18. `p2_final_source`
19. `p2_ref_annotation_ids`
20. `p2_ref_annotators`
21. `p2_ref_dice`

---

## 8. 验收标准

1. 每个视频输出 1 份最终 CSV。
2. 每帧恰好 1 行。
3. 每帧同时包含 `P1/P2` 两个人的最终结果。
4. 三标注及以上时，确实选 Dice 最大的那一对作为参考来源。
5. 最终信源字段严格符合本文档约定。

---

## 9. 完成定义（DoD）

1. 最终 CSV 已生成。
2. 复审结果、Dice=1、一致性冲突、存在性冲突等规则都已融合。
3. 输出可直接作为最终 annotation 交付物使用。
