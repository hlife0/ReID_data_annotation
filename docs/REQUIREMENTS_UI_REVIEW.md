# 需求文档 B：UI Review / 段模式复核规范（当前实现版）

本文件描述当前 review/admin 栈的**实际实现**，重点是：

- 当前入口在哪里
- 当前 review UI 的工作单位是什么
- 当前支持哪些在线接口
- 当前的前后端能力边界是什么

如果你想看当前主线，请先读：

- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)

如果你想看段模式的数学基础，请看：

- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)

---

## 1. 当前目标

当前 review UI 的默认目标已经从“逐帧双人复核”转成：

- 段模式复核
- 稳定段代表帧标注
- 单帧非简单帧标注

也就是说，当前系统的默认工作单位是：

- `segment`

---

## 2. 当前实现入口

- review 服务：
  - `./codes/ui_review_server.py`
  - 默认端口 `10086`
- admin 服务：
  - `./codes/ui_admin_server.py`
  - 默认端口 `10087`
- review 前端：
  - `./codes/ui_review_web/`
- admin 前端：
  - `./codes/ui_admin_web/`

---

## 3. 当前依赖的批次产物

```text
./annotation/batch_<...>/
├── manifests/annotation_tasks.csv
├── pseudo_labels/<video_stem>.auto.csv
├── segment_prep/
│   ├── <video_stem>.segments.json
│   ├── <video_stem>.segment_frames.json
│   └── segment_prep_summary.json
├── ui_tasks/
│   ├── frame_pool.csv
│   ├── frame_annotation_counts.csv
│   ├── assignment_log.csv
│   └── ui_review.sqlite3
├── reviewed_raw/
├── reviewed/
└── logs/
```

当前正式批次：

- `./annotation/batch_20260413_v01`

---

## 4. 当前 review UI 的工作模型

### 4.1 已保留的 frame-mode

系统仍然保留：

- `next_frame`
- `submit`

所以旧的逐帧模式没有被删除。

### 4.2 当前推荐的 segment-mode

当前更推荐用：

- `next_segment`
- `segment_detail`
- `submit_segment`

在段模式下，用户默认流程是：

1. 领取下一段
2. 查看该段代表帧
3. 直接标这张图
4. 提交并进入下一段

---

## 5. 当前页面结构

当前 review 页面主要分为：

1. 顶部工具栏
   - annotator id
   - `下一问题点`
   - `跳过当前帧`
   - `提交并下一问题点`
2. 状态条
   - video
   - frame
   - timestamp
   - annotation count
3. 段摘要条
   - segment type
   - segment id
   - segment range
4. 左侧主画布
   - AI boxes
   - 用户当前槽位结果
5. 右侧共享槽位编辑器

---

## 6. 当前槽位模型

当前已不再写死 `P1/P2`，而是动态槽位：

- `p1` 到 `p7`

前端和后端都按动态 `slot_names` 工作。

每个槽位当前允许的 `source`：

- `ai`
- `manual_draw`
- `manual_param`
- `absent`
- `occluded`
- `outside`

---

## 7. 当前后端接口

### 7.1 frame-mode

- `POST /api/next_frame`
- `POST /api/submit`

### 7.2 segment-mode 读取

- `POST /api/next_segment`
- `GET /api/segment_detail`

### 7.3 segment-mode 提交

- `POST /api/submit_segment`

### 7.4 历史与修订

- `GET /api/my_annotations`
- `GET /api/annotation_detail`
- `POST /api/update_annotation`

### 7.5 导出

- `POST /api/export`

---

## 8. 当前段模式能力

当前主线能力是：

- 离线切分稳定段与单帧非简单帧
- 代表帧选择
- 段级派单
- 稳定段按 `track_id -> p1-p7` 展开为逐帧结果
- 单帧非简单帧直接写入逐帧结果

---

## 9. 当前 admin 面板能力

当前 admin 页面已能看：

- total frames
- annotated frames
- total annotations
- annotator counts
- red / yellow / green span counts
- `auto_pass_span_count`
- `qa_sample_span_count`
- annotator overview
- recent annotations
- frame detail query

所以 admin 现在不只是“谁标了多少帧”，也是：

- 风险分层监控入口

---

## 10. 当前系统的主要限制

当前已知限制包括：

1. 段模式实现仍处于持续收口期
2. 稳定段当前仍只使用 `low_score + overlap + track-set constancy`
3. 稳定段代表帧上的手工框到 AI track 的自动匹配目前只做唯一匹配

---

## 12. 当前推荐命令

### 启动 review

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/ui_review_server.py \
  --batch-dir ./annotation/batch_20260413_v01 \
  --host 127.0.0.1 \
  --port 10086
```

### 启动 admin

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/ui_admin_server.py \
  --batch-dir ./annotation/batch_20260413_v01 \
  --host 127.0.0.1 \
  --port 10087
```

### 重算 segment_prep

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/process_segment_review_prep.py \
  --batch-dir ./annotation/batch_20260413_v01
```

---

## 13. 相关文档

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
