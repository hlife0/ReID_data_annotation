# Data Annotation Pipeline

本项目包含三阶段流程 + D 阶段增强：

1. **预标注批处理**（A 阶段）
2. **UI 双人标注与复标分发**（B 阶段）
3. **双 IMU 静止/运动比值分析与人物对应辅助**（C 阶段）
4. **基于历史 Track ID 的自动推荐**（D 阶段）

---

## 当前状态（截至 2026-03-15）

- A 阶段：ByteTrack 预标注已跑通，最新批次 `batch_20260314_v05`，已生成 `pseudo_labels/*.auto.csv` 与带框视频 `pseudo_labels/videos/*.boxed.mp4`。
- B 阶段：UI 标注与后台服务可用；历史标注数据在 `batch_20260305_v03`，最新批次推荐使用 `batch_20260314_v05`。
- C 阶段：IMU 比值分析产物在 `batch_20260306_v02/imu_mapping/`，分析汇总见 `C_STAGE_IMU_MAPPING_ANALYSIS.md`。
- D 阶段：自动推荐已实现（`ui_review_server.py` + `ui_review_web/app.js`），文档见 `REQUIREMENTS_TRACK_RECOMMENDATION.md`。

---

## 1. 根目录脚本规范

根目录脚本统一前缀：

- `process_xxx.py`：批处理/主流程
- `test_xxx.py`：测试与辅助验证
- `ui_xxx.py`：UI 服务与后台服务

当前脚本：

- `process_prelabel_batch.py`
- `process_imu_mapping_batch.py`
- `test_render_pseudo_labels_video.py`
- `test_imu_mapping_outputs.py`
- `ui_review_server.py`
- `ui_admin_server.py`

---

## 2. 项目结构（核心）

```text
.
├── data -> /data/hrli/data_annotation/data
├── process_prelabel_batch.py
├── process_imu_mapping_batch.py
├── test_render_pseudo_labels_video.py
├── test_imu_mapping_outputs.py
├── ui_review_server.py
├── ui_admin_server.py
├── ui_review_web/
├── ui_admin_web/
├── REQUIREMENTS_PRELABEL.md
├── REQUIREMENTS_UI_REVIEW.md
├── REQUIREMENTS_IMU_MAPPING.md
└── batch_<YYYYMMDD>_<vNN>/
```

---

## 3. 阶段 A：预标注

### 3.1 作用

- 输入巡检（视频/时间戳/IMU）
- 生成任务清单 `manifests/annotation_tasks.csv`
- 输出预标注 `pseudo_labels/<video_stem>.auto.csv`

### 3.2 运行示例

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./process_prelabel_batch.py \
  --required-root ./data/required \
  --output-root . \
  --backend ultralytics \
  --device cuda:3 \
  --model yolo11x.pt \
  --tracker botsort.yaml
```

使用 ByteTrack（YOLOX）追踪：

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./process_prelabel_batch.py \
  --required-root ./data/required \
  --output-root . \
  --backend bytetrack \
  --bytetrack-root /data/hrli/ByteTrack \
  --bytetrack-exp-file exps/example/mot/yolox_x_mix_det.py \
  --bytetrack-ckpt pretrained/bytetrack_x_mot17.pth.tar \
  --bytetrack-device gpu \
  --bytetrack-gpu-id 2 \
  --bytetrack-fp16 \
  --bytetrack-fuse
```

只抽任务（A0/A1，不跑推理）：

```bash
.venv/bin/python ./process_prelabel_batch.py --only-task-extraction
```

---

## 4. 阶段 B：UI 标注与复标

### 4.1 启动标注服务

建议先做离线帧缓存（避免标注时抢 CPU）：

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./ui_review_server.py \
  --batch-dir ./batch_20260314_v05 \
  --frame-cache-disk \
  --frame-cache-prewarm-only
```

再启动服务（内存 + 磁盘缓存）：

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./ui_review_server.py \
  --batch-dir ./batch_20260314_v05 \
  --port 10086 \
  --frame-cache-disk \
  --frame-cache-max 512
```

访问：`http://localhost:10086`

### 4.2 启动后台面板（可选）

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./ui_admin_server.py --batch-dir ./batch_20260314_v05 --port 10087
```

访问：`http://localhost:10087`

### 4.3 UI 能力要点

- P1/P2 双人物槽位
- AI 框应用 / 手绘 / 参数编辑 / 不存在（`absent`）
- 拖拽移动与缩放，参数双向同步
- 提交后写库并自动分配下一帧
- 支持基于历史 `track_id` 的自动推荐（D 阶段）

---

## 5. 测试可视化脚本（可选）

将预标注框渲染到视频用于抽检：

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./test_render_pseudo_labels_video.py \
  --batch-dir ./batch_20260305_v03 \
  --video-stem 20260211_171423 \
  --bbox-format coco_xywh
```

输出：

- `batch_xxx/pseudo_labels/videos/<video_stem>.boxed.mp4`

---

## 6. 阶段 C：双 IMU 比值分析

阶段目标：

- 对每帧计算两个 IMU 的比值系数 `k_t`
- 计算 `m_t = max(k_t, 1/k_t)`
- 按 `m_t` 降序输出候选帧，优先回放最容易判断人物-IMU 对应的时刻

详细规范见：`REQUIREMENTS_IMU_MAPPING.md`

### 6.1 运行示例

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./process_imu_mapping_batch.py \
  --required-root ./data/required \
  --output-root . \
  --coef-type motion \
  --smoothing-window 5 \
  --max-align-gap-ms 250
```

指定已有批次目录输出：

```bash
.venv/bin/python ./process_imu_mapping_batch.py \
  --required-root ./data/required \
  --batch-dir ./batch_20260305_v03
```

输出文件：

- `batch_xxx/imu_mapping/<video_stem>.imu_ratio_rank.csv`
- `batch_xxx/imu_mapping/<video_stem>.imu_mapping_summary.json`
- `batch_xxx/logs/run.log`
- `batch_xxx/logs/errors.log`

### 6.2 C 阶段产物校验

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./test_imu_mapping_outputs.py --batch-dir ./batch_20260305_v03
```

---

## 7. 需求文档

- 预标注规范：`REQUIREMENTS_PRELABEL.md`
- UI 规范：`REQUIREMENTS_UI_REVIEW.md`
- IMU 映射规范：`REQUIREMENTS_IMU_MAPPING.md`
- 自动推荐规范：`REQUIREMENTS_TRACK_RECOMMENDATION.md`
- 入口说明：`REQUIREMENTS.md`
