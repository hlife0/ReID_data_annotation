# Codes Directory

`codes/` 只保留当前活跃代码与历史归档代码。

## 活跃目录

- `application/`
  - 在线服务与前端静态资源
  - 当前主入口：
    - `application/ui_human_stage_1_server.py`
    - `application/ui_review_server.py`
    - `application/ui_admin_server.py`
- `process/`
  - 离线处理脚本与处理库
  - 当前新增入口：
    - `process/process_human_stage_1_prep.py`
  - 主线执行顺序见：
    - [`process/README.md`](/home/hrli/data_annotation/codes/process/README.md)
- `test/`
  - 当前活跃测试
  - 统一用：
    - `PYTHONPATH=codes .venv/bin/python -m unittest discover -s codes/test`

## 历史目录

- `archive/`
  - 已弃用或不再作为主线的历史实现
  - 仅用于追溯，不应作为当前入口继续扩写

## 当前主线的最短理解

如果你只关心当前两阶段主线，请按下面顺序看代码：

1. `process/process_prelabel_batch.py`
2. `process/process_segment_review_prep.py`
3. `process/process_human_stage_1_prep.py`
4. `application/ui_human_stage_1_server.py`
5. `application/ui_review_server.py`
6. `application/ui_admin_server.py`
7. `test/test_process_segment_review_prep.py`
8. `test/test_process_human_stage_1_prep.py`
9. `test/test_ui_human_stage_1_server.py`
10. `test/test_segment_review_server.py`

补充说明：

- `process_segment_review_prep.py` 当前不只保留 first-pass 的 `stable_segment / non_simple_single_frame`，也会在 second-pass 中生成 `repair_window`
- 当前持续优化的第一轮人工主线是 `human_stage_1`
- 旧的一次性标注/result-stack/downstream 代码已归档到：
  - `codes/archive/legacy_one_shot_annotation/`
