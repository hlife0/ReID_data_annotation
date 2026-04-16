# Repair Window Fragmentation Reduction Design

## Goal

在不推翻当前段模式主线的前提下，减少碎片化严重区域带来的人工工作单元数量。

本设计的目标不是把复杂区域全部自动化，而是识别“虽然被切得很碎，但仍然具有短时连续性”的局部区域，并把它们从一串碎片段升级为一个受控的 `repair_window`：

- 默认窗口长度不超过 `10` 帧
- 人工只标少量 `anchor frames`
- 其余帧由系统在短窗口内保守补全
- 一旦补全条件不足，立即回退到更保守的人工路径

## Context

当前主线已经完成：

- AI 预标注
- `stable_segment` / `non_simple_single_frame` 离线分段
- 段级 review
- 段结果展开成逐帧 `p1-p7`

当前最有效的降本来源是：

- 长稳定段只标代表帧
- 历史 `track -> slot` 推荐预填

但在若干 session 中，局部时段仍然被切成大量单帧难例或超短稳定段。这些区域常见于：

- 短暂低分抖动
- 局部框重叠
- 极短遮挡
- 轻微 track 抖动

它们未必需要逐帧人工处理，但当前系统会把它们拆成很多工作单元，造成人工点击和心智切换成本上升。

## Scope

本次设计只解决：

- 碎片簇识别
- `repair_window` 候选生成
- `repair_window` 的 anchor 标注工作流
- 非 anchor 帧的短窗口补全
- 补全失败时的保守回退

本次不做：

- 全自动通过高置信段
- 超过 `10` 帧的长窗口插值
- 基于完整时间轴的密集关键帧编辑器
- 修改当前 SQLite 的基础 annotation schema

## Alternatives

### Option A: 只继续扩展现有 bridge 规则

优点：

- 改动最小
- 主要集中在 `segment_prep`
- 不必新增新的 segment type

缺点：

- 只能吃掉非常局部的抖动
- 对“已经碎成很多小段”的区域收益有限
- 一旦桥接条件放宽过头，风险是静默误并段

### Option B: 引入 `repair_window`，处理碎片簇

优点：

- 直接针对“局部过碎”问题，而不是只修单个坏点
- 既减少工作单元，又保留人工兜底
- 风险被 `<= 10` 帧和回退规则限制在局部窗口内

缺点：

- 需要改离线 prep、在线服务和前端交互
- 需要新增一套补全和回退语义

### Option C: 先保留碎片段，事后离线合并结果

优点：

- 不打断当前前端
- 实现风险较低

缺点：

- 不能降低第一轮人工工作单元数
- 与本次“减少人工干预”的目标不匹配

## Recommendation

选择 Option B，并少量吸收 Option A 的思想。

具体来说：

- 保留当前 `stable_segment` / `non_simple_single_frame` 第一阶段切分
- 继续允许保守 bridge 吃掉明显检测抖动
- 在第一阶段切分完成后，再专门识别碎片簇
- 只把“短、碎、可修复”的区域升级成 `repair_window`

这样可以避免一次性推翻现有语义，同时把降本重点放到 hardest sessions 的碎片区。

## Design

### 1. 总体流程

新的离线流程分为两阶段：

1. 第一阶段：保持现有规则，产出
   - `stable_segment`
   - `non_simple_single_frame`
2. 第二阶段：扫描第一阶段的 segment 序列，识别局部碎片簇，择优升级为 `repair_window`

升级后的输出结果必须仍然满足：

- 同一视频所有 segment 互不重叠
- 覆盖全部帧
- 每帧仍然只属于一个最终工作单元

最终 segment 类型变为：

- `stable_segment`
- `non_simple_single_frame`
- `repair_window`

### 2. 第一阶段需要额外缓存的 frame-level 特征

为支持第二阶段扫描，第一阶段在处理每帧时额外缓存下列描述子：

- `track_ids(t)`
- `bad_reason(t)`
  - `simple`
  - `low_only`
  - `overlap_only`
  - `both`
- `visible_count(t)`
- 相邻帧 `track_ids` 的 Jaccard
- 同一 `track_id` 在相邻帧的 bbox IoU
- 当前帧是否已被 bridge 规则修复

这些特征仅服务于离线扫描，不改变当前 review payload。

### 3. 碎片簇 seed 识别

不是所有短段都值得进入 `repair_window`。第二阶段只从高价值 seed 出发。

一个 segment 会成为 seed，当它满足任一条件：

- `segment_type = non_simple_single_frame`
- `segment_type = stable_segment` 且 `frame_count <= 2`
- 它位于一个局部高碎片区域中

局部高碎片区域的判定窗口为最多 `10` 帧，满足以下全部条件时成立：

- 窗口总跨度 `<= 10` 帧
- 窗口内至少有 `3` 个 segment
- 窗口内至少有 `2` 个 `non_simple_single_frame`
  - 或至少有 `2` 个 `frame_count <= 2` 的超短稳定段

### 4. 从 seed 扩张候选 `repair_window`

从 seed 开始，按 segment 为单位向左右扩张候选窗。

允许被吸收进候选窗的 segment 定义为“小碎片”：

- `non_simple_single_frame`
- `stable_segment` 且 `frame_count <= 3`

扩张规则：

- 总窗口跨度始终 `<= 10` 帧
- 只吸收仍属于小碎片的相邻 segment
- 吸收后若 provisional 连续性指标跌破后续硬门槛，则停止扩张

停止扩张条件：

- 再扩张会让窗口跨度超过 `10`
- 遇到 `frame_count >= 4` 的较长稳定段
- 起终点 `track_ids` 差异过大
- 出现明显硬断裂事件

硬断裂事件包括：

- 窗口内多个人同时消失或同时新出现
- 连续 `>= 2` 帧 `both`
- 连续 `>= 3` 帧 `overlap_only`
- 人数大幅跳变

### 5. `repairability` 判定

不是每个候选窗都应该交给 repair 流程。必须同时通过硬门槛和软评分。

#### 5.1 硬门槛

候选窗必须满足：

- `window_len <= 10`
- `segment_count >= 3`
- 窗口端点 `track_ids` 的 Jaccard `>= 0.6`
- 相邻帧 `track_ids` 的 Jaccard `>= 0.6` 的帧对占比 `>= 70%`
- 主导 `track_id` 的相邻 bbox IoU 均值 `>= 0.35`
- 不存在明显硬断裂事件

不满足任一条件，则该窗不可升级为 `repair_window`。

#### 5.2 软评分

对通过硬门槛的候选窗，计算：

`fragmentation_score`

- `2 * non_simple_count`
- `+ 1 * micro_stable_count`
- `+ 1 * boundary_count`

`repairability_score`

- `0.35 * endpoint_track_jaccard`
- `+ 0.35 * mean_adjacent_track_jaccard`
- `+ 0.20 * mean_same_track_iou`
- `+ 0.10 * clean_frame_ratio`

其中：

- `micro_stable_count` 指 `frame_count <= 3` 的稳定段数量
- `boundary_count` 指窗内 segment 切换次数
- `clean_frame_ratio` 指 `bad_reason = simple` 或已被 bridge 修复的帧占比

### 6. 只保留“真能省工”的窗

每个候选窗都要计算：

- `expected_old_tasks`
- `expected_new_tasks`
- `expected_gain = expected_old_tasks - expected_new_tasks`

默认估计规则：

- `expected_old_tasks = 当前窗口内已有 segment 数`
- `expected_new_tasks = repair_window 所需 anchor 数`

只有满足以下条件时才保留：

- `fragmentation_score >= 6`
- `repairability_score >= 0.70`
- `expected_gain >= 2`

如果一个窗当前只有 `3` 个任务，改成 `3` 个 anchor 后并没有减少人工任务数，则不应生成 `repair_window`。

### 7. 冲突候选的选择

多个候选窗可能重叠。最终输出必须是一组互不重叠的 repair windows。

处理规则：

- 先枚举全部候选窗
- 按 `priority_score = repairability_score * expected_gain` 降序排序
- 从高到低贪心选择
- 已选窗口覆盖的帧，不能再被其他 `repair_window` 占用

未被选中的区域，继续保留原始：

- `stable_segment`
- `non_simple_single_frame`

### 8. `repair_window` 的离线产物

在 `segment_prep/*.segments.json` 中，`repair_window` 记录至少新增：

- `segment_id`
- `video_stem`
- `segment_type = repair_window`
- `start_frame`
- `end_frame`
- `frame_count`
- `anchor_candidates`
- `track_ids`
- `repairability_score`
- `fragmentation_score`
- `expected_gain`
- `trigger_reason`

`anchor_candidates` 为候选 anchor frame 列表，真正用于人工标注的 anchor 可由服务端按规则最终选定。

### 9. `repair_window` 的人工工作语义

`repair_window` 是一个工作单元，但它内部包含多个必须人工确认的 keyframes。

默认 anchor 规则：

- `window_len <= 4`
  - 标 `2` 帧：首帧、末帧
- `5 <= window_len <= 10`
  - 标 `3` 帧：首帧、中点帧、末帧

推荐再加一层“坏帧优先替换”：

- 若窗口内存在 `overlap_only` 或 `both` 的帧
- 则优先把这类最坏帧纳入 anchor 集合
- 总 anchor 数仍不超过 `3`

最坏帧排序规则固定为：

- `both` 优先于 `overlap_only`
- `overlap_only` 优先于 `low_only`
- 同类并列时，优先选择最接近窗口中点的帧

因此默认 anchor 选择顺序为：

1. 首帧
2. 末帧
3. 窗口内最坏帧
4. 若无明显最坏帧，则使用中点帧

前端交互应是：

- 显示当前窗第 `1/n`、`2/n`、`3/n` 个 anchor
- 标注员完成全部 anchor 后
- 系统先自动补全其余帧
- 再向标注员展示一次 repair 结果预览
- 标注员做最终确认提交

### 10. 非 anchor 帧的补全策略

补全不是单一“线性插值”，而是按 slot 的 source 分层处理。

#### 10.1 两侧 anchor 都绑定到同一 `ai_track_id`

优先采用 track 跟随：

- bbox 取当前帧 AI box
- 若 anchor 上存在人工微调
  - 则对相对 AI box 的偏移量做短距离线性插值

输出 provenance：

- `ai_follow`
- `ai_follow_with_offset_interp`

#### 10.2 两侧都是人工框，但无稳定同 track

只在短窗口内允许 bbox 线性插值。

输出 provenance：

- `manual_param_interpolated`

#### 10.3 一侧 `absent`，一侧 `present`

不直接插值 bbox，而是按距离做分段选择：

- 靠近 `present` anchor 的帧继承 `present`
- 靠近 `absent` anchor 的帧继承 `absent`

输出 provenance：

- `piecewise_absent_present`

#### 10.4 两侧都 `absent`

中间全部继承 `absent`。

#### 10.5 任一侧是 `occluded` / `outside`

默认不做长距离插值。

仅允许 very-short propagation：

- 相邻 `1-2` 帧内可复制
- 超过后必须回退成更多人工 anchor 或整窗降级

### 11. 在线回退与降级

回退分为离线回退和在线回退。

#### 11.1 离线回退

在候选窗生成阶段，只要不满足硬门槛或预期收益不足，就不生成 `repair_window`，继续保留原始分段。

#### 11.2 在线回退

在人工完成 anchor 后，系统对每个非 anchor 帧、每个 slot 计算 `frame_fill_confidence`。

触发在线失败的条件包括：

- 需要跟随的 `ai_track_id` 在目标帧缺失
- 两侧 anchor 指向不同 track，且不存在稳定 piecewise 解释
- 插值后 bbox 异常
  - 宽高跳变过大
  - 中心点跳变过大
  - bbox 越界过多
- source 状态在邻近帧之间明显自相矛盾

回退动作分三级：

1. 轻度失败
   - 允许再增加 `1` 个人工 anchor
   - 总 anchor 数不得超过 `4`
2. 中度失败
   - 允许把一个 `repair_window` 拆成两个更小的 `repair_window`
3. 重度失败
   - 整窗降级回原始碎片段

上限规则：

- 默认 anchor 数 `2-3`
- 最大 anchor 数 `4`
- 超过 `4` 仍无法稳定补全，则必须降级

### 12. 数据库与服务端影响

本设计不要求新增 annotation 主表字段。

原因：

- `repair_window` 最终仍然写回 frame-level `annotations`
- `segment_reviews.segment_type` 已是文本字段，可直接容纳 `repair_window`

需要调整的主要是：

- segment JSON 解析与 payload
- 服务端对 `repair_window` 的读取与提交流程
- 补全 provenance 的 frame-level 写入

### 13. 验证与 rollout

#### 13.1 影子评估

第一步只修改离线 prep，输出并行统计，不改 UI：

- 原始 `segment_count`
- 引入 `repair_window` 后的新工作单元数
- 每个窗口的 `expected_gain`
- 窗口长度分布
- fallback 预测率
- 受益最大的 session 排名

影子评估重点观察 hardest sessions：

- `20260410_195433_seg_200624895`
- `20260410_195433_seg_202322593`
- `20260410_195433_seg_210024755`

#### 13.2 小流量试运行

只在高 repairability 的 session 上启用，并限制：

- `window_len <= 10`
- `repairability_score` 高于正式阈值
- 以 `low_only` 主导
- 不含明显人数突变

试运行需要记录：

- 每 `1000` 帧所需人工工作单元数
- 每个 `repair_window` 的实际 anchor 数
- 在线 fallback 率
- 标注员最终确认前的返修率
- repair 结果后续被编辑或推翻的比例

#### 13.3 正式扩大

只有当以下条件同时满足时，才扩大范围：

- 人工工作单元数显著下降
- fallback 率处于可接受水平
- 标注员返修率无明显恶化
- hardest sessions 的收益高于 easiest sessions 的锦上添花收益

## Files

### Code

- Modify: `codes/process/process_segment_review_prep.py`
- Modify: `codes/process/segment_prep_common.py`
- Modify: `codes/application/ui_review_server.py`
- Modify: `codes/application/ui_review_web/app.js`

### Tests

- Modify: `codes/test/test_process_segment_review_prep.py`
- Modify: `codes/test/test_segment_review_server.py`
- Modify: `codes/test/test_ui_review_server.py`

### Docs

- Create: `docs/superpowers/specs/2026-04-17-repair-window-fragmentation-design.md`
- Create: `docs/superpowers/plans/2026-04-17-repair-window-fragmentation.md` after spec approval
- Update: batch summary / experiment notes after shadow evaluation

## Testing Strategy

至少覆盖以下测试：

1. 第一阶段原有 `stable_segment` / `non_simple_single_frame` 逻辑不被破坏
2. 能识别局部高碎片区域并生成 `repair_window`
3. 候选窗超过 `10` 帧时不会生成 `repair_window`
4. repairability 不足时不会生成 `repair_window`
5. 重叠候选窗按 `priority_score` 贪心去重
6. `repair_window` 默认 anchor 选择符合规则
7. 同 track 双端约束时，非 anchor 帧走 `ai_follow` 或 `ai_follow_with_offset_interp`
8. absent / present 冲突时走 piecewise 规则，而不是直接 bbox 插值
9. 在线补全失败时，可追加 anchor、拆窗或整窗降级
10. 降级后仍能回到现有保守人工路径

## Rollout Notes

实现顺序建议严格遵守：

1. 先做离线候选扫描与影子统计
2. 再决定阈值
3. 再接服务端 `repair_window` 语义
4. 最后接前端 anchor 标注与预览确认

这样即使影子评估显示收益不明显，也能在进入 UI 改造前止损。
