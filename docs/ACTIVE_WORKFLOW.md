# Active Workflow

本文件描述当前 **active 仓库** 真正支持的主线流程。

当前主线按 `Step 0` 到 `Step 5` 组织：

1. `Step 0` 原始采集整理（可选）
2. `Step 1` AI 预标注
3. `Step 2` 第一阶段任务生成
4. `Step 3` 第一阶段人工粗标
5. `Step 4` 第二阶段任务池生成
6. `Step 5` 第二阶段精细化标注 / review

其中当前真正已经跑通的主线重点是：

- `Step 0 -> Step 3`

其中 `Step 3` 的 `human_stage_1` 当前已经作为最终完成版定稿。

---

## Step 0：原始输入整理

目录：

- [step0_preprocess/](/home/hrli/data_annotation/codes/process/step0_preprocess)

职责：

- 把原始采集资产整理成标准输入

核心入口：

- [process_prepare_capture_batch.py](/home/hrli/data_annotation/codes/process/step0_preprocess/process_prepare_capture_batch.py)

---

## Step 1：AI 预标注

目录：

- [step1_prelabel/](/home/hrli/data_annotation/codes/process/step1_prelabel)

职责：

- 从标准化视频生成 `pseudo_labels/*.auto.csv`

核心入口：

- [process_prelabel_batch.py](/home/hrli/data_annotation/codes/process/step1_prelabel/process_prelabel_batch.py)

---

## Step 2：第一阶段任务生成

目录：

- [step2_stage1_prep/](/home/hrli/data_annotation/codes/process/step2_stage1_prep)

职责：

- 基于 AI 预标注生成 `human_stage_1_prep/`

核心入口：

- [process_human_stage_1_prep.py](/home/hrli/data_annotation/codes/process/step2_stage1_prep/process_human_stage_1_prep.py)

---

## Step 3：第一阶段人工粗标

目录：

- [step3_human_stage_1/](/home/hrli/data_annotation/codes/application/step3_human_stage_1)

职责：

- 让标注员对 `human_stage_1_prep/` 工作单元做 coarse decision

允许的决策：

- `ai_match`
- `absent`
- `needs_manual`

核心入口：

- [ui_human_stage_1_server.py](/home/hrli/data_annotation/codes/application/step3_human_stage_1/ui_human_stage_1_server.py)

当前完成版包含：

- 标准页面 `/`
- 快捷页面 `/fast`
- 专属后台 `/admin`
- 全局共享双轮队列
- annotator 进度与强提示交互

---

## Step 4：第二阶段任务池生成

目录：

- [step4_stage2_task_pool/](/home/hrli/data_annotation/codes/process/step4_stage2_task_pool)

职责：

- 读取 `Step 3` 的粗标结果
- 判断哪些帧或段需要升级到 `Step 5`
- 生成第二阶段任务池

说明：

- 当前 active 仓库里，这一步仍是显式保留的缺口
- 已有目录与说明，但没有独立生产实现

---

## Step 5：第二阶段精细化标注 / review

目录：

- [step5_stage2_review_prep/](/home/hrli/data_annotation/codes/process/step5_stage2_review_prep)
- [step5_stage2_review/](/home/hrli/data_annotation/codes/application/step5_stage2_review)

职责：

- 承接 `Step 4` 的第二阶段任务池
- 做更精细的 review / refinement

说明：

- 当前 active 仓库中保留了它的基础设施与资源
- 但按当前主线口径，它属于后续阶段，不应被当成“已完成主线”

---

## Support

目录：

- [support/](/home/hrli/data_annotation/codes/application/support)

职责：

- 提供 admin 和横向支持能力

---

## 当前最短理解

如果只记一句话：

> active 仓库当前真正负责的是，从标准化输入开始，到第一阶段 `human_stage_1` 最终完成版跑通为止；`Step 4` 是缺口，`Step 5` 是后续阶段资源。
