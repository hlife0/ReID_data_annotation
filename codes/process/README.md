# Process Directory

本目录只放离线处理脚本与处理库，不放在线服务和测试。

如果你接手当前仓库，先记住一个原则：

- `process/` 负责“先离线生成什么”
- `application/` 负责“在线怎么用这些产物”
- `test/` 负责“怎么验证这些环节没乱套”

## 当前主线顺序

当前段模式主线必须按下面顺序理解和执行。

### 1. `process_prepare_capture_batch.py`（可选）

只在你手里拿到的是原始采集文件时才需要跑。

作用：

- 把原始视频和 IMU 数据整理成 `staging/required/`

如果你已经有标准化好的 `data/required/`，可以直接跳过这一步。

### 2. `process_prelabel_batch.py`

这是预标注入口。

作用：

- 从 `data/required/` 读取视频和时间戳
- 生成 `pseudo_labels/*.auto.csv`

这是段模式主线的前置条件，没有 `.auto.csv` 就不能继续后面的分段。

### 3. `process_segment_review_prep.py`

这是段模式离线准备入口。

作用：

- 读取 `pseudo_labels/*.auto.csv`
- 计算简单帧
- 先求 first-pass 的极大稳定段与单帧非简单帧
- 再在 first-pass 结果之上做 second-pass `repair_window` 合并
- 生成：
  - `segment_prep/*.segments.json`
  - `segment_prep/*.segment_frames.json`
  - `segment_prep/segment_prep_summary.json`

只要这一步没重算，review 服务看到的就是旧段结果。

### 4. `application/ui_review_server.py`

这是在线 review 服务入口。

作用：

- 读取 `segment_prep/`
- 按段分发
- 接收 `stable_segment`、`non_simple_single_frame` 与 `repair_window` 的标注
- 展开成逐帧 `p1-p7` 结果

### 4b. `process_human_stage_1_prep.py`

这是第一轮粗标的离线准备入口。

作用：

- 先复用现有 first-pass 语义，得到：
  - `stable_segment`
  - `non_simple_single_frame`
- 再在 first-pass 结果之上做 second-pass 的 `repair_window` 合并
- 生成：
  - `human_stage_1_prep/*.segments.json`
  - `human_stage_1_prep/*.segment_frames.json`
  - `human_stage_1_prep/human_stage_1_prep_summary.json`

这一步是 `human_stage_1` 在线服务的唯一上游输入，不应该跳过。

### 4c. `application/ui_human_stage_1_server.py`

这是第一轮粗标在线服务入口。

作用：

- 读取 `human_stage_1_prep/`
- 只返回单帧 coarse-labeling 任务
- 提供历史多数票推荐与自动预选
- 存储和修改：
  - `ai_match`
  - `absent`
  - `needs_manual`

它和 `ui_review_server.py` 是平行栈，不替代原 review 服务。

### 5. `application/ui_admin_server.py`

这是在线 admin 服务入口。

作用：

- 查看 batch 全局统计
- 查看段统计
- 查看 annotator 活跃度与提交结果

## 最常见的正确顺序

```text
process_prepare_capture_batch.py   (可选)
-> process_prelabel_batch.py
-> process_segment_review_prep.py
-> application/ui_review_server.py
-> application/ui_admin_server.py
```

### 第一轮粗标闭环

```text
process_prepare_capture_batch.py   (可选)
-> process_prelabel_batch.py
-> process_human_stage_1_prep.py
-> application/ui_human_stage_1_server.py
```

## 当前优化重点

当前仓库仍保留 review 栈与 admin 栈，但正在持续优化的第一轮人工主线已经转到：

```text
process_prelabel_batch.py
-> process_human_stage_1_prep.py
-> application/ui_human_stage_1_server.py
```

## 其他脚本

- `prepare_capture_lib.py`
  - `process_prepare_capture_batch.py` 的辅助库
- `segment_prep_common.py`
  - `process_segment_review_prep.py` 的公共读取与几何工具
- `process_imu_mapping_batch.py`
  - IMU 映射辅助脚本

旧的一次性标注下游脚本已归档到：

- `codes/archive/legacy_one_shot_annotation/process/`

## 不要乱套的规则

1. 不要先开 review 服务再忘了重算 `segment_prep/`
2. 不要先开 `human_stage_1` 服务再忘了重算 `human_stage_1_prep/`
3. `human_stage_1_prep.py` 必须建立在 first-pass 结果语义之上，不能跳过 first-pass 直接并 `repair_window`
4. 不要把 `archive/` 里的旧脚本当成活跃入口
