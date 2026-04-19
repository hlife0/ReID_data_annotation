# Process Directory

本目录只放离线处理脚本与处理库，不放在线服务和测试。

如果你接手当前仓库，先记住一个原则：

- `process/` 负责“先离线生成什么”
- `application/` 负责“在线怎么用这些产物”
- `test/` 负责“怎么验证这些环节没乱套”

## 当前主线顺序

当前 active 仓库按 `Step 0` 到 `Step 5` 组织。

其中：

- `Step 0 -> Step 3` 是当前真正已经跑通的主线
- `Step 4` 是显式保留的主线缺口
- `Step 5` 是第二阶段资源与基础设施所在位置，但按主线口径应视为后续阶段

### Step 0：`step0_preprocess/`（可选）

只在你手里拿到的是原始采集文件时才需要跑。

作用：

- 把原始视频和 IMU 数据整理成 `staging/required/`

如果你已经有标准化好的 `data/required/`，可以直接跳过这一步。

### Step 1：`step1_prelabel/`

这是预标注入口。

作用：

- 从 `data/required/` 读取视频和时间戳
- 生成 `pseudo_labels/*.auto.csv`

这是段模式主线的前置条件，没有 `.auto.csv` 就不能继续后面的分段。

### Step 2：`step2_stage1_prep/`

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

### Step 3：`application/step3_human_stage_1/`

这是第一轮粗标在线服务入口。

作用：

- 读取 `human_stage_1_prep/`
- 只返回单帧 coarse-labeling 任务
- 提供历史多数票推荐与自动预选
- 存储和修改：
  - `ai_match`
  - `absent`
  - `needs_manual`

这是当前真正运行中的第一阶段人工主线。

### Step 4：`step4_stage2_task_pool/`

本目录负责表达：

- 读取 `Step 3` 的粗标结果
- 判断哪些帧或段需要升级到 `Step 5`
- 生成第二阶段任务池

当前 active 仓库里，这一步还没有独立的生产实现，但目录和 README 已经显式保留。

### Step 5：`step5_stage2_review_prep/` + `application/step5_stage2_review/`

这是第二阶段精细化标注 / review 资源所在位置。

当前保留的内容包括：

- `step5_stage2_review_prep/process_segment_review_prep.py`
- `application/step5_stage2_review/ui_review_server.py`
- `application/step5_stage2_review/web/`

它们代表第二阶段的基础设施与现有实现资源，但按当前仓库主线口径，这一步应视为后续阶段，而不是已完成主线。

### Support：`application/support/ui_admin_server.py`

这是在线 admin 服务入口。

作用：

- 查看 batch 全局统计
- 查看段统计
- 查看 annotator 活跃度与提交结果

## 最常见的正确顺序

```text
step0_preprocess/process_prepare_capture_batch.py   (可选)
-> step1_prelabel/process_prelabel_batch.py
-> step2_stage1_prep/process_human_stage_1_prep.py
-> application/step3_human_stage_1/ui_human_stage_1_server.py
```

### 第一轮粗标闭环

```text
step0_preprocess/process_prepare_capture_batch.py   (可选)
-> step1_prelabel/process_prelabel_batch.py
-> step2_stage1_prep/process_human_stage_1_prep.py
-> application/step3_human_stage_1/ui_human_stage_1_server.py
```

## 当前优化重点

当前仓库仍保留 Step 5 资源与 admin 栈，但当前真正持续推进的主线已经转到：

```text
step1_prelabel/process_prelabel_batch.py
-> step2_stage1_prep/process_human_stage_1_prep.py
-> application/step3_human_stage_1/ui_human_stage_1_server.py
```

## 其他脚本

- `step0_preprocess/prepare_capture_lib.py`
  - `step0_preprocess/process_prepare_capture_batch.py` 的辅助库
- `shared/segment_prep_common.py`
  - `step5_stage2_review_prep/process_segment_review_prep.py` 与 `step2_stage1_prep/process_human_stage_1_prep.py` 的公共读取与几何工具
- `devtools/analyze_human_stage_1_segmentation_grid.py`
  - 开发过程中的参数扫描与统计分析工具，不属于主线 step

旧的一次性标注下游脚本已归档到：

- `codes/archive/legacy_one_shot_annotation/process/`

旧的辅助支线脚本已归档到：

- `codes/archive/legacy_auxiliary/process/`

## 不要乱套的规则

1. 不要先开 review 服务再忘了重算 `segment_prep/`
2. 不要先开 `human_stage_1` 服务再忘了重算 `human_stage_1_prep/`
3. `human_stage_1_prep.py` 必须建立在 first-pass 结果语义之上，不能跳过 first-pass 直接并 `repair_window`
4. 不要把 `archive/` 里的旧脚本当成活跃入口
