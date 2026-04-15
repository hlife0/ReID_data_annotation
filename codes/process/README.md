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
- 求极大稳定段
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
- 接收代表帧或单帧标注
- 展开成逐帧 `p1-p7` 结果

### 5. `application/ui_admin_server.py`

这是在线 admin 服务入口。

作用：

- 查看 batch 全局统计
- 查看段统计
- 查看 annotator 活跃度与提交结果

### 6. `process_final_annotation_batch.py`（下游）

这是下游导出脚本，不属于“先把段模式跑起来”的最小闭环。

只有在前面的 segment review 主线稳定后，才继续对齐和使用它。

## 最常见的正确顺序

```text
process_prepare_capture_batch.py   (可选)
-> process_prelabel_batch.py
-> process_segment_review_prep.py
-> application/ui_review_server.py
-> application/ui_admin_server.py
```

## 其他脚本

- `prepare_capture_lib.py`
  - `process_prepare_capture_batch.py` 的辅助库
- `segment_prep_common.py`
  - `process_segment_review_prep.py` 的公共读取与几何工具
- `process_annotation_analysis.py`
  - 下游一致性分析脚本
- `process_imu_mapping_batch.py`
  - IMU 映射辅助脚本
- `render_final_annotations_video.py`
  - 最终导出结果的视频可视化脚本

## 不要乱套的规则

1. 不要先开 review 服务再忘了重算 `segment_prep/`
2. 不要把 `process_final_annotation_batch.py` 当成段模式的前置步骤
3. 不要把 `archive/` 里的旧脚本当成活跃入口
