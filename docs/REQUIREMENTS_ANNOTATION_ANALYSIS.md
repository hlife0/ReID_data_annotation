# 需求文档 F：标注结果分析与 Dice 折线图（实现对齐版）

## 1. 目标

本阶段目标：基于 UI 标注结果，对每个视频逐帧分析多标注之间的一致性，并输出可视化折线图，帮助快速发现“哪一帧、哪一个人”的标注分歧更大。

交付目标：

1. 对每个视频、每一帧、每个人物槽位分别计算一个 Dice 分析值。
2. 当某帧有 2 个标注时，直接计算这 2 个标注的 Dice 分析值。
3. 当某帧有 3 个标注时，对 3 个标注两两计算 Dice 分析值，并取最小值作为该帧最终值。
4. 对每个视频输出 2 张折线图：`P1` 一张、`P2` 一张。
5. 额外对全部视频、全部 `P1/P2` Dice 值汇总输出 1 张频数分布直方图。
6. 额外输出 1 张“返工阈值曲线图”：横轴为阈值 `0~1`，纵轴为需要返工的图片数量。
7. 逐视频折线图横轴为 `frame_index`，纵轴为该帧该人物的 Dice 分析值。
8. 输出结果可直接用于人工排查“低一致性帧”与“存在/不存在判断冲突帧”。

---

## 2. 当前实现入口

主脚本：`./codex/process_annotation_analysis.py`

说明：

1. 分析以批次目录中的 SQLite 为主数据源。
2. 输出写入对应批次目录下的 `annotation_analysis/`。

---

## 3. 输入范围与路径约束

主输入：

1. `./annotation/batch_<YYYYMMDD>_<vNN>/ui_tasks/ui_review.sqlite3`
2. `frames` 表（用于获取 `video_stem`、`frame_index`、`timestamp_ms`）
3. `annotations` 表（用于获取每条标注的 `P1/P2` 框、`source`、`submitted_at` 等信息）

路径规则：

1. 使用当前工作目录下相对路径（`./...`）。
2. 业务批次数据统一从 `./annotation/...` 读取。
3. 不把运行机上的其它绝对路径写入业务协议。

---

## 4. 输出目录与产物

写入当前批次目录：

```text
./annotation/batch_<YYYYMMDD>_<vNN>/
├── annotation_analysis/
│   ├── <video_stem>.dice_timeseries.csv
│   ├── <video_stem>.p1.dice.png
│   ├── <video_stem>.p2.dice.png
│   ├── <video_stem>.dice_summary.json
│   ├── all_videos.dice_hist.png
│   └── all_videos.rework_threshold.png
└── logs/
    ├── run.log
    └── errors.log
```

说明：

1. `dice_timeseries.csv` 是逐帧核心结果。
2. `p1/p2.dice.png` 是逐视频逐人物的折线图。
3. `dice_summary.json` 用于记录参数、统计、异常与极值帧信息。
4. `all_videos.dice_hist.png` 用于查看所有视频综合后的 Dice 频数分布。
5. `all_videos.rework_threshold.png` 用于查看不同阈值下，需要返工的图片数量变化。

---

## 5. 取数与分组规则

### 5.1 基本分组

对 `annotations` 表按以下键分组：

- `video_stem`
- `frame_index`

在每个分组内，对 `P1` 和 `P2` **独立分析**。

### 5.2 标注条目排序

同一帧内的标注记录，建议按以下顺序稳定排序：

1. `submitted_at` 升序
2. `annotation_id` 升序

### 5.3 有效标注数规则

1. 当某帧标注数 `< 2` 时，不计算该帧 Dice 分析值。
2. 当某帧标注数为 `2` 时，只计算这一对。
3. 当某帧标注数为 `3` 时，计算 3 个 pair：`(1,2)`、`(1,3)`、`(2,3)`。
4. 若未来某帧标注数 `> 3`，允许对全部两两组合计算，并继续沿用“取最小值”规则。

---

## 6. Dice 分析值定义（强制）

### 6.1 分析对象

对每个 slot 分别处理：

- `P1` 使用：`p1_bbox_x/y/w/h`、`p1_source`
- `P2` 使用：`p2_bbox_x/y/w/h`、`p2_source`

### 6.2 两条标注之间的 pairwise 计算

设同一帧、同一人物槽位的两条标注为 `a`、`b`。

#### 情况 1：两条标注都为 `absent`

项目约定：

- `dice_value(a, b) = 1.0`

#### 情况 2：一条为 `absent`，另一条不是 `absent`

项目约定：

- `dice_value(a, b) = 0.0`

说明：

1. 这里采用“标准相似度语义”：双方都认定不存在，视为完全一致；一方认定存在、一方认定不存在，视为完全不一致。
2. 因此整个分析值范围保持在 `[0, 1]`，更符合 Dice 作为相似度指标的直觉。

#### 情况 3：两条标注都不是 `absent`

对两个框使用 COCO `xywh` 解释，并计算标准框间 Dice：

- `inter = intersection_area(box_a, box_b)`
- `area_a = w_a * h_a`
- `area_b = w_b * h_b`
- `dice_value(a, b) = 2 * inter / (area_a + area_b)`

要求：

1. `bbox_w > 0` 且 `bbox_h > 0`。
2. 若框非法，则记为失败并写错误日志，不允许静默吞掉。

### 6.3 三条及以上标注的聚合规则

若同一帧该人物槽位有 `n >= 3` 条标注：

1. 先对全部 pair 两两计算 `dice_value`。
2. 取这些 pairwise 结果中的**最小值**作为该帧该人物最终值。

记号：

- `frame_dice = min(pairwise_dice_values)`

说明：

1. 本规则严格按业务要求执行。
2. 由于 `absent` 情况已按“完全一致=1、完全冲突=0”映射，整个最终值可以继续按相似度理解：越接近 `1` 越一致，越接近 `0` 分歧越大。

---

## 7. CSV 字段规范（强制）

文件：`<video_stem>.dice_timeseries.csv`

必须包含字段：

1. `video_stem`
2. `frame_index`
3. `timestamp_ms`
4. `annotation_count`
5. `p1_dice`
6. `p2_dice`
7. `p1_pair_count`
8. `p2_pair_count`

规则：

1. 每帧最多输出 1 行。
2. `p1_dice` 与 `p2_dice` 分别表示该帧 `P1/P2` 的最终分析值。
3. `p1_pair_count` / `p2_pair_count` 表示参与该最终值计算的 pair 数。
4. 若某帧因标注数不足而未计算，则该帧可以不写出到 CSV。

---

## 8. 折线图规范（强制）

对每个 `video_stem` 输出两张图：

1. `<video_stem>.p1.dice.png`
2. `<video_stem>.p2.dice.png`

画图要求：

1. 横轴：`frame_index`
2. 纵轴：Dice 分析值
3. `P1` 和 `P2` 不混画，每人单独一张图
4. 建议纵轴范围固定为 `0 ~ 1.05`
5. 图标题中必须包含：`video_stem`、人物槽位（`P1` 或 `P2`）
6. 图中建议增加参考线：
   - `y = 1.0`（完全一致）
   - `y = 0.0`（完全冲突 / absent 冲突）

---

## 9. Summary JSON 规范（强制）

文件：`<video_stem>.dice_summary.json`

必须包含：

1. `video_stem`
2. `generated_at`
3. `input_db`
4. `dice_rules`：
   - `both_absent_value = 1.0`
   - `absent_mismatch_value = 0.0`
   - `three_or_more_rule = min(pairwise_values)`
5. `stats`：
   - `frame_total`
   - `frame_output`
   - `frame_skipped_lt2_annotations`
   - `p1_min_dice`
   - `p1_max_dice`
   - `p2_min_dice`
   - `p2_max_dice`
6. `top_frames`：
   - `p1_top_frames`
   - `p2_top_frames`

建议：

1. `top_frames` 至少保留前 20 个**低值帧**，便于人工优先回看分歧最大的时刻。
2. 若同值，按 `frame_index` 升序。

---

## 10. 执行步骤（强制顺序）

### Step F0：输入巡检

1. 检查 SQLite 文件是否存在且可读。
2. 检查 `frames` 与 `annotations` 表是否存在。
3. 检查 `annotations` 中是否至少存在 2 条以上同帧记录。

### Step F1：按帧聚合标注

1. 按 `video_stem + frame_index` 聚合。
2. 合并 `timestamp_ms`。
3. 统计每帧标注条数。

### Step F2：逐帧计算 `P1/P2` Dice 分析值

1. 对 `P1` 独立计算。
2. 对 `P2` 独立计算。
3. 若有 3 条标注，则两两计算并取最小值。

### Step F3：导出逐帧 CSV

1. 写出 `dice_timeseries.csv`。
2. 记录每帧最终值与参与 pair 数。

### Step F4：画图

1. 对每个视频画 `P1` 折线图。
2. 对每个视频画 `P2` 折线图。
3. 汇总全部视频与全部 `P1/P2` Dice 值，画 1 张频数分布直方图。
4. 基于全部图片的逐帧 Dice 结果，画 1 张返工阈值曲线图。
5. 输出为 PNG。

### Step F5：导出 summary

1. 写出参数与统计信息。
2. 列出高风险帧（高值帧）。

---

## 11. 验收标准

全部满足才算通过：

1. 每个视频都生成 1 个 `dice_timeseries.csv`。
2. 每个视频都生成 2 张折线图（`P1` 一张、`P2` 一张）。
3. 能额外生成 1 张全部视频综合 Dice 频数分布直方图。
4. 能额外生成 1 张返工阈值曲线图。
5. 双标注帧 Dice 计算正确。
4. 三标注帧采用“两两计算后取最小值”。
5. `absent` 规则严格满足：
   - 双 absent -> `0.0`
   - 单边 absent -> `2.0`
6. 有 `run.log`、`errors.log`、`dice_summary.json`。

---

## 12. 失败处理规则

1. 缺少 SQLite、表结构不完整或字段缺失：直接失败并写日志。
2. 某帧标注数不足 2：允许跳过，但必须计数。
3. 某条非 absent 标注框非法：该帧记失败并写日志，不允许静默纠正。
4. 某视频画图失败：该视频记失败，不能假装成功。

---

## 13. 完成定义（DoD）

当且仅当以下条件全部满足：

1. 能从批次 SQLite 中稳定读取全部多标注帧。
2. 每个视频都得到逐帧 `P1/P2` Dice 分析结果。
3. 每个视频都输出 2 张折线图。
4. `absent` 与 3 标注规则严格符合本文档约定。
5. 输出可直接用于人工定位“低一致性/异常冲突”帧。

## 14. 综合返工阈值曲线定义（补充）

文件：`all_videos.rework_threshold.png`

规则：

1. 把所有视频的逐帧结果汇总。
2. 对每一帧取 `min(p1_dice, p2_dice)` 作为该图片的综合 Dice。
3. 对每个阈值 `t`（`0 <= t <= 1`），统计满足 `min(p1_dice, p2_dice) < t` 的图片数量。
4. 横轴为阈值 `t`，纵轴为返工图片数量。

说明：

1. 本图按当前 Dice 语义实现：`dice < threshold` 视为该图片需要返工。
2. 因为采用的是 `min(p1_dice, p2_dice)`，所以只要一张图片中任一人物槽位低于阈值，该图片就会被计入返工数量。
3. 曲线按实际观测到的 Dice 值做精确分段，而不是固定 `0.01` 采样，因此不会丢失真实拐点。
