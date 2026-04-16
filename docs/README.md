# Data Annotation Pipeline

本仓库当前已经不只是“逐帧双人框标注工具”，而是一套围绕 **AI 预标注 + 段模式复核 + 逐帧 `p1-p7` 结果生成** 的标注流程。

当前统一代码目录是：

- `./codes/`
- 当前代码分区说明见：
  - [codes/README.md](/home/hrli/data_annotation/codes/README.md)

当前正式批次是：

- `./annotation/batch_20260413_v01`
- 当前批次的段级压缩统计报告见：
  - [BATCH_20260413_V01_SEGMENT_SUMMARY.md](/home/hrli/data_annotation/docs/BATCH_20260413_V01_SEGMENT_SUMMARY.md)

---

## 当前状态

截至当前版本，主线能力如下：

1. A 阶段：预标注批处理可从 `data/required/` 生成 `pseudo_labels/*.auto.csv`
2. B/Y 阶段：review 服务已开始切到段模式
3. 离线主线已新增：
   - `codes/process/process_segment_review_prep.py`
   - `segment_prep/*.segments.json`
   - `segment_prep/*.segment_frames.json`
   - `segment_prep/segment_prep_summary.json`
   - `codes/process/README.md`
4. 段模式主语义已明确为：
   - `stable_segment`
   - `non_simple_single_frame`
5. 数学定义文档与段模式需求文档已建立

当前主线规范见：

- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)

历史轨迹复核文档已归档到：

- [archive/legacy_segment_mode/README.md](/home/hrli/data_annotation/docs/archive/legacy_segment_mode/README.md)

---

## 核心目录

```text
.
├── codes/
│   ├── application/
│   ├── process/
│   ├── test/
│   └── archive/
├── docs/
├── data/
├── annotation/
│   └── batch_<YYYYMMDD>_<vNN>/
└── staging/
```

---

## 先看哪几份文档

如果你是第一次接手，推荐顺序：

1. [README.md](/home/hrli/data_annotation/docs/README.md)
2. [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
3. [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
4. [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
5. [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
6. [REQUIREMENTS_PRELABEL.md](/home/hrli/data_annotation/docs/REQUIREMENTS_PRELABEL.md)
7. [codes/README.md](/home/hrli/data_annotation/codes/README.md)
8. [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)

如果你只关心标注界面怎么用：

1. [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
2. [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)

---

## 当前推荐流程

```mermaid
flowchart LR
    A[data/required] --> B[process/process_prelabel_batch.py]
    B --> C[batch/pseudo_labels/*.auto.csv]
    C --> D[process/process_segment_review_prep.py]
    D --> E[batch/segment_prep]
    E --> F[application/ui_review_server.py]
    F --> G[segment-mode review UI]
    G --> H[reviewed_raw/*.jsonl]
    G --> I[reviewed/*.csv]
```

### 这条主线里每一步的角色

- `process/process_prelabel_batch.py`
  - 负责 A 阶段 AI 预标注
- `process/process_segment_review_prep.py`
  - 负责离线生成：
    - `segments.json`
    - `segment_frames.json`
    - `segment_prep_summary.json`
- `application/ui_review_server.py`
  - 负责在线段级派单、代表帧加载、提交与逐帧展开
- `application/ui_admin_server.py`
  - 负责看全局统计与 annotator 活跃度
- `process/README.md`
  - 负责说明整个处理流程先后顺序

---

## 常用命令

### 1. 运行离线 segment prep

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/process/process_segment_review_prep.py \
  --batch-dir ./annotation/batch_20260413_v01
```

### 2. 启动 review 服务

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/application/ui_review_server.py \
  --batch-dir ./annotation/batch_20260413_v01 \
  --host 127.0.0.1 \
  --port 10086
```

访问：

- `http://127.0.0.1:10086`

### 3. 启动 admin 服务

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python codes/application/ui_admin_server.py \
  --batch-dir ./annotation/batch_20260413_v01 \
  --host 127.0.0.1 \
  --port 10087
```

访问：

- `http://127.0.0.1:10087`

### 4. 跑当前核心测试

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python -m unittest discover -s codes/test
```

### 5. JS 语法检查

```bash
cd /home/hrli/data_annotation
node --check codes/application/ui_review_web/app.js
node --check codes/application/ui_admin_web/app.js
```

---

## review UI 该怎么理解

当前 review UI 的默认心智模型不是：

- “给我下一段的一张代表图”

而是：

- “给我下一段待标注的小段”

也就是说，默认工作单位已经从：

- 逐帧随机图片

变成：

- `stable_segment`
- `non_simple_single_frame`

推荐用法是：

1. 点 `下一段`
2. 在代表图上直接标图片
3. 提交并进入下一段

详见：

- [ANNOTATOR_INTRO.md](/home/hrli/data_annotation/docs/ANNOTATOR_INTRO.md)
- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)

---

## 现阶段最重要的现实限制

当前系统已经可用，但还不是终态。最值得知道的限制有：

1. 段模式已建立，但主服务仍处于持续收口期
2. 稳定段定义当前只吸收了 `low_score + overlap + track-set constancy`
3. `bbox_jump` 等旧风险信号还没有进入新的数学定义主线
4. 文档主线已切到段模式，但 archive 中仍保留旧阶段上下文

---

## 其他文档

- [REQUIREMENTS_SEGMENT_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_SEGMENT_REVIEW.md)
- [STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md](/home/hrli/data_annotation/docs/STABLE_SEGMENT_MATHEMATICAL_DEFINITIONS.md)
- [codes/README.md](/home/hrli/data_annotation/codes/README.md)
- [codes/process/README.md](/home/hrli/data_annotation/codes/process/README.md)
- [REQUIREMENTS_PRELABEL.md](/home/hrli/data_annotation/docs/REQUIREMENTS_PRELABEL.md)
- [REQUIREMENTS_UI_REVIEW.md](/home/hrli/data_annotation/docs/REQUIREMENTS_UI_REVIEW.md)
- [REQUIREMENTS_IMU_MAPPING.md](/home/hrli/data_annotation/docs/REQUIREMENTS_IMU_MAPPING.md)
- [REQUIREMENTS_ANNOTATION_ANALYSIS.md](/home/hrli/data_annotation/docs/REQUIREMENTS_ANNOTATION_ANALYSIS.md)
- [REQUIREMENTS_REVIEW_ANNOTATION_RESULTS.md](/home/hrli/data_annotation/docs/REQUIREMENTS_REVIEW_ANNOTATION_RESULTS.md)
- [REQUIREMENTS_FINAL_ANNOTATION.md](/home/hrli/data_annotation/docs/REQUIREMENTS_FINAL_ANNOTATION.md)
- [REQUIREMENTS.md](/home/hrli/data_annotation/docs/REQUIREMENTS.md)
- [BATCH_20260413_V01_SEGMENT_SUMMARY.md](/home/hrli/data_annotation/docs/BATCH_20260413_V01_SEGMENT_SUMMARY.md)
