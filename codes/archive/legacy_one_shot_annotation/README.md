# Legacy One-Shot Annotation Code

本目录保存已从活跃仓库下线的一次性标注相关代码。

当前仓库只保留两阶段主线：

1. `human_stage_1`
2. 后续 segment-mode review / refinement

因此，下面这些旧路径都已从 active surface 移出：

- 旧 review-result 栈
- 旧单阶段下游分析脚本
- 旧单阶段最终导出脚本
- 旧 frame-mode 测试与快照

## 目录说明

- `application/`
  - 旧 `ui_review_result_server.py`
  - 旧 `ui_review_result_web/`
  - `ui_review_server_mixed_snapshot.py`
    - 迁移前的混合快照，用于保留旧 frame-mode 代码上下文
- `process/`
  - 旧下游分析、最终导出、渲染脚本
- `test/`
  - 旧一次性标注相关测试

## 恢复建议

若未来需要恢复旧路径：

1. 先阅读：
   - [SCHEMA.md](/home/hrli/data_annotation/docs/archive/legacy_one_shot_annotation/SCHEMA.md)
   - [README.md](/home/hrli/data_annotation/docs/archive/legacy_one_shot_annotation/README.md)
2. 再从本目录挑选需要恢复的代码
3. 最后再决定是否恢复旧数据库初始化和旧文档入口
