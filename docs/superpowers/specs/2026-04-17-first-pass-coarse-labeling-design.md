# First-Pass Coarse Labeling Design

## Goal

把当前段模式主线重构成一个更便宜的前半段流程，使第一轮人工不再负责最终 bbox 标注，而只负责低成本确认：

- 某个 `p1-p7` 是否对应当前帧里的某个 AI 框
- 若不对应，是因为该人不存在，还是因为 AI 漏框 / 框明显错误

本设计的目标不是直接生成最终精确框，而是为后续第二轮精标和最终结果生成提供一层不瞎猜的、高质量身份参考。

## Hard Constraints

以下几条是本设计的底线，不可违反：

1. 必须先完整跑一遍现有的 first-pass segmentation  
   必须先得到：
   - `stable_segment`
   - `non_simple_single_frame`

2. `repair_window` 只能建立在这份 first-pass 结果之上  
   它只能是 second-pass merge layer，不能替代 first-pass segmentation。

3. 不能改原来的 review UI  
   不允许继续在：
   - `codes/application/ui_review_server.py`
   - `codes/application/ui_review_web/`
   上叠加第一轮粗标语义。

4. 必须新起一套独立栈  
   第一轮人工粗标必须走新的独立服务和前端：
   - `human_stage_1`

5. 第一轮禁止手动画框  
   第一轮只能做三选一 coarse decision，不做 bbox 精修。

## Context

当前仓库已经具备：

- A 阶段 AI 预标注
- 段模式分段
- review UI / admin UI / review-result UI
- `repair_window` 的早期实验实现

但现状有两个核心问题：

1. 第一轮人工任务过重  
   当前第一轮仍然会牵涉 bbox 语义，成本高。

2. `repair_window` 的职责过重  
   当前 `repair_window` 试图直接服务于最终框展开，导致算法需要在身份不稳定的碎片区做过多推断，性价比不高。

因此需要把第一轮任务彻底收缩成一个更便宜、更稳定的粗标分流层。

## Scope

本设计只覆盖：

- 整体流程重定义
- 前序自动步骤的职责划分
- `human_stage_1` 的系统边界
- 第一轮人工粗标的语义、页面交互和数据输出

本设计暂不细化：

- 第二轮任务池的精确生成规则
- 第二轮精标 UI 与交互
- 最终 frame-level 结果生成细节
- 局部升级 vs. 整段升级的优化规则

上述后半段只保留占位语义，不作为当前优先实现项。

## Recommendation

采用“两层人工生产”的主线：

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

这里的 `算法分段` 必须严格分成两个顺序步骤：

1. 先按当前既有规则完成一次 first-pass segmentation，产出：
   - `stable_segment`
   - `non_simple_single_frame`
2. 再只基于这份 first-pass 结果，做 second-pass 的 `repair_window` 搜索与合并

`repair_window` 只能是 second-pass merge layer，不能替代 first-pass segmentation。

## Architecture

### Keep Existing UI Untouched

现有系统保持原样，不在其上叠加第一轮粗标语义：

- `codes/application/ui_review_server.py`
- `codes/application/ui_review_web/`
- `codes/application/ui_review_result_server.py`
- `codes/application/ui_review_result_web/`
- `codes/application/ui_admin_server.py`
- `codes/application/ui_admin_web/`

### New Independent Stage-1 Stack

第一轮人工粗标必须使用新的独立栈：

- 新后端：
  - `codes/application/ui_human_stage_1_server.py`
- 新前端：
  - `codes/application/ui_human_stage_1_web/index.html`
  - `codes/application/ui_human_stage_1_web/app.js`
  - `codes/application/ui_human_stage_1_web/styles.css`

### Separate Stage-1 Storage

第一轮粗标结果不能复用当前 `ui_review.sqlite3` 的语义，建议在 batch 下新增独立目录：

```text
annotation/batch_<...>/
├── human_stage_1_prep/
├── human_stage_1/
│   ├── ui_human_stage_1.sqlite3
│   ├── assignment_log.csv
│   ├── coarse_labels_raw/
│   └── coarse_labels_export/
```

这样可以保证：

- 原 review 流程不被污染
- 第一轮 coarse decision 与后续精标结果分开存储
- 可以独立重跑 prep，而不影响原 review 数据

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

### Hard Constraint

这一层必须遵守以下底线：

- 必须先完整跑一遍现有的 first-pass 规则
- 必须先得到：
  - `stable_segment`
  - `non_simple_single_frame`
- 然后才能在这份结果之上寻找并合并 `repair_window`

明确禁止：

- 直接从 raw frame / raw detection 生成 `repair_window`
- 用 `repair_window` 替代 `stable_segment + non_simple_single_frame` 的 first-pass 主语义
- 先做 `repair_window`，再回头补 stable / non-simple

一句话说，`repair_window` 只能建立在“现有稳定段 + 复杂单帧”的第一次切分结果之上，它是 second-pass merge，不是 first-pass segmentation。

### Prep Execution Mode

为了强制保证上面的顺序，建议新增一个独立离线脚本：

- `codes/process/process_human_stage_1_prep.py`

它的职责是：

1. 读取 `pseudo_labels/*.auto.csv`
2. 先调用或复用现有 first-pass 规则，得到：
   - `stable_segment`
   - `non_simple_single_frame`
3. 再在这份结果上做 second-pass `repair_window` 合并
4. 输出供第一轮 UI 使用的 `human_stage_1_prep/`

### First-Pass Segment Types

first-pass 只允许以下 `2` 类基础结果：

1. `stable_segment`
2. `non_simple_single_frame`

在 first-pass 完成之后，最终进入第一轮人工粗标的工作单元才允许是以下 `3` 类：

1. `stable_segment`
2. `repair_window`
3. 极少量剩余 `non_simple_single_frame`

### `stable_segment`

语义不变：

- 表示当前段在 identity / visibility 角度足够稳定
- 第一轮只看其代表帧

### `repair_window`

语义修改为：

- 不再以直接展开最终框为目标
- 改为服务第一轮粗标

生成规则必须建立在 first-pass 结果之上，先按简单、便宜版本定义：

- 从连续碎片段中搜索可合并区间
- 把 second-pass 选中的连续碎片段合并成一个 `repair_window`
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

### Prep Output

建议在 batch 下新增：

```text
annotation/batch_<...>/
└── human_stage_1_prep/
    ├── <video_stem>.segments.json
    ├── <video_stem>.segment_frames.json
    └── human_stage_1_prep_summary.json
```

这套产物就是 `ui_human_stage_1_server.py` 的唯一上游输入。

## Step 3: 第一轮人工粗标

### Core Principle

第一轮不再负责最终 bbox 标注。

第一轮的职责只有一件事：

对当前 segment 的单帧视图，低成本确认每个 `p1-p7` 与 AI 框之间的关系。

### Unified One-Frame Semantics

三类 segment 在第一轮统一成“只看一帧”的工作模式：

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

### `human_stage_1` UI Behavior

页面只保留：

- 原图
- 当前帧 AI 框
- `p1-p7` 槽位

每个槽位只允许执行：

- 选择某个 AI 框
- 标记为 `不存在`
- 标记为 `存在但 AI 错 / 漏`

页面不再出现第一轮手动画框入口。

### `human_stage_1` Server Responsibilities

`ui_human_stage_1_server.py` 只负责：

- 读取 `human_stage_1_prep/`
- 按最终工作单元派发任务
- 返回当前单帧粗标视图
- 接收 coarse decision
- 存储第一轮结果

它不负责：

- 重算分段
- 生成最终 bbox
- 替代原 `ui_review_server.py`

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
5. 保证原 review UI 完全不受第一轮粗标改造影响

第一轮不再承担最终框责任，不画框、不修框，只做便宜但关键的分流；第二轮才处理 AI 明显不可用的复杂情况。

## Files Likely Affected Later

本设计后续实现预计主要影响：

### New

- `codes/process/process_human_stage_1_prep.py`
- `codes/application/ui_human_stage_1_server.py`
- `codes/application/ui_human_stage_1_web/index.html`
- `codes/application/ui_human_stage_1_web/app.js`
- `codes/application/ui_human_stage_1_web/styles.css`

### Reused or Referenced

- `codes/process/process_segment_review_prep.py`
- `codes/process/segment_prep_common.py`
- `codes/test/test_process_segment_review_prep.py`
- `codes/test/test_segment_review_server.py`

### New Tests

- `codes/test/test_process_human_stage_1_prep.py`
- `codes/test/test_ui_human_stage_1_server.py`
- `codes/test/test_ui_human_stage_1_web_static.py`

## Testing Direction

当前设计对应的第一轮测试重点应包括：

1. 先完成 first-pass，产出 `stable_segment + non_simple_single_frame`
2. `repair_window` 只能在 first-pass 结果上 second-pass 合并生成
3. `ui_human_stage_1_server.py` 只读取 `human_stage_1_prep/`，不自行重算分段
4. `stable_segment` 只返回代表帧粗标任务
5. `repair_window` 只返回中间帧粗标任务
6. 第一轮页面不再暴露手动画框入口
7. 每个槽位只允许：
   - `ai_match`
   - `absent`
   - `needs_manual`
8. `outside` 和不可分辨遮挡在第一轮统一进 `absent`
9. 第一轮产物存 coarse decision，而不是最终 bbox
10. 原 `ui_review_server.py` 与 `ui_review_web/` 不发生语义回归

## Rollout

推荐分两阶段推进：

### Phase A

只改：

- first-pass 之后的 second-pass `repair_window` 合并层
- 新的 `human_stage_1_prep/`
- 新的 `ui_human_stage_1_server.py`
- 新的 `ui_human_stage_1_web/`
- coarse decision 存储

不改：

- 第二轮精标
- 最终结果生成
- 原 `ui_review_server.py`

### Phase B

在第一轮稳定后，再接：

- 第二轮任务池
- 第二轮精标
- 结果生成与复审

这样可以先把前半段链路跑通，再扩后半段。
