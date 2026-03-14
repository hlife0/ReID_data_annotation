# 需求文档 B：UI 双人标注与复标分发规范（实现对齐版）

## 1. 目标

本阶段负责：逐帧 UI 标注、任务分发、结果持久化与导出。

交付目标：

1. 每次请求随机分配一帧，优先 `annotation_count < 3`。
2. 支持 `P1(绿衣服)` 与 `P2(灰衣服)` 双槽位标注。
3. 每次提交追加写入并原子更新计数。
4. 达到 3 次后仍继续可分配、可追加。

---

## 2. 当前实现入口

- 标注服务：`./ui_review_server.py`（默认端口 `10086`）
- 管理面板：`./ui_admin_server.py`（默认端口 `10087`）

---

## 3. 输入范围与路径约束

主输入：

- `./data/required/<video_stem>/video/<video_stem>_retimed.mp4`
- `./data/required/<video_stem>/video/<video_stem>_frame_timestamps_retimed.csv`
- `./batch_<YYYYMMDD>_<vNN>/pseudo_labels/<video_stem>.auto.csv`

路径约束：

1. 以当前工作目录相对路径为主。
2. 数据盘通过 `./data` 软链接访问。
3. `./data/required/*` 仅只读，不写入。

---

## 4. 批次目录与产物

```text
./batch_<YYYYMMDD>_<vNN>/
├── ui_tasks/
│   ├── frame_pool.csv
│   ├── frame_annotation_counts.csv
│   ├── assignment_log.csv
│   └── ui_review.sqlite3
├── reviewed_raw/
│   └── <video_stem>.frame_records.jsonl
├── reviewed/
│   └── <video_stem>.reviewed.csv
└── logs/
    ├── run.log
    └── errors.log
```

说明：

1. SQLite 为主存储，CSV/JSONL 为可读导出与同步产物。
2. 记录按追加策略保存，不覆盖历史提交。

---

## 5. 本批次目标视频

固定目标：

- `20260211_171423`
- `20260211_171724`
- `20260211_172257`
- `20260211_172522`

---

## 6. 前端交互规范（实现）

### 6.1 页面结构

页面包含：

1. Header（标注员ID、跳过、提交并下一帧、语言切换）。
2. 状态条（视频、帧号、时间戳、当前累计标注次数）。
3. 画布区（帧图 + AI 框 + 用户框）。
4. 控制区（P1/P2 来源、AI 应用、手动画框、参数输入）。

### 6.2 双人物槽位

- `P1(绿衣服)`
- `P2(灰衣服)`

提交时必须同时给出 P1/P2 的有效状态（可为“存在框”或“不存在”）。

### 6.3 每个槽位支持 4 种方式

1. 应用 AI 框（按 `track_id` 按钮）。
2. 手动画框。
3. 参数输入框直接改 `bbox_x/y/w/h`。
4. 点击“`不存在`”（`source=absent`）。

### 6.4 画布交互与同步

1. 用户框支持拖动与八方向缩放。
2. 框操作实时回写参数输入框。
3. 参数输入实时反向更新画布框。
4. AI 应用/手绘/不存在状态都实时同步到来源与输入区。

### 6.5 渲染规则

1. AI 框：虚线、按 `track_id` 着色、显示 `id`。
2. 用户框：实线、可交互。
3. P1/P2 颜色固定且可区分。

---

## 6.6 标注历史与修订（新增）

为支持标注员自查与纠错，UI 提供左侧历史栏：

1. 仅展示当前 `annotator_id` 的提交记录，按 `submitted_at` 从近到远排序。
2. 点击条目进入编辑模式，加载对应帧与历史框。
3. 编辑后保存更新原记录，不改变数据库结构与计数逻辑。

---

## 7. 后端分发与持久化规范（实现）

### 7.1 分帧策略

`POST /api/next_frame`：

1. 优先随机选择 `annotation_count < 3` 帧。
2. 若全部 `>=3`，从最小计数组随机。
3. 永不因“达到 3 次”拒绝继续分配。

### 7.2 提交流程

`POST /api/submit`：

1. 校验 `video_stem + frame_index + timestamp_ms` 对齐任务池。
2. 校验 P1/P2：
- `source in {ai, manual_draw, manual_param}` 时，要求 `bbox_w>0` 且 `bbox_h>0`。
- `source=absent` 时，写入 `bbox_x=y=w=h=0`。
3. 在事务内：插入 annotation + 计数 `+1` + 分配下一帧。
4. 返回 `submitted` 与 `next_frame`。

### 7.3 持久化字段（核心）

- `annotation_id`
- `video_stem`
- `frame_index`
- `timestamp_ms`
- `annotator_id`
- `submitted_at`
- `p1_bbox_x/p1_bbox_y/p1_bbox_w/p1_bbox_h`
- `p1_source`（`ai/manual_draw/manual_param/absent`）
- `p1_ai_track_id`
- `p2_bbox_x/p2_bbox_y/p2_bbox_w/p2_bbox_h`
- `p2_source`（`ai/manual_draw/manual_param/absent`）
- `p2_ai_track_id`

### 7.4 自动推荐（D 阶段扩展）

若启用 D 阶段自动推荐：

1. `/api/next_frame` 的 `frame` 会额外返回 `recommendations` 字段（详见 `REQUIREMENTS_TRACK_RECOMMENDATION.md`）。
2. UI 在用户未操作前，可自动应用推荐的 `track_id` 到 P1/P2。
3. 统计表 `track_person_stats` 由提交时更新维护。

### 7.5 标注修订 API（新增）

新增接口：

1. `GET /api/my_annotations?annotator_id=...`  
   返回该标注员的历史记录（按提交时间倒序）。
2. `GET /api/annotation_detail?annotator_id=...&annotation_id=...`  
   返回标注记录与对应帧信息，用于进入编辑模式。
3. `POST /api/update_annotation`  
   更新已存在的 annotation 记录（仅允许同一 `annotator_id` 修改）。

---

## 8. 导出规范

- 实时追加：`reviewed_raw/*.frame_records.jsonl` 与 `reviewed/*.reviewed.csv`
- 批量重导出：`POST /api/export` 按 DB 重建上述文件

---

## 9. 验收标准（实现对齐）

1. UI 支持 P1/P2 双槽位与 4 种标注方式（含“不存在”）。
2. 框拖动/缩放与参数输入双向同步可用。
3. 提交成功后可自动进入下一帧。
4. 计数可统计，且可超过 3 次继续分配。
5. 产物路径、命名与字段完整可读。

---

## 10. 常用命令

### 10.1 初始化（可选，清空并重建）

```bash
.venv/bin/python ./ui_review_server.py --batch-dir ./batch_20260305_v03 --reset-storage --init-only
```

### 10.2 启动标注服务

```bash
.venv/bin/python ./ui_review_server.py --batch-dir ./batch_20260305_v03 --port 10086
```

### 10.3 启动管理面板

```bash
.venv/bin/python ./ui_admin_server.py --batch-dir ./batch_20260305_v03 --port 10087
```

### 10.4 性能缓存（推荐）

离线预热（先跑完缓存再开服务，避免标注时抢 CPU）：

```bash
.venv/bin/python ./ui_review_server.py \
  --batch-dir ./batch_20260305_v03 \
  --frame-cache-disk \
  --frame-cache-prewarm-only
```

启动服务（启用缓存）：

```bash
.venv/bin/python ./ui_review_server.py \
  --batch-dir ./batch_20260305_v03 \
  --port 10086 \
  --frame-cache-disk \
  --frame-cache-max 512
```
