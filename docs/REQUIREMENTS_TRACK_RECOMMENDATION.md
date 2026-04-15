# 需求文档 D：基于历史 AI Track ID 的自动推荐（实现对齐版）

## 1. 目标

在现有 UI 标注流程中引入“硬规则自动推荐”，减少人工重复判断成本。  
当标注员领取新帧时，系统根据“同一视频内 AI track_id 的历史标注统计”自动推荐 P1/P2 的对应关系；标注员可直接确认并进入下一帧。

---

## 实现状态（2026-03-15）

- 已落地于 `codes/ui_review_server.py` 与 `codes/ui_review_web/app.js`。
- 数据表 `track_person_stats` 已创建并在提交时更新。
- `/api/next_frame` 返回 `frame.recommendations`，UI 会在用户未操作前自动应用。

---

## 2. 核心思想（强制）

对每个视频，维护一个“AI track_id → 人物(P1/P2)”的历史统计表。  
当标注员在任意帧对某个 AI track_id 进行“非 absent 标注”时，系统记一次“该 track_id 被标为 P1 或 P2”。

当标注员领取新帧时：

1. 系统遍历当前帧内所有 AI 自动框（所有 track_id）。
2. 若某个 track_id 在该视频历史统计表中出现过，则选取“累计被标为次数最多的人”作为推荐结果。
3. 自动填入推荐结果到 UI（等效为自动点击对应 AI 框按钮），其它 UI 逻辑保持不变。

---

## 3. 适用范围

- 仅对同一 `video_stem` 内生效。
- 仅使用 AI 自动框（track_id），不适用于手绘框“新框”的强制推荐。
- 仅在 `source != absent` 的提交中更新统计。
- 不跨视频共享统计。

---

## 4. 新增/更新数据结构

### 4.1 统计表（DB）
新增表：`track_person_stats`

字段：

- `video_stem` (TEXT, PK 部分)
- `ai_track_id` (TEXT, PK 部分)
- `p1_count` (INTEGER, default 0)
- `p2_count` (INTEGER, default 0)
- `last_updated_at` (TEXT)

主键：`(video_stem, ai_track_id)`

### 4.2 可选缓存/导出（非强制）
可选导出 CSV：  
`annotation/batch_xxx/ui_tasks/track_person_stats.csv`

字段：

- `video_stem`
- `ai_track_id`
- `p1_count`
- `p2_count`
- `last_updated_at`

---

## 5. 业务规则（强制）

### 5.1 统计更新规则（提交时）

当 `POST /api/submit` 成功提交后：

- 对 P1：
  - 若 `p1_source != absent` 且 `p1_ai_track_id` 非空，则：
    - 对 `(video_stem, ai_track_id)` 的 `p1_count += 1`
- 对 P2：
  - 若 `p2_source != absent` 且 `p2_ai_track_id` 非空，则：
    - 对 `(video_stem, ai_track_id)` 的 `p2_count += 1`

仅记录“基于 AI track_id 的标注”。  
对手绘框（无 ai_track_id）的标注不计入统计。

### 5.2 推荐生成规则（领取新帧时）

当 `POST /api/next_frame` 返回新帧时：

对于该帧的每个 AI track_id：

1. 查询 `(video_stem, ai_track_id)` 统计记录。
2. 若存在统计记录：
   - 若 `p1_count > p2_count` → 推荐 `P1`
   - 若 `p2_count > p1_count` → 推荐 `P2`
   - 若相等 → 不推荐（保持空）
3. 推荐结果必须只针对该 track_id 生效。

### 5.3 UI 自动填充规则

当后端返回推荐结果：

- UI 自动将推荐的 `track_id` 选中为对应 P1 或 P2（等效于用户点击该 track_id 的 AI 框按钮）。
- 若 P1/P2 已存在用户手动修改，则不强制覆盖（优先级：用户操作 > 自动推荐）。
- 推荐仅作为默认建议，不应改变交互方式。

---

## 6. API 改动（强制）

### 6.1 `/api/next_frame` 返回结构新增字段

在 `frame` payload 中新增：

```json
"recommendations": [
  {
    "track_id": "12",
    "recommended_person": "p1"
  }
]
```

说明：

- 仅包含有明确推荐的 track_id。
- 若无推荐则为空数组。

---

## 7. UI 改动（强制）

### 7.1 自动应用推荐

当 UI 收到 `frame.recommendations`：

- 逐条尝试应用推荐（以 `track_id` 匹配当前帧 AI 框）。
- 若匹配成功且对应 slot 未被用户操作过，则自动应用。
- 应用时同步显示来源为 `ai`，并自动选中推荐 track_id。

### 7.2 可视提示（可选）

可在 UI 上轻量提示（不强制）：

- 推荐成功时提示：`已根据历史推荐 P1/P2`
- 可在提示条或 toast 中展示。

---

## 8. 一致性要求

- 推荐逻辑必须严格基于同一 `video_stem` 的统计记录。
- 推荐结果必须可复现（相同统计数据 → 相同推荐）。
- 统计更新必须在提交事务内完成，确保一致性。

---

## 9. 验收标准（强制）

1. 提交标注后，DB 中 `track_person_stats` 计数正确递增。
2. 领取新帧时，若某 track_id 有历史记录，UI 自动选中推荐人。
3. 若 P1/P2 已被用户修改，则不会被自动覆盖。
4. 无历史统计记录时不推荐。
5. 不影响现有 UI 交互和提交逻辑。

---

## 10. 失败处理规则

- 若推荐查询失败，不影响正常分帧，`recommendations` 返回空数组。
- 若统计表缺失，系统应自动创建或降级为“不推荐”。

---

## 11. 完成定义（DoD）

当且仅当以下条件全部满足：

1. DB 中新增 `track_person_stats` 表并在提交时正确更新。
2. `/api/next_frame` 返回推荐结果，UI 自动应用推荐。
3. 推荐逻辑仅基于同视频历史统计，且不会覆盖用户手动修改。
4. A/B 阶段其它功能行为保持不变。
