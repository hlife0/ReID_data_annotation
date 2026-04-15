# 需求文档 B：UI Review / Issue-Mode 复核规范（当前实现版）

本文件描述当前 review/admin 栈的**实际实现**，重点是：

- 当前入口在哪里
- 当前 review UI 的工作单位是什么
- 当前支持哪些在线接口
- 当前的前后端能力边界是什么

如果你想看跨阶段主线，请先读：

- [REQUIREMENTS_TRAJECTORY_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_TRAJECTORY_REVIEW.md)

如果你想看 `issue` 算法和风险逻辑，请看：

- [ISSUE_TRAJECTORY_REVIEW_FLOW.md](/home/hrli/data_annotation/docs/ISSUE_TRAJECTORY_REVIEW_FLOW.md)

---

## 1. 当前目标

当前 review UI 的默认目标已经从：

- 逐帧双人复核

转成：

- issue-mode 问题点驱动复核
- 轨迹级工作单位
- 关键帧修正 + 智能传播

也就是说，当前系统的默认工作单位是：

- `issue`

而不是：

- 单帧

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
├── review_prep/
│   ├── <video_stem>.track_summary.json
│   ├── <video_stem>.risk_spans.json
│   ├── <video_stem>.issue_pool.csv
│   └── review_prep_summary.json
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

### 4.2 当前推荐的 issue-mode

当前更推荐用：

- `next_issue`
- `issue_detail`
- `issue_frame`
- `submit_issue_propagation`

在 issue-mode 下，用户默认流程是：

1. 领取一条 issue
2. 查看问题区间和相关轨迹
3. 记录关键帧
4. 用传播把修改扩成整段
5. 进入下一条 issue

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
3. issue 摘要条
   - severity
   - issue id
   - issue range
   - issue reasons
   - issue timeline
4. 左侧主画布
   - AI boxes
   - 用户当前槽位结果
5. 右侧问题列表
6. 右侧轨迹工作台
   - issue tracks
   - keyframe list
7. 右侧共享槽位编辑器

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

### 7.2 issue-mode 读取

- `POST /api/next_issue`
- `GET /api/issues`
- `GET /api/issue_detail`
- `GET /api/issue_frame`

### 7.3 issue-mode 提交

- `POST /api/submit_issue`
  - 只提当前帧，但当前实现会直接 resolve 整个 issue
- `POST /api/submit_issue_range`
  - 当前结果扩到整个 issue
- `POST /api/submit_issue_partial_range`
  - 当前结果扩到 issue 子区间
- `POST /api/submit_issue_interpolation`
  - 两关键帧之间线性插值
- `POST /api/submit_issue_propagation`
  - 多关键帧 + AI 轨迹跟随传播

### 7.4 历史与修订

- `GET /api/my_annotations`
- `GET /api/annotation_detail`
- `POST /api/update_annotation`

### 7.5 导出

- `POST /api/export`

---

## 8. 当前轨迹工作台能力

当前前端已经支持：

- issue list
- issue timeline
- issue 内上一帧 / 下一帧
- issue tracks 卡片
- keyframe list
- `Merge` 到当前槽位
- `切断轨迹`
- `重新出现`
- `遮挡`
- `出画`
- `智能传播整段`

但当前仍然属于：

- issue 内工作台

还不是：

- 全局跨 issue 轨迹编辑器

---

## 9. 当前传播能力

传播实现见：

- `./codes/review_propagation.py`

当前传播逻辑不是单纯线性插值，而是：

- 单关键帧时：
  - 尽量沿同一条 AI track 跟随传播
  - 传播关键帧相对 AI 框的修正量
- 双关键帧时：
  - 优先插值修正量
  - 必要时在起止两条 AI track 之间切换
- 对 `absent / occluded / outside`
  - 做状态复制，不做 bbox 插值

---

## 10. 当前 admin 面板能力

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

## 11. 当前系统的主要限制

当前已知限制包括：

1. `submit_issue` 单帧提交会过早 resolve 整个 issue
2. issue 分配还没有真正排他锁
3. `issue_id` 仍是排序编号，不是稳定主键
4. green 不等于 correctness，只等于“未命中当前启发式规则”
5. propagation 仍然依赖 AI 轨迹质量
6. `split / merge / reappear` 目前是 issue 内、槽位级首版

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

### 重算 review_prep

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/process_review_issue_prep.py \
  --batch-dir ./annotation/batch_20260413_v01
```

---

## 13. 相关文档

- [README.md](/home/hrli/data_annotation/docs/README.md)
- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
- [ISSUE_TRAJECTORY_REVIEW_FLOW.md](/home/hrli/data_annotation/docs/ISSUE_TRAJECTORY_REVIEW_FLOW.md)
- [REQUIREMENTS_TRAJECTORY_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_TRAJECTORY_REVIEW.md)
