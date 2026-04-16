# Stable Segment Prefill Design

## Goal

为当前段模式 review UI 增加一个“稳定段预填”能力：后端基于同一视频中的历史 `ai_track_id -> slot` 标注关系给出推荐，前端在稳定段打开时自动把对应 AI 框填进槽位，让标注员从“可修改的初稿”开始，而不是从空白开始。

## Scope

本次只做：

- `stable_segment` 的推荐生成
- `stable_segment` 的自动预填
- 复用现有的 `source = ai` 和 `ai_track_id`

本次不做：

- 自动提交
- non-simple 单帧自动预填
- 新数据库 schema
- 可视化推荐解释面板

## Current Constraints

当前后端 payload 已经预留：

- `frame.recommendations`

但实际始终为空。[ui_review_server.py](/home/hrli/data_annotation/codes/application/ui_review_server.py)

当前前端已经有：

- `applyAiToSlot(slot, tid)`

它能把某个 `ai_track_id` 对应的 bbox 填进某个槽位。[app.js](/home/hrli/data_annotation/codes/application/ui_review_web/app.js)

因此最小闭环是：

1. 后端真正返回 `recommendations`
2. 前端在稳定段载入时自动调用“应用 AI 框”

## Recommendation Source

推荐来源采用同视频历史多数票，不依赖 `track_person_stats` 表。

对当前代表帧中每个可见 `ai_track_id`：

1. 扫描同 `video_stem` 的历史 `annotations`
2. 解析 `slots_json`
3. 统计该 `ai_track_id` 被标到各个 `slot` 的次数
4. 若某个 `slot` 是唯一最高票，则生成候选推荐

计票时只统计：

- 有 `ai_track_id`
- `source` 不是 `absent / occluded / outside`

## Recommendation Resolution

推荐必须满足一对一约束：

- 一个 `slot` 不能同时推荐给两个 track
- 一个 track 也只能推荐到一个 `slot`

解决方式：

1. 对每个 track 先求唯一最高票 `slot`
2. 候选项按：
   - `vote_count` 降序
   - `confidence` 降序
   - `ai_track_id` 升序
3. 贪心分配，冲突项跳过

如果某个 track 的最高票并列，则直接不推荐。

## Payload Shape

后端返回：

```json
[
  {
    "slot": "p1",
    "ai_track_id": "11",
    "vote_count": 8,
    "confidence": 0.889,
    "reason": "history_majority"
  }
]
```

## Frontend Behavior

当 `stable_segment` 打开时：

1. 前端先加载 `frame.ai_boxes`
2. 再读取 `frame.recommendations`
3. 对每条推荐：
   - 找到对应 `ai_track_id` 的 bbox
   - 将该 bbox 填入对应 `slot`
   - 设 `source = "ai"`
   - 设 `aiTrackId = ai_track_id`

要求：

- 仅对 `stable_segment` 自动应用
- 不弹 toast
- 不覆盖已存在的用户编辑状态
- 若推荐无效或找不到 bbox，直接跳过

## Files

- Modify: `codes/application/ui_review_server.py`
- Modify: `codes/application/ui_review_web/app.js`
- Modify: `codes/test/test_segment_review_server.py`

## Testing

至少覆盖：

1. 有清晰历史多数票时，`next_segment` 返回推荐
2. 历史票数并列时，不返回推荐
3. 推荐不会把同一 `slot` 分配给多个 track
4. 前端逻辑至少保持语法通过

## Rollout

本次直接作为当前主分支行为启用，不新增 feature flag。
