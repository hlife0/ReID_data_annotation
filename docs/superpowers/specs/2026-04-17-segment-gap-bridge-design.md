# Segment Gap Bridge Design

## Goal

在不破坏现有批次数据和在线 review 主流程的前提下，为 `segment_prep` 增加一个保守的时序容错层，把明显属于检测抖动的短暂低分坏点重新吸收回稳定段，并在一个新的派生 batch 上执行这套流程。

## Context

当前 `process_segment_review_prep.py` 的 simple/non-simple 判定是逐帧、局部的：

- 任意框 `score < low_score_threshold`，该帧即为 non-simple
- 任意两框 `IoU > high_overlap_iou`，该帧即为 non-simple

在 `low_score_threshold = 0.4` 下，当前正式批次 `annotation/batch_20260413_v01` 仍有大量 `non_simple_single_frame`，其中一部分是长度 1-2 帧的短暂低分抖动。对这类坏点逐帧人工处理，人工成本高，且它们并不一定对应真实的语义复杂性。

## Alternatives

### Option A: 继续降低全局 low-score 阈值

优点：

- 最简单
- 不需要增加新算法状态

缺点：

- 风险是全局放松标准
- 会把一些真的不稳的帧直接并入稳定段
- 一旦进入稳定段，错误可能被整段传播

### Option B: 保守型 low-score gap bridge

优点：

- 只吃掉很短、很像检测抖动的坏点
- 改动集中在离线 prep
- 不改在线 API / UI / SQLite schema

缺点：

- 收益不如激进改规范大
- 需要多一层 frame 状态扫描

### Option C: 把 non-simple 单帧改成短复杂段

优点：

- 人工量可能大幅下降

缺点：

- 已经改变当前主线规范
- 会牵涉 UI、提交协议、展开逻辑和文档心智模型

## Recommendation

选择 Option B。

原因：

- 它直接减少人工任务数，而不仅仅减少单任务耗时
- 它是当前所有降本方案里最局部、风险最低的一刀
- 它不需要改变当前段模式主语义

## Design

### 1. Raw 判定保持不变

先按当前规则对每一帧做原始判定：

- `raw_simple`
- `raw_bad`

并额外记录坏帧原因：

- `low_only`
- `overlap_only`
- `both`

### 2. 增加保守桥接层

在原始判定之后，对每个 session 再做一次顺序扫描，识别长度不超过 `max_gap_frames` 的连续坏段。

只有同时满足以下条件的坏段，才被桥接为 effective simple：

1. 坏段长度 `<= max_gap_frames`
2. 坏段左右两侧都存在帧
3. 左右两侧都为 `raw_simple`
4. 左右两侧 `track_ids` 完全相同
5. 坏段内每一帧的 `track_ids` 与左右两侧一致
6. 坏段原因只允许：
   - `low_only`
   - 或在明确开启时再放宽到 `low_or_both`

第一版只实现最保守模式：

- 仅桥接 `low_only`
- 默认 `max_gap_frames = 2`

### 3. 用 effective simple 参与切段

稳定段切分不再直接依赖原始逐帧判定，而是依赖桥接后的 `effective_simple`。

切分规则保持原样：

- `effective_simple` 且 `track_ids` 恒定时并入同一个 stable segment
- 其余帧继续落成 `non_simple_single_frame`

### 4. CLI 可配置，但默认不改变旧行为

为了不破坏已有用法，新增 CLI 参数但默认关闭桥接：

- `--bridge-low-score-gaps`
- `--max-gap-frames`

旧命令不加这些参数时，行为与当前版本一致。

### 5. 新 batch 执行，不覆盖旧数据

执行时创建一个新的派生 batch：

- 建议：`annotation/batch_20260417_v01`

其内容来自当前正式 batch：

- 复制或硬链接 `manifests/annotation_tasks.csv`
- 复制或硬链接 `pseudo_labels/*.auto.csv`

然后仅在新 batch 上：

- 运行新的 `process_segment_review_prep.py`
- 初始化新的 review 存储

不修改旧 batch `annotation/batch_20260413_v01` 下的任何 review 数据和 `segment_prep/`。

## Files

### Code

- Modify: `codes/process/process_segment_review_prep.py`
- Modify: `codes/test/test_process_segment_review_prep.py`

### Docs

- Create: `docs/superpowers/specs/2026-04-17-segment-gap-bridge-design.md`
- Create: `docs/superpowers/plans/2026-04-17-segment-gap-bridge.md`
- Create: batch-level markdown summary for the new batch after execution

## Testing Strategy

重点覆盖：

1. 单个 `low_only` 坏帧，两侧 simple 且 track set 相同，应被桥接
2. 连续 2 帧 `low_only`，应被桥接
3. `overlap_only` 坏帧，不应桥接
4. 坏段前后 track set 不同，不应桥接
5. session 起止边界上的坏帧，不应桥接
6. 未开启桥接参数时，行为保持旧逻辑

## Execution Notes

实现完成后，需要在新 batch 上输出：

- 新的 `segment_prep_summary.json`
- 新 batch 的 session 级 markdown 汇总表

并确认：

- 新 batch 的 `annotations = 0`
- `assignments = 0`
- `segment_reviews = 0`

从而保证它是一个干净的新起点。
