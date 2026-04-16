# First-Pass Coarse Labeling Design

## Goal

把当前段模式主线重新收敛成一个更便宜的前半段流程，使第一轮人工不再负责最终 bbox 标注，而只负责低成本确认：

- 某个 `p1-p7` 是否对应当前帧里的某个 AI 框
- 若不对应，是因为该人不存在，还是因为 AI 漏框 / 框明显错误

本设计的目标不是直接生成最终精确框，而是为后续第二轮精标和最终结果生成提供一层不瞎猜的、高质量身份参考。

## Context

当前仓库已经具备：

- A 阶段 AI 预标注
- 段模式分段
- `stable_segment` 代表帧标注
- `repair_window` 的早期实验实现

但现状有两个核心问题：

1. 第一轮人工任务过重
2. `repair_window` 的职责过重

第一轮仍然会牵涉 bbox 语义，成本高；而当前 `repair_window` 试图直接服务于最终框展开，导致算法需要在身份不稳定的碎片区做过多推断，性价比不高。

因此需要把第一轮任务彻底收缩成一个更便宜、更稳定的粗标分流层。

## Scope

本设计只覆盖：

- 整体流程重定义
- 前序自动步骤的职责划分
- 第一轮人工粗标的语义、页面交互和数据输出

本设计暂不细化：

- 第二轮任务池的精确生成规则
- 第二轮精标 UI 与交互
- 最终 frame-level 结果生成细节
- 局部升级 vs. 整段升级的优化规则

上述后半段只保留占位语义，不作为当前优先实现项。

## Recommendation

采用两层人工生产的主线：

1. 第一轮只做粗标分流
2. 第二轮只处理第一轮确认无法直接用 AI 的复杂段

也就是说：

- 第一轮负责低成本确认身份与 AI 可用性
- 第二轮才负责昂贵的 bbox 精标

这是当前最符合预算约束的方案。

## Overall Flow

新的主线流程定义为 `5` 步：

1. `AI 预标注`
2. `算法分段`
3. `第一轮人工粗标`
4. `算法计算第二轮任务池`
5. `第二轮人工精标 + 结果生成 + 复审`

其中当前优先落地的是前 `3` 步。

## Step 1: AI 预标注

### Purpose

对视频做逐帧检测与追踪，生成统一格式的 `pseudo_labels/*.auto.csv`。

### Responsibility

- 提供 frame-level AI 候选框
- 提供 `track_id`
- 为后续分段和第一轮粗标提供基础输入

### Non-Goals

- 不要求这一层输出最终正确身份
- 不要求这一层输出最终可交付 bbox

## Step 2: 算法分段

### Purpose

把 frame-level AI 结果整理成适合第一轮人工粗标的工作单元。

### First-Pass Segment Types

第一轮只允许以下 `3` 类工作单元：

1. `stable_segment`
2. `repair_window`
3. 极少量 `non_simple_single_frame`

### `stable_segment`

语义不变：

- 表示当前段在 identity / visibility 角度足够稳定
- 第一轮只看其代表帧

### `repair_window`

语义修改为：

- 不再以直接展开最终框为目标
- 改为服务第一轮粗标

生成规则先按简单、便宜版本定义：

- 把连续碎片段合并成一个 `repair_window`
- 连续碎片段可包含：
  - `non_simple_single_frame`
  - 很短的 `stable_segment`
- `repair_window` 最长不超过 `10` 帧
- 第一轮只看其中间那一帧

这里不再优先使用复杂的 `repairability_score`、hard break 筛子作为当前主线设计核心。

### `non_simple_single_frame`

仍然保留，但目标是：

- 尽量少
- 只在无法合理并入 `repair_window` 时进入第一轮

## Step 3: 第一轮人工粗标

### Core Principle

第一轮不再负责最终 bbox 标注。

第一轮的职责只有一件事：

对当前 segment 的单帧视图，低成本确认每个 `p1-p7` 与 AI 框之间的关系。

### Unified One-Frame Semantics

三类 segment 在第一轮统一成只看一帧的工作模式：

- `stable_segment`
  - 标代表帧
- `repair_window`
  - 只标中间帧
- `non_simple_single_frame`
  - 就标当前这一帧

### Slot Decision Space

对每个 `p1-p7`，第一轮只允许三选一：

1. `对应某个 AI 推荐框`
2. `不存在`
3. `存在，但 AI 没框 / AI 框明显错`

### Semantic Interpretation

三个选项分别对应：

#### 1. `ai_match`

该人物在当前帧存在，并且可直接对应到一个当前可见 AI 框。

#### 2. `absent`

该人物在第一轮粗标语义下按不存在处理。

这里统一吸收以下情况：

- 真正不在画面里
- 已出镜
- 遮挡到人也无法分辨身份

也就是说，第一轮不区分：

- `absent`
- `outside`
- 无法分辨身份的强遮挡

统一并入 `absent`。

#### 3. `needs_manual`

该人物在当前帧存在，但：

- AI 没给框
- 或 AI 框明显错误，不可直接使用

第一轮只记录这一事实，不要求给出手动画框。

### Hard Constraint: No Manual Boxes

第一轮必须禁止：

- 手动画框
- bbox 微调
- 新增 bbox 参数编辑语义

第一轮只做三选一判断，不做最终框。

### First-Pass UI Behavior

页面只保留：

- 原图
- 当前帧 AI 框
- `p1-p7` 槽位

每个槽位只允许执行：

- 选择某个 AI 框
- 标记为 `不存在`
- 标记为 `存在但 AI 错 / 漏`

页面不再出现第一轮手动画框入口。

### First-Pass Submission Payload

第一轮提交不存最终 bbox，而存 coarse decision。

建议每个槽位记录：

- `slot`
- `decision_type`
  - `ai_match`
  - `absent`
  - `needs_manual`
- `ai_track_id`
  - 仅在 `ai_match` 时存在

同时记录：

- `segment_id`
- `video_stem`
- `frame_index`
- `segment_type`

### First-Pass Output Meaning

第一轮产物不是最终标注结果，而是：

- 高质量身份参考
- AI 框可用性参考
- 第二轮是否需要精标的直接依据

## Deferred Later Stages

### Step 4 Placeholder: 第二轮任务池

当前只保留占位定义：

- 第一轮结束后，算法根据 coarse decision 生成第二轮任务池
- 对出现 `needs_manual` 的复杂段，优先整段升级进入第二轮
- 局部升级替代整段升级是后续优化项，不作为当前优先实现内容

### Step 5 Placeholder: 第二轮精标 + 结果生成 + 复审

当前只保留占位定义：

- 第二轮处理真正昂贵的 bbox 精标
- 算法生成 frame-level 结果
- 最终进入人工复审

不在本设计中展开。

## Why This Design Is Better

这版主线的优势在于：

1. 明确拆分了身份判断与 bbox 精标
2. 把第一轮成本压到最低
3. 让 `stable_segment` 与 `repair_window` 共用同一套第一轮语义
4. 让后续昂贵人工只花在真正需要的地方

第一轮不再承担最终框责任，不画框、不修框，只做便宜但关键的分流；第二轮才处理 AI 明显不可用的复杂情况。

## Files Likely Affected Later

本设计后续实现预计主要影响：

- `codes/process/process_segment_review_prep.py`
- `codes/application/ui_review_server.py`
- `codes/application/ui_review_web/app.js`
- `codes/test/test_process_segment_review_prep.py`
- `codes/test/test_segment_review_server.py`
- `codes/test/test_ui_review_web_static.py`

## Testing Direction

当前设计对应的第一轮测试重点应包括：

1. `stable_segment` 只返回代表帧粗标任务
2. `repair_window` 只返回中间帧粗标任务
3. 第一轮页面不再暴露手动画框入口
4. 每个槽位只允许：
   - `ai_match`
   - `absent`
   - `needs_manual`
5. `outside` 和不可分辨遮挡在第一轮统一进 `absent`
6. 第一轮产物存 coarse decision，而不是最终 bbox

## Rollout

推荐分两阶段推进：

### Phase A

只改：

- segment 语义
- 第一轮 UI 语义
- coarse decision 存储

不改：

- 第二轮精标
- 最终结果生成

### Phase B

在第一轮稳定后，再接：

- 第二轮任务池
- 第二轮精标
- 结果生成与复审

这样可以先把前半段链路跑通，再扩后半段。
