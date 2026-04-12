# 需求文档 A：预标注批处理规范（实现对齐版）

## 1. 目标

本阶段只负责：输入巡检、任务清单生成、AI 预标注输出。

交付目标：

1. 为每个目标视频生成 `pseudo_labels/<video_stem>.auto.csv`。
2. 记录完整字段（含 `timestamp_ms`、`track_id`）。
3. 所有产物写入同一批次目录，供 UI 阶段直接接力。

---

## 2. 当前实现入口

主脚本：`./codex/process_prelabel_batch.py`

可选测试脚本（仅用于可视化核查，不是主流程必需）：

- `./codex/test_render_pseudo_labels_video.py`

---

## 3. 输入范围与路径约束

路径规则：

1. 仅使用当前工作目录下的相对路径（`./...`）。
2. 访问数据盘时，通过软链接 `./data/...`。
3. 禁止把 `/data/...` 之类绝对路径作为业务输入输出约定。

主输入：

- `./data/required/<video_stem>/video/<video_stem>_retimed.mp4`
- `./data/required/<video_stem>/video/<video_stem>_frame_timestamps_retimed.csv`
- `./data/required/<video_stem>/imu/*.csv`（仅用于巡检，不参与预标注；允许 1 到 N 个）

---

## 4. 批次目录与产物

批次目录命名：

- `annotation/batch_<YYYYMMDD>_<vNN>`，例如 `annotation/batch_20260305_v03`

主流程必需产物：

```text
./annotation/batch_<YYYYMMDD>_<vNN>/
├── manifests/
│   └── annotation_tasks.csv
├── pseudo_labels/
│   └── <video_stem>.auto.csv
└── logs/
    ├── run.log
    └── errors.log
```

可选测试产物（仅运行测试渲染脚本时出现）：

```text
./annotation/batch_<YYYYMMDD>_<vNN>/
└── pseudo_labels/
    └── videos/
        └── <video_stem>.boxed.mp4
```

---

## 5. 本批次目标视频

当前实现默认扫描 `required-root` 下所有包含 `video/` 子目录的 `video_stem` 目录。

若 `required-root` 下未发现任何目录，则回退到历史固定目标集。

---

## 6. 输出字段规范（`*.auto.csv`）

字段必须完整且列集合严格一致：

- `video_stem`
- `frame_index`
- `timestamp_ms`
- `track_id`
- `bbox_x`
- `bbox_y`
- `bbox_w`
- `bbox_h`
- `score`
- `class_name`（固定 `person`）
- `imu_id`（固定 `unknown`）
- `source`（固定 `auto`）
- `review_state`（固定 `pending`）

规则：

1. `timestamp_ms` 必须来自 retimed 时间戳 CSV。
2. `bbox_*` 使用 COCO `xywh`（左上角 + 宽高）。
3. `bbox_w > 0` 且 `bbox_h > 0`。

---

## 7. 执行步骤（实现）

### Step A0：输入巡检

- 检查视频、时间戳 CSV、IMU 数量（期望至少 1）。
- 不满足条件的视频标记为 `blocked`（写日志）。

### Step A1：任务清单生成

输出：`manifests/annotation_tasks.csv`

字段：

- `video_stem`
- `video_path`
- `timestamp_path`
- `imu_paths`
- `status`（`todo` / `blocked`）
- `priority`

### Step A2：预标注推理

仅对 `status=todo` 执行。

当前实现支持：

- `--backend ultralytics`（默认）
- `--backend hog`（兜底）
- `--backend bytetrack`（ByteTrack/YOLOX 追踪，需 ByteTrack 仓库与 venv）

补充模式：

- `--only-task-extraction`：只跑 A0/A1，不跑 A2。

---

## 8. 验收标准

1. 任务清单存在且包含全部目标视频。
2. 对每个 `todo` 视频有对应 `.auto.csv`。
3. 输出列完整且无非法 `bbox_w/bbox_h`。
4. 日志可读：`logs/run.log`、`logs/errors.log`。

---

## 9. 常用命令

### 9.1 主流程（默认 ultralytics）

```bash
.venv/bin/python ./codex/process_prelabel_batch.py \
  --required-root ./data/required \
  --output-root ./annotation \
  --backend ultralytics \
  --device cuda:3 \
  --model yolo11x.pt \
  --tracker botsort.yaml
```

### 9.2 只做任务抽取（A0/A1）

```bash
.venv/bin/python ./codex/process_prelabel_batch.py --only-task-extraction
```

### 9.3 可选：单视频渲染检测框（测试）

```bash
.venv/bin/python ./codex/test_render_pseudo_labels_video.py \
  --batch-dir ./annotation/batch_20260305_v03 \
  --video-stem 20260211_171423 \
  --bbox-format coco_xywh
```
