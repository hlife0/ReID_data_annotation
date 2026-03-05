# Data Annotation Pipeline

本项目包含三阶段流程：

1. **预标注批处理**（A 阶段）
2. **UI 双人标注与复标分发**（B 阶段）
3. **双 IMU 静止/运动比值分析与人物对应辅助**（C 阶段）

---

## 1. 根目录脚本规范

根目录脚本统一前缀：

- `process_xxx.py`：批处理/主流程
- `test_xxx.py`：测试与辅助验证
- `ui_xxx.py`：UI 服务与后台服务

当前脚本：

- `process_prelabel_batch.py`
- `test_render_pseudo_labels_video.py`
- `ui_review_server.py`
- `ui_admin_server.py`

---

## 2. 项目结构（核心）

```text
.
├── data -> /data/hrli/data_annotation/data
├── process_prelabel_batch.py
├── test_render_pseudo_labels_video.py
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

只抽任务（A0/A1，不跑推理）：

```bash
.venv/bin/python ./process_prelabel_batch.py --only-task-extraction
```

---

## 4. 阶段 B：UI 标注与复标

### 4.1 启动标注服务

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./ui_review_server.py --batch-dir ./batch_20260305_v03 --port 10086
```

访问：`http://localhost:10086`

### 4.2 启动后台面板（可选）

```bash
cd /home/hrli/data_annotation
.venv/bin/python ./ui_admin_server.py --batch-dir ./batch_20260305_v03 --port 10087
```

访问：`http://localhost:10087`

### 4.3 UI 能力要点

- P1/P2 双人物槽位
- AI 框应用 / 手绘 / 参数编辑 / 不存在（`absent`）
- 拖拽移动与缩放，参数双向同步
- 提交后写库并自动分配下一帧

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

---

## 7. 需求文档

- 预标注规范：`REQUIREMENTS_PRELABEL.md`
- UI 规范：`REQUIREMENTS_UI_REVIEW.md`
- IMU 映射规范：`REQUIREMENTS_IMU_MAPPING.md`
- 入口说明：`REQUIREMENTS.md`
