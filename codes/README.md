# Codes Directory

`codes/` 只保留当前活跃代码与历史归档代码。

## 活跃目录

- `application/`
  - 在线服务与前端静态资源
  - 当前按 step 分层：
    - `application/step3_human_stage_1/`
    - `application/step5_stage2_review/`
    - `application/support/`
- `process/`
  - 离线处理脚本与处理库
  - 当前按 step 分层：
    - `process/step0_preprocess/`
    - `process/step1_prelabel/`
    - `process/step2_stage1_prep/`
    - `process/step4_stage2_task_pool/`
    - `process/step5_stage2_review_prep/`
    - `process/shared/`
    - `process/devtools/`
  - 主线执行顺序见：
    - [`process/README.md`](/home/hrli/data_annotation/codes/process/README.md)
- `test/`
  - 当前活跃测试
  - 当前按 step / support / devtools 分层
  - 统一用：
    - `PYTHONPATH=codes .venv/bin/python -m unittest discover -s codes/test`

## 历史目录

- `archive/`
  - 已弃用或不再作为主线的历史实现
  - 仅用于追溯，不应作为当前入口继续扩写

## 当前主线的最短理解

如果你只关心当前 `Step 0-5` 主线，请按下面顺序看代码：

1. `process/step0_preprocess/`
2. `process/step1_prelabel/`
3. `process/step2_stage1_prep/`
4. `application/step3_human_stage_1/`
5. `process/step4_stage2_task_pool/`
6. `process/step5_stage2_review_prep/`
7. `application/step5_stage2_review/`
8. `application/support/`
9. `test/step0_preprocess/` 到 `test/step5_stage2_review/`
10. `test/support/` 与 `test/devtools/`

补充说明：

- 当前真正已经跑通的主线重点是 `Step 0 -> Step 3`
- `Step 4` 目录当前是显式占位，用来表达“第一阶段结果处理 / 第二阶段任务池生成”这一缺口
- `Step 5` 目录保留当前第二阶段资源与基础设施，但按仓库主线口径应视为后续阶段，不是已完成主线
- 旧的一次性标注/result-stack/downstream 代码已归档到：
  - `codes/archive/legacy_one_shot_annotation/`
- 旧辅助支线已归档到：
  - `codes/archive/legacy_auxiliary/`
