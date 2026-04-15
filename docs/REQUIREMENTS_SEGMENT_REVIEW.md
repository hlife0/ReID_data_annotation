# 需求文档 Y：段模式 Review（稳定段 + 单帧非简单帧）

最后更新：2026-04-15

---

## 1. 文档目标

本文档定义一条新的 review 主线：

- 不再以 `issue` 为主语义
- 不再以“风险帧 / 风险区间”作为人工工作单位
- 改为先离线分段，再按段分发给标注者

这条主线的唯一目标是：

> 对每个 `session` 的每一帧，最终输出完整的 `p1-p7` 结果。

其中：

- `p1-p7` 表示固定真人身份槽位
- `AI track_id` 仅是中间辅助对象，不是最终交付对象

---

## 2. 设计约束

本方案必须满足以下约束：

1. 主语义必须是“段”，不是 `issue`
2. 离线阶段必须先把每个 `session` 切成很多标注段
3. 每个标注段只能是两种类型之一：
   - `stable_segment`
   - `non_simple_single_frame`
4. 标注者不应看到复杂的段定义细节
5. 标注者在前端上仍然只需要“看图并标图”
6. 最终必须能把段级标注结果展开成逐帧 `p1-p7` 结果

---

## 3. 数学基础

本方案的术语严格建立在：

- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)

之上。

后续所有实现、接口、产物、验证，必须服从该文档中的以下核心对象：

1. `simple frame`
2. `stable segment`
3. `non-simple frame`
4. `segment-level identity mapping`
5. `frame-level final result`

本文档中不重新定义这些数学对象；若表述与数学定义冲突，以数学定义文档为准。

---

## 4. 核心对象

### 4.1 标注段 `annotation segment`

一个 `annotation segment` 是一个可直接分发给标注者的工作单位。

对任意 `session`，其所有标注段必须构成该 `session` 全帧集合的一个不交覆盖。

### 4.2 段类型

每个标注段必须且只能属于以下两类之一：

1. `stable_segment`
2. `non_simple_single_frame`

其中：

- `stable_segment` 的定义严格沿用数学定义文档中的稳定段
- `non_simple_single_frame` 指由一个非简单帧单独形成的单帧区间 `[t,t]`

### 4.3 代表帧 `representative_frame`

每个 `stable_segment` 必须指定一个代表帧：

- `representative_frame ∈ [start_frame, end_frame]`

代表帧是该稳定段对标注者展示的唯一默认帧。

`non_simple_single_frame` 的代表帧就是它自身唯一的一帧。

### 4.4 段级身份映射

对每个 `stable_segment`，系统最终需要得到一个段级身份映射：

```text
track_id -> p1-p7
```

更精确地说，是数学定义文档中的单射：

```text
phi_S : K(S) -> P
```

其中：

- `K(S)` 是该稳定段的恒定可见轨迹集合
- `P={p1,...,p7}` 是固定人物槽位集合

### 4.5 逐帧结果

系统最终输出的是：

- 对每个帧
- 对每个 `p1-p7`
- 给出完整状态结果

也就是数学定义文档中的：

```text
R_sigma(t, p)
```

---

## 5. 离线分段要求

### 5.1 总原则

对每个 `session`，后端必须先做离线分段，得到一组标注段。

这组标注段必须满足：

1. 互不重叠
2. 完全覆盖该 `session` 的全部帧
3. 每段都是合法的 `stable_segment` 或 `non_simple_single_frame`

### 5.2 稳定段生成规则

离线阶段必须先计算：

- 每帧是否为 `simple frame`

然后按照数学定义求出所有极大稳定段：

- 区间内轨迹集合恒定
- 区间内每一帧都是简单帧

得到所有 `stable_segment`。

### 5.3 单帧非简单段生成规则

对所有不属于任何稳定段的帧：

- 每一帧单独生成一个 `non_simple_single_frame`

不得把多个非简单帧合并成一个多帧复杂段。

也就是说，剩余部分一律按“逐帧难例”处理。

### 5.4 代表帧选择规则

对每个 `stable_segment`：

1. 必须选择一个 `representative_frame`
2. 该帧必须落在该段内部
3. 该选择规则必须是确定性的

本方案将代表帧固定定义为稳定段中点帧：

```text
representative_frame = floor((start_frame + end_frame) / 2)
```

不得使用随机抽取。

---

## 6. 离线产物

建议新增目录：

```text
./annotation/batch_<...>/
├── segment_prep/
│   ├── <video_stem>.segments.json
│   ├── <video_stem>.segment_frames.json
│   └── segment_prep_summary.json
```

### 6.1 `<video_stem>.segments.json`

必须包含该视频的全部标注段。

每条记录至少包含：

1. `segment_id`
2. `video_stem`
3. `segment_type`
4. `start_frame`
5. `end_frame`
6. `representative_frame`
7. `track_ids`
8. `frame_count`

其中：

- 若 `segment_type=stable_segment`
  - `track_ids` 必须等于该段恒定轨迹集合
- 若 `segment_type=non_simple_single_frame`
  - `start_frame=end_frame=representative_frame`

### 6.2 `<video_stem>.segment_frames.json`

必须能从帧快速查到它所属的 `segment_id`。

用途：

1. 服务端按帧反查所属段
2. admin 做段级/帧级统计
3. 后续展开逐帧结果时快速索引

### 6.3 `segment_prep_summary.json`

必须给出批次级统计：

1. `video_count`
2. `segment_count`
3. `stable_segment_count`
4. `non_simple_single_frame_count`
5. `avg_stable_segment_length`
6. `max_stable_segment_length`

---

## 7. 在线服务要求

### 7.1 主语义

在线 review 服务必须以 `segment` 为唯一主语义。

不得再以 `issue` 作为主分发单位。

### 7.2 主接口

服务端主接口应改为：

1. `POST /api/next_segment`
2. `GET /api/segment_detail`
3. `POST /api/submit_segment`

可选接口：

1. `GET /api/segments?...`
2. `GET /api/my_segments?...`

### 7.3 `next_segment`

`next_segment` 必须返回：

1. `segment_id`
2. `segment_type`
3. `video_stem`
4. `start_frame`
5. `end_frame`
6. `representative_frame`
7. 当前代表帧图像信息
8. 当前代表帧的 AI boxes
9. 当前可见 `track_ids`
10. 动态 `slot_names`

### 7.4 `segment_detail`

`segment_detail` 必须能返回完整段元数据。

对 `stable_segment`，应至少返回：

1. `track_ids`
2. `representative_frame`
3. 该段范围

对 `non_simple_single_frame`，应至少返回：

1. 单帧图像
2. 当前帧 AI boxes

### 7.5 `submit_segment`

`submit_segment` 的语义按段类型区分：

#### 对 `stable_segment`

提交内容必须足以确定：

- 该段代表帧上的 `track_id -> p1-p7` 身份映射

具体要求：

1. 对每个可见人物槽位，后端必须最终得到唯一的 `ai_track_id`
2. 若前端已显式提交 `ai_track_id`，则直接采用
3. 若前端只提交了人工框而未显式给出 `ai_track_id`，则后端必须尝试在代表帧上把该框唯一匹配到一个 AI track
4. 若无法唯一匹配，则该次 `stable_segment` 提交必须失败，不得在不确定映射下自动扩展整段
5. 一旦映射唯一确定，允许把人工框相对代表帧 AI 框的几何修正传播到整段

也就是说，`stable_segment` 的本质仍然是：

- 代表帧上确定 `track_id -> p1-p7`

人工框只是在该映射确定后，用于提供几何修正。

服务端收到后，必须据此把该稳定段诱导为逐帧 `p1-p7` 结果。

#### 对 `non_simple_single_frame`

提交内容必须是：

- 该帧完整的 `p1-p7` 结果

服务端收到后，直接将该帧结果写入最终逐帧结果层。

---

## 8. 前端交互要求

### 8.1 标注者视角

前端必须继续满足：

- 标注者看起来仍像“直接标图片”

不要求标注者理解：

- 稳定段
- 非简单帧
- 数学定义
- 分段算法

### 8.2 展示要求

前端默认只展示：

1. 当前段的一张图片
2. 当前图片上的 AI boxes
3. `p1-p7` 编辑区

不要求向标注者暴露：

- issue list
- issue timeline
- 风险分层细节
- 复杂传播控制

### 8.3 对 `stable_segment`

前端应把该段视为：

- 一个代表帧图片任务

标注者在该代表帧上完成：

- 可见轨迹到 `p1-p7` 的对应

### 8.4 对 `non_simple_single_frame`

前端应把该段视为：

- 一张普通复杂帧图片任务

标注者在该帧上直接完成完整结果。

---

## 9. 从段级结果到逐帧结果

### 9.1 稳定段展开

对每个 `stable_segment S=[m,n]`：

1. 读取其段级身份映射
2. 对每个 `t∈[m,n]`
3. 对每个 `p∈P`
4. 根据该段恒定轨迹集合与该帧 AI bbox
   生成该帧的 `p1-p7` 结果

也就是说，稳定段的逐帧结果由：

1. 段级身份映射
2. 该帧 AI bbox

共同决定。

### 9.2 单帧非简单段展开

对每个 `non_simple_single_frame`：

1. 其唯一帧的提交结果直接写入该帧最终结果

### 9.3 全视频结果

对同一 `session` 的全部标注段结果展开后，必须合成为：

- 一个覆盖该 `session` 全部帧的
- 完整逐帧 `p1-p7` 结果集合

不得存在缺帧或重复覆盖。

---

## 10. 兼容与迁移要求

### 10.1 主线切换

本方案要求彻底切到段模式主线。

因此：

- `issue_pool`
- `next_issue`
- `issue_detail`
- `submit_issue_*`
- `issue_reviews`
- `issue_keyframe_edits`

都不再是主线概念。

### 10.2 兼容要求

为避免一次性切换引起服务崩溃，迁移时允许短暂保留旧结构，但要求：

1. README 主入口必须切到段模式
2. 新文档不得继续以 issue 为主语义
3. 新服务默认只暴露段模式接口

---

## 11. 验收标准

### 11.1 分段正确性

对每个 `session`：

1. 全部帧必须被标注段完全覆盖
2. 任意两个标注段不得重叠
3. 每个标注段必须是：
   - 一个稳定段
   - 或一个单帧非简单帧

### 11.2 在线派单正确性

1. `next_segment` 必须返回合法段
2. 标注者无需接触分段细节
3. 同一段提交后，不应重复进入主分发队列

### 11.3 逐帧结果正确性

1. 每个 `session` 的每一帧最终都必须有完整 `p1-p7` 结果
2. `stable_segment` 的逐帧结果必须由段级身份映射自动展开
3. `non_simple_single_frame` 的结果必须来自该帧直接标注

---

## 12. 与数学定义的一致性核查

本节用于检查本需求文档是否符合：

- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)

### 核查 1：主对象一致

数学定义中的主对象是：

1. 简单帧
2. 稳定段
3. 非简单帧
4. 段级身份映射
5. 帧级结果

本需求文档对应为：

1. `simple frame`
2. `stable_segment`
3. `non_simple_single_frame`
4. `track_id -> p1-p7`
5. 逐帧 `p1-p7` 结果

二者一致。

### 核查 2：分解一致

数学定义要求：

- 全部帧被分解为稳定段与单帧非简单帧

本需求文档要求：

- 全部标注段必须完全覆盖 session 全部帧
- 每段只能是 `stable_segment` 或 `non_simple_single_frame`

二者一致。

### 核查 3：稳定段定义一致

数学定义中的稳定段要求：

1. 轨迹集合恒定
2. 每一帧都是简单帧
3. 该段是极大区间

本需求文档离线分段要求中逐条保留了这三点。

二者一致。

### 核查 4：段级身份映射一致

数学定义要求对每个稳定段存在：

```text
phi_S : K(S) -> P
```

本需求文档要求对每个稳定段提交：

```text
track_id -> p1-p7
```

这是同一对象的工程表示。

二者一致。

### 核查 5：逐帧结果一致

数学定义要求最终构造：

```text
R_sigma(t, p)
```

本需求文档要求最终得到：

- 每一帧
- 每个 `p1-p7`
- 完整结果

二者一致。

### 结论

本需求文档与数学定义文档在主对象、分解结构、段级身份映射和最终结果目标上是一致的。
