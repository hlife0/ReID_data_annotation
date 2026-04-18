# Batch `20260417_v01` Human Stage 1 Segmentation Optimization Report

最后更新：2026-04-19

---

## 1. 这份报告要回答什么问题

当前项目已经不再把第一轮人工工作理解为“逐帧手工看框”，而是先用 AI 预标注生成逐帧候选框，再在离线阶段把这些帧压缩成更少的人工工作单元，最后让 `human_stage_1` 标注员只看每个工作单元的一张代表帧。

因此，当前阶段最核心的优化问题不是：

- AI 能不能直接给出最终结果

而是：

- 能否把 AI 已经给出的逐帧框进一步合并成更少的人工工作单元
- 在减少人工工作量的同时，尽量不把本来不该合并的片段压得过头

这份报告聚焦于 `human_stage_1` 分支，回答以下问题：

1. `human_stage_1` 的离线分段算法大致是怎么工作的
2. 不同 first-pass / second-pass 配置下，人工工作单元数会降到多少
3. 哪些参数最值得调，哪些参数收益已经明显递减
4. 当前更推荐使用哪组“平衡配置”

本次实验基于：

- batch: `./annotation/batch_20260417_v01`
- 视频数：`20`
- 原始总帧数：`109,634`

实验原始结果见：

- `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/summary.md`
- `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/results.json`

---

## 2. 当前核心思路：先让 AI 逐帧打框，再把帧合并成更少的人类工作单元

`human_stage_1` 的目标不是在第一轮就得到最终精确 bbox，而是用尽量低的人工成本先做一轮粗标：

- 某个固定身份槽位是否能直接对应当前帧里的某个 AI 框
- 如果不能，是因为该人不存在，还是因为当前帧需要后续人工精修

这条思路的关键在于：

- AI 仍然逐帧产出 `pseudo_labels/*.auto.csv`
- 但人不再逐帧看
- 系统先在离线阶段把许多相邻帧合并成 segment
- 每个 segment 只暴露 1 张代表帧给标注员

所以，对 `human_stage_1` 来说，真正决定人工成本的不是“总帧数”，而是：

```text
最终剩余的人工工作单元数 = 最终 segment 数
```

本报告中所有“仍需人工标注多少帧”的表述，都应理解为：

- 仍需人工查看多少个 `human_stage_1` 工作单元
- 每个工作单元对应 1 张代表帧

---

## 3. 指标口径

### 3.1 人工工作单元数

对 `human_stage_1` 分支：

- first-pass 后的工作单元数 = `stable_segment + non_simple_single_frame` 的总数
- second-pass 后的工作单元数 = second-pass 合并后的最终 `segments` 总数

### 3.2 剩余人工占比

本报告统一使用：

```text
remaining_work_unit_ratio = work_unit_count / total_original_frames
```

这不是“真正还剩多少物理帧要逐帧看”，而是：

- 用“人工工作单元数 / 原始总帧数”来衡量压缩效果

这个指标越低，说明人工第一轮成本越低。

---

## 4. `human_stage_1` 的详细算法

`human_stage_1` 的离线分段是一个两阶段流程：

1. first-pass segmentation
2. second-pass `repair_window` merge

它的目标很明确：

- first-pass 先给出一个严格、稳定、可解释的小段分解
- second-pass 再在这份分解之上，把一些明显碎片化的局部区域重新打包成更少的工作单元

### 4.1 输入

输入来自 AI 预标注产物：

- `pseudo_labels/<video_stem>.auto.csv`

每条记录至少包含：

- `frame_index`
- `track_id`
- `bbox`
- `score`

---

### 4.2 First-Pass：先做严格切分

first-pass 的作用是先回答：

- 哪些帧足够“简单”，适合被并入一个稳定段
- 哪些帧“不简单”，需要单独保留

#### Step 1：逐帧判断是否为 simple frame

对每一帧，检查两类风险：

1. 是否存在低置信度框
2. 是否存在高重叠框

当且仅当下面两个条件同时满足时，该帧被视为 `simple`：

1. 该帧内所有可见轨迹的 `score >= low_score_threshold`
2. 该帧内任意两条轨迹的 IoU 都不超过 `high_overlap_iou`

否则该帧被视为 non-simple。

本次 sweep 中固定：

- `high_overlap_iou = 0.25`

first-pass 主要扫的参数是：

- `low_score_threshold`
- 是否开启 `bridge_low_score_gaps`

#### Step 2：可选桥接 short low-score gaps

当 `bridge_low_score_gaps = true` 时，算法会做一个很保守的桥接：

- 中间坏段长度不超过 `max_gap_frames`
- 坏段两侧都是 simple
- 坏段前后 `track_ids` 完全相同
- 坏段内部 `track_ids` 也与两侧相同
- 坏段原因只能是 `low_only`

换句话说，这一步只尝试修复“人没变、轨迹集合没变、只是某几帧 score 抖了一下”的短裂缝。

在本次 sweep 中固定：

- `max_gap_frames = 2`

#### Step 3：构造 first-pass segments

完成 simple / non-simple 判断后，first-pass 线性扫描整段视频：

- 连续 simple 帧，如果 `track_ids` 集合保持不变，就合并成一个 `stable_segment`
- 一旦当前帧 non-simple，就把它单独记成一个 `non_simple_single_frame`

因此，first-pass 的结果只会包含两类工作单元：

1. `stable_segment`
2. `non_simple_single_frame`

这一步的设计思想是：

- 先严格、可解释地切出一套“基础小段”
- 不在 first-pass 阶段做太激进的合并

---

### 4.3 Second-Pass：把局部碎片再打包成 `repair_window`

`human_stage_1` 的 second-pass 并不是重新从原始帧开始切，而是只在 first-pass 结果上做局部合并。

它服务的目标很具体：

- 第一轮粗标并不需要精确逐帧 bbox
- 因此，一小串局部碎片如果整体上仍然像同一个短窗口任务，就可以打包成一个 `repair_window`

#### Step 1：定义 fragment

在 `human_stage_1` 里，一个 first-pass segment 只要满足下列任一条件，就会被视为 fragment：

1. `non_simple_single_frame`
2. 长度不超过 `micro_stable_max_frames` 的 `stable_segment`

本次 sweep 的 second-pass 主要扫两个参数：

- `micro_stable_max_frames`
- `max_repair_window_frames`

#### Step 2：从 non-simple frame 开始向右扩 run

算法从一个 `non_simple_single_frame` 出发，向右扩张：

- 只允许吃进 fragment
- 整个 run 的总帧跨度不能超过 `max_repair_window_frames`

#### Step 3：决定是否合并成 `repair_window`

若一个 run 中至少包含 `2` 个 `non_simple_single_frame`，则将这个 run 合并为一个 `repair_window`。

本次实验中固定：

- `min_non_simple_segments = 2`

这一条规则很重要，因为它防止算法把“只有一个真正复杂点、其余只是很短稳定段”的区域过度打包。

#### Step 4：`repair_window` 如何降低人工成本

一旦若干 first-pass 小段被合成一个 `repair_window`：

- 原本可能需要人工看多个 segment
- 现在只需要看一个新的 stage-1 工作单元

因此，second-pass 的本质是：

- 进一步减少 `human_stage_1` 的人工工作单元数
- 但它比 first-pass 更有“成本优先”的味道，因此也更需要小心避免过合并

---

## 5. 本次 sweep 的配置矩阵

### 5.1 First-Pass 配置

| Key | `low_score_threshold` | `bridge_low_score_gaps` |
|---|---:|---:|
| `FP1` | `0.40` | `false` |
| `FP2` | `0.40` | `true` |
| `FP3` | `0.50` | `false` |
| `FP4` | `0.50` | `true` |
| `FP5` | `0.60` | `false` |
| `FP6` | `0.60` | `true` |

固定参数：

- `high_overlap_iou = 0.25`
- `max_gap_frames = 2`

### 5.2 Second-Pass 配置

| Key | `micro_stable_max_frames` | `max_repair_window_frames` |
|---|---:|---:|
| `SP1` | `1` | `6` |
| `SP2` | `2` | `8` |
| `SP3` | `3` | `10` |
| `SP4` | `4` | `12` |

固定参数：

- `min_non_simple_segments = 2`

---

## 6. First-Pass 的效果

下表表示：仅完成 first-pass 后，还剩多少个 `human_stage_1` 人工工作单元。

| First-Pass | 参数 | 工作单元数 | 占原始总帧数 |
|---|---|---:|---:|
| `FP1` | `low_score=0.40`, `bridge=false` | `22,813` | `20.8083%` |
| `FP2` | `low_score=0.40`, `bridge=true` | `21,031` | `19.1829%` |
| `FP3` | `low_score=0.50`, `bridge=false` | `28,146` | `25.6727%` |
| `FP4` | `low_score=0.50`, `bridge=true` | `25,017` | `22.8187%` |
| `FP5` | `low_score=0.60`, `bridge=false` | `34,583` | `31.5440%` |
| `FP6` | `low_score=0.60`, `bridge=true` | `30,698` | `28.0004%` |

### 6.1 First-Pass 观察

#### 观察 1：`bridge=true` 始终有明显收益

同一 `low_score_threshold` 下，开启保守 bridge 都会减少工作单元数：

- `FP1 -> FP2`：`22,813 -> 21,031`，减少 `1,782`
- `FP3 -> FP4`：`28,146 -> 25,017`，减少 `3,129`
- `FP5 -> FP6`：`34,583 -> 30,698`，减少 `3,885`

说明：

- 仅仅把短 low-score 抖动桥接起来，就已经能减少不少碎片化
- 且这一优化相对保守，风险通常比进一步放宽阈值更低

#### 观察 2：`low_score_threshold` 对 first-pass 影响很大

不论 bridge 开不开，`low_score_threshold` 越高，first-pass 切出来的工作单元越多。

例如在 `bridge=false` 下：

- `0.40` 时是 `22,813`
- `0.50` 时是 `28,146`
- `0.60` 时是 `34,583`

这说明：

- `low_score_threshold` 是决定 first-pass 粒度的核心旋钮
- 阈值越严格，越多帧会被视为 non-simple，从而增加人工成本

---

## 7. First-Pass + Second-Pass 的最终效果

下表表示：first-pass 再加 second-pass 之后，`human_stage_1` 最终仍需人工处理的工作单元数。

表中格式为：

```text
工作单元数 / 占原始总帧数
```

| Second-Pass \ First-Pass | `FP1` | `FP2` | `FP3` | `FP4` | `FP5` | `FP6` |
|---|---:|---:|---:|---:|---:|---:|
| `SP1` | `9,058 / 8.2620%` | `7,885 / 7.1921%` | `10,259 / 9.3575%` | `8,244 / 7.5196%` | `11,342 / 10.3453%` | `8,924 / 8.1398%` |
| `SP2` | `7,711 / 7.0334%` | `6,816 / 6.2170%` | `8,509 / 7.7613%` | `6,992 / 6.3776%` | `9,334 / 8.5138%` | `7,483 / 6.8254%` |
| `SP3` | `6,833 / 6.2326%` | `6,131 / 5.5922%` | `7,425 / 6.7725%` | `6,178 / 5.6351%` | `8,061 / 7.3526%` | `6,539 / 5.9644%` |
| `SP4` | `6,207 / 5.6616%` | `5,595 / 5.1033%` | `6,638 / 6.0547%` | `5,600 / 5.1079%` | `7,120 / 6.4943%` | `5,855 / 5.3405%` |

---

## 8. 结果解读：应该怎样权衡

### 8.1 当前 production 默认口径对应什么位置

当前 `human_stage_1` production 逻辑等价于：

- first-pass：`FP5`
- second-pass：`SP3`

也就是：

- `low_score_threshold = 0.60`
- `bridge_low_score_gaps = false`
- `micro_stable_max_frames = 3`
- `max_repair_window_frames = 10`

该配置下的最终人工工作单元为：

- `8,061`
- 占原始总帧数 `7.3526%`

这可以视为当前对照基线。

### 8.2 最值得优先采用的 first-pass 优化：开启 `bridge`

如果只改一件事，把 current baseline 从 `FP5 + SP3` 改成 `FP6 + SP3`：

- `8,061 -> 6,539`
- 减少 `1,522`
- 相对下降约 `18.9%`

这个收益已经很可观，而且 bridge 的规则比较保守，因此它是一个典型的：

- 低风险
- 高收益

优化项。

### 8.3 `low_score_threshold` 从 `0.60` 调到 `0.50` 仍然有收益

在 `bridge=true` 的前提下，再把 `low_score_threshold` 从 `0.60` 调到 `0.50`，以 `SP3` 为例：

- `FP6 + SP3 = 6,539`
- `FP4 + SP3 = 6,178`

进一步减少：

- `361`

这说明：

- `0.60 -> 0.50` 仍然值得认真考虑

### 8.4 `0.50 -> 0.40` 的收益已经非常有限

这个结论是本次 sweep 里最关键的发现之一。

以 `SP3` 为例：

- `FP4 + SP3 = 6,178`
- `FP2 + SP3 = 6,131`

两者只差：

- `47`

以 `SP4` 为例：

- `FP4 + SP4 = 5,600`
- `FP2 + SP4 = 5,595`

两者只差：

- `5`

这意味着：

- 一旦开启 bridge，并配合较强的 second-pass
- 把 `low_score_threshold` 从 `0.50` 再进一步放宽到 `0.40`
- 已经几乎吃不到什么额外收益

但它仍然意味着更宽松地把低分框当成 simple frame，因此从风险收益比看，`0.40` 已不再是明显划算的选项。

### 8.5 second-pass 越强，工作单元越少，但过合并风险也越高

在同一个 first-pass 下，从 `SP1` 到 `SP4`，工作单元数会持续下降。

例如在 `FP4` 下：

- `SP1 = 8,244`
- `SP2 = 6,992`
- `SP3 = 6,178`
- `SP4 = 5,600`

这说明 second-pass 确实能稳定地继续降成本。

但 second-pass 的风险在于：

- 它是在 first-pass 之后做更积极的局部合并
- 合并得越强，越可能把本来不该由同一个代表帧概括的碎片压在一起

因此：

- `SP1 / SP2` 偏保守
- `SP4` 明显更偏成本导向
- `SP3` 更像一个中位的平衡点

---

## 9. 推荐的平衡配置

综合本次 sweep 的结果，推荐的平衡配置是：

- first-pass：`FP4`
- second-pass：`SP3`

也就是：

- `low_score_threshold = 0.50`
- `bridge_low_score_gaps = true`
- `high_overlap_iou = 0.25`
- `max_gap_frames = 2`
- `micro_stable_max_frames = 3`
- `max_repair_window_frames = 10`
- `min_non_simple_segments = 2`

### 9.1 为什么推荐这组

原因有三点：

1. 它比当前 baseline 明显更便宜  
   `8,061 -> 6,178`，减少 `1,883` 个工作单元，下降约 `23.4%`

2. 它比“只开 bridge”的保守方案还再省一截  
   `FP6 + SP3 = 6,539`，而 `FP4 + SP3 = 6,178`

3. 它几乎吃到了 `0.40` 宽松阈值的大部分收益，但更保守  
   `FP4 + SP3 = 6,178`  
   `FP2 + SP3 = 6,131`  
   差距只有 `47`

换句话说，这组配置的核心优势是：

- 比 current baseline 明显降本
- 比最激进配置更稳
- 比保守配置多拿到一部分真实收益
- 同时避免为了极小边际收益把 `low_score_threshold` 放得过低

### 9.2 在推荐配置下，最终仍要标注多少

推荐配置 `FP4 + SP3` 下，最终人工仍需处理：

- `6,178` 个 `human_stage_1` 工作单元
- 占原始总帧数 `109,634` 的 `5.6351%`

对于 `human_stage_1` 来说，这可以直接理解为：

- 标注员最终仍需人工查看 `6,178` 张代表帧

---

## 10. 与其他候选方案的关系

### 10.1 更保守的方案

若团队希望先拿一版低风险收益，可以优先考虑：

- `FP6 + SP3`

即：

- `low_score_threshold = 0.60`
- `bridge = true`
- 保持 second-pass 强度不变

结果是：

- `6,539`
- `5.9644%`

这比 current baseline 已经好很多，且改动最小。

### 10.2 更激进的方案

若团队只追求最低人工成本，本次 sweep 中最激进且效果最好的方案是：

- `FP2 + SP4`

结果是：

- `5,595`
- `5.1033%`

但它相比推荐配置 `FP4 + SP3` 只再少：

- `583` 个工作单元

从工程判断看，这部分额外收益并不足以自动证明它值得承受更高的过合并风险。

---

## 11. 最终建议

如果只给一句建议，本报告建议：

> 将 `human_stage_1` 的默认分段配置从当前等价的 `FP5 + SP3`，调整为 `FP4 + SP3`。

其含义是：

1. 保留当前 second-pass 的主强度不变
2. 打开保守 bridge
3. 把 `low_score_threshold` 从 `0.60` 放宽到 `0.50`
4. 不建议为了极小边际收益继续放宽到 `0.40`

这样做之后，`human_stage_1` 的第一轮人工工作量预计可从：

- `8,061`

降到：

- `6,178`

占原始总帧数比例从：

- `7.3526%`

降到：

- `5.6351%`

---

## 12. 附：本次分析脚本与结果文件

### 12.1 分析脚本

- `codes/process/analyze_human_stage_1_segmentation_grid.py`

### 12.2 自动生成结果

- `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/summary.md`
- `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/first_pass_summary.csv`
- `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/second_pass_grid.csv`
- `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/results.json`

### 12.3 验证

本次分析相关测试已通过：

```bash
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.test_analyze_human_stage_1_segmentation_grid \
  codes.test.test_process_human_stage_1_prep -v
```
