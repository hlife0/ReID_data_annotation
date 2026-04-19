# 标注者上手指南（review 段模式）

说明：

- 本文档描述的是 `ui_review_server.py` 对应的 review UI
- 它不是 `human_stage_1` 的粗标说明
- 如果你要看 `human_stage_1` 当前策略，请优先看：
  - [README.md](/home/hrli/data_annotation/docs/README.md)
  - [BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md](/home/hrli/data_annotation/docs/BATCH_20260417_V01_HUMAN_STAGE_1_SEGMENTATION_OPTIMIZATION_REPORT.md)

当前标注界面的默认工作单位是：

- 一个段

当前 review 服务里，一个段可能是以下三种情况之一：

1. `stable_segment`
2. `non_simple_single_frame`
3. `repair_window`

你不需要理解后台如何分段，只需要按界面给出的当前图片或 anchor 图直接标注。

---

## 1. 你要做什么

你的目标很简单：

- 对当前图片上的 `p1-p7` 进行标注

系统会自动负责：

- 这张图属于哪个段
- 这一段如何展开成逐帧结果

---

## 2. 你在界面里会看到什么

打开页面后，你主要会看到：

1. 顶部按钮
   - `下一段`
   - `跳过当前段`
   - `提交并下一段`
2. 状态条
   - 视频名
   - 当前帧号
   - 时间戳
   - 标注次数
3. 段摘要条
   - 段类型
   - 段 id
   - 段范围
   - 当前图里有哪些 AI track
4. 左侧画布
   - 当前图片
   - AI 框
   - 你画出来的 `p1-p7` 框
5. 右侧槽位编辑区
   - `p1-p7`
   - AI 框应用
   - 自动推荐预填
   - 手动画框
   - 不存在 / 遮挡 / 出画
   - `其余设为不存在`

---

## 3. 你的默认操作流程

1. 点 `下一段`
2. 看当前图片
3. 选中要处理的 `p1-p7`
4. 对每个槽位：
   - 先看系统是否已经自动预填推荐框
   - 直接应用 AI 框
   - 或手动画框
   - 或标记不存在
   - 必要时标记遮挡 / 出画
5. 如果剩下很多空槽位本来就没人：
   - 点 `其余设为不存在`
6. 点 `提交并下一段`

你不需要：

- 手动找问题区间
- 看时间轴
- 理解后台的段展开逻辑

---

## 4. 稳定段和单帧难例怎么理解

### 稳定段

系统会从这个段里挑一张代表图给你。

你只需要把这张代表图标清楚：

- 哪个 AI track 对应哪个 `p1-p7`
- 框是否需要微调

后台会把这张图的身份结果传播到整段。

### 单帧非简单帧

这类段只有一帧。

你把它当成一张普通复杂图片直接标完就行。

### `repair_window`

这类段表示一小段局部碎片区间。

你通常不会只看 1 张图，而是会按界面要求处理几个 anchor frame。

你需要做的是：

- 在每个 anchor 上完成槽位标注
- 确认身份关系没有错
- 让系统再根据这些 anchor 自动填中间帧

---

## 5. 按钮含义

### `应用AI框`

把当前 AI track 直接放到你选中的 `p1-p7` 槽位上。

### 自动推荐预填

系统会根据当前 session 里已经提交过的 `track -> p1-p7` 历史关系，自动给当前段里的可见 AI track 做推荐。

这意味着你打开一个段时，部分槽位可能已经被系统先填好：

- 身份对应关系
- 对应 AI 框

你只需要：

- 确认它对不对
- 错了就改

### `其余设为不存在`

把当前还没有分配、仍然处于“未设置”的槽位，批量标记为：

- `不存在`

这个按钮不会改动已经有结果的槽位，例如：

- 已应用 AI 框
- 已手动画框
- 已标记不存在 / 遮挡 / 出画

### `绘制新框`

在画布上自己画框。

### `不存在`

这个人物在当前图里没有出现。

### `遮挡`

这个人物在当前图里存在，但被挡住了。

### `出画`

这个人物已经离开了画面。

### `提交并下一段`

提交当前图片结果，并进入下一段。

若当前段是 `repair_window`，通常需要先完成当前要求的 anchor，再进入下一段。

---

## 6. 质量要求

1. `p1-p7` 身份不要混
2. 框尽量贴合人物可见区域
3. 能用 AI 框时优先用，再微调
4. 不确定时先保证槽位身份正确
5. 如果系统已经预填，优先检查预填结果而不是从空白重做

---

## 7. 相关文档

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
