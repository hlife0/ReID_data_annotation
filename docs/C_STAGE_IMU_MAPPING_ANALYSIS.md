# C 阶段结果分析：双 IMU 静止/运动比值与人物对应辅助

- 分析批次：`annotation/batch_20260306_v02`
- 文档生成时间：`2026-03-06 03:52:38`
- 数据来源：`batch_20260306_v02/imu_mapping/*.imu_ratio_rank.csv` 与 `*.imu_mapping_summary.json`

## 1. 这个需求在做什么

这个需求（需求文档 C）要解决的问题是：
1. 把每个视频对应的两块 IMU 数据，对齐到视频每一帧时间。
2. 在每一帧上计算两块 IMU 的可比系数，得到 `k_t = c_a / c_b` 与 `m_t = max(k_t, 1/k_t)`。
3. 按 `m_t` 由高到低排序，挑出最容易区分两个人状态差异的时刻，辅助人工回放判断“谁对应哪块 IMU”。
4. 每帧同时输出 `static_coef_a/static_coef_b`，让“谁更静止”有可解释依据。

## 2. 我的算法与实现细节（可复现）

### 2.1 输入与巡检（C0）
- 输入目录使用相对路径：`./data/required/<video_stem>/...`。
- 每个视频必须有：
  - `video/<video_stem>_frame_timestamps_retimed.csv`
  - `imu/*.csv` 且数量必须恰好 2
- 不满足条件时标记 `blocked`，并写入 `annotation/batch_xxx/logs/errors.log`（不静默跳过）。

### 2.2 通道与预处理（C1）
- 使用 IMU 通道：`加速度X/Y/Z`、`角速度X/Y/Z`、`epoch_ms`。
- 列名兼容：优先精确匹配，其次子串匹配（兼容中文列名/BOM）。
- 无法解析的行（缺失值/异常值）直接丢弃，并统计 `skipped_rows`。
- 对原始运动强度做中心滑动均值去噪，窗口 `smoothing_window=5`。

### 2.3 系数定义
- 原始运动强度：
  - `acc_mag = sqrt(ax^2 + ay^2 + az^2)`
  - `gyro_mag = sqrt(gx^2 + gy^2 + gz^2)`
  - `motion_raw = |acc_mag - 1| + gyro_mag / gyro_norm_dps`，本次 `gyro_norm_dps=180`
- 平滑后运动系数：`motion_coef = max(min_coef, moving_average(motion_raw) + min_coef)`，本次 `min_coef=1e-6`。
- 静止系数：`static_coef = 1 / (1 + motion_coef)`。
- 本次运行 `coef_type=motion`，因此：`coef_a = motion_coef_a`，`coef_b = motion_coef_b`。
- 比值定义：
  - `k_t = coef_a / coef_b`
  - `m_t = max(k_t, 1/k_t)`

### 2.4 帧时间对齐策略
- 对每个视频帧 `timestamp_ms(t)`，分别在两块 IMU 的 `epoch_ms` 序列做最近邻匹配。
- 允许最大时间差 `max_align_gap_ms=250`；超过阈值则该帧跳过并计入统计。
- 本批次 4 个视频全部成功对齐，无对齐跳帧。

### 2.5 排序、导出与校验（C2/C3）
- 输出 CSV 字段严格满足文档要求：
  - `video_stem, frame_index, timestamp_ms, imu_id_a, imu_id_b, static_coef_a, static_coef_b, coef_type, coef_a, coef_b, k_t, m_t, rank_m_desc`
- 排序规则：先按 `m_t` 降序，再按 `timestamp_ms` 升序；`rank_m_desc` 从 1 开始连续编号。
- 每视频输出 summary JSON，记录算法公式、参数、异常处理、统计和建议回放区间。
- 额外使用 `codex/test_imu_mapping_outputs.py` 做字段、公式、排序、rank 连续性校验。

## 3. 本次运行结果总览

- 运行命令：` .venv/bin/python ./codex/process_imu_mapping_batch.py --required-root ./data/required --output-root ./annotation --coef-type motion --smoothing-window 5 --max-align-gap-ms 250 `
- 输出批次：`annotation/batch_20260306_v02`
- 处理视频数：4
- 成功：4，blocked：0，failed：0
- 校验结果：`Validation PASS: csv_files=4, summary_files=4`

## 4. 每个视频的 5 个高优先级片段（并标注“谁更静止”）

说明：时间均为“相对视频起点”的时间；每段为约 2.4 秒窗口（中心点 ±1.2 秒，起点不足时从 0 秒截断）。

### 4.1 视频 `20260211_171423`

- IMU-A：`da:19:a9:ac:6d:fe`
- IMU-B：`f8:a2:fd:ea:fb:80`

| 序号 | 片段时间 | 关键帧(rank) | m_t | static_coef_a | static_coef_b | 谁更静止 |
|---|---|---:|---:|---:|---:|---|
| 1 | 1分08.18秒 到 1分10.58秒 | 1 | 7.0493 | 0.5764 | 0.9056 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 2 | 1分03.28秒 到 1分05.68秒 | 22 | 5.5077 | 0.2951 | 0.6975 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 3 | 0分18.78秒 到 0分21.18秒 | 79 | 3.4525 | 0.7496 | 0.4643 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 4 | 0分25.05秒 到 0分27.45秒 | 85 | 3.3808 | 0.5937 | 0.3018 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 5 | 0分00.00秒 到 0分01.27秒 | 88 | 3.3490 | 0.4714 | 0.7492 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |

判读建议：优先按以上顺序回放这些片段，结合画面中 P1/P2 身体运动幅度，判断对应 IMU。

### 4.2 视频 `20260211_171724`

- IMU-A：`da:19:a9:ac:6d:fe`
- IMU-B：`f8:a2:fd:ea:fb:80`

| 序号 | 片段时间 | 关键帧(rank) | m_t | static_coef_a | static_coef_b | 谁更静止 |
|---|---|---:|---:|---:|---:|---|
| 1 | 0分53.94秒 到 0分56.34秒 | 1 | 44.5842 | 0.6736 | 0.9892 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 2 | 1分01.14秒 到 1分03.54秒 | 17 | 16.9756 | 0.8468 | 0.9895 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 3 | 0分12.74秒 到 0分15.14秒 | 20 | 16.9419 | 0.7128 | 0.9768 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 4 | 0分09.24秒 到 0分11.64秒 | 23 | 16.7237 | 0.7667 | 0.9821 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 5 | 0分48.57秒 到 0分50.97秒 | 26 | 16.6353 | 0.7929 | 0.9845 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |

判读建议：优先按以上顺序回放这些片段，结合画面中 P1/P2 身体运动幅度，判断对应 IMU。

### 4.3 视频 `20260211_172257`

- IMU-A：`da:19:a9:ac:6d:fe`
- IMU-B：`f8:a2:fd:ea:fb:80`

| 序号 | 片段时间 | 关键帧(rank) | m_t | static_coef_a | static_coef_b | 谁更静止 |
|---|---|---:|---:|---:|---:|---|
| 1 | 0分00.00秒 到 0分01.20秒 | 1 | 28.1036 | 0.5170 | 0.9678 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 2 | 0分30.06秒 到 0分32.46秒 | 6 | 6.9126 | 0.5754 | 0.1639 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 3 | 0分18.75秒 到 0分21.15秒 | 30 | 4.8221 | 0.5331 | 0.1914 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 4 | 0分06.04秒 到 0分08.44秒 | 42 | 3.6451 | 0.6435 | 0.3312 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 5 | 0分25.15秒 到 0分27.55秒 | 73 | 3.2837 | 0.4779 | 0.2180 | IMU-A（da:19:a9:ac:6d:fe）更静止 |

判读建议：优先按以上顺序回放这些片段，结合画面中 P1/P2 身体运动幅度，判断对应 IMU。

### 4.4 视频 `20260211_172522`

- IMU-A：`da:19:a9:ac:6d:fe`
- IMU-B：`f8:a2:fd:ea:fb:80`

| 序号 | 片段时间 | 关键帧(rank) | m_t | static_coef_a | static_coef_b | 谁更静止 |
|---|---|---:|---:|---:|---:|---|
| 1 | 0分00.00秒 到 0分02.17秒 | 1 | 68.6484 | 0.1639 | 0.9308 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 2 | 0分41.46秒 到 0分43.86秒 | 21 | 9.4935 | 0.8394 | 0.3550 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 3 | 0分58.38秒 到 1分00.78秒 | 36 | 7.6626 | 0.2241 | 0.6888 | IMU-B（f8:a2:fd:ea:fb:80）更静止 |
| 4 | 0分44.67秒 到 0分47.07秒 | 49 | 7.1906 | 0.8323 | 0.4084 | IMU-A（da:19:a9:ac:6d:fe）更静止 |
| 5 | 0分09.57秒 到 0分11.97秒 | 96 | 5.3843 | 0.6060 | 0.2222 | IMU-A（da:19:a9:ac:6d:fe）更静止 |

判读建议：优先按以上顺序回放这些片段，结合画面中 P1/P2 身体运动幅度，判断对应 IMU。

## 5. 结果解读注意事项

1. `m_t` 只表示“差异强度”，不直接告诉你“谁是谁”。
2. “谁更静止”是基于 `static_coef` 的瞬时比较；最终人-IMU 对应仍需结合视频人工确认。
3. 当前 `coef_type=motion`，若后续切到 `coef_type=static`，`k_t` 含义会变成静止系数比值，但输出字段不变。
4. 若未来出现 IMU 丢包/对齐失败，`errors.log` 和 summary 的 `frame_skipped_*` 会给出明确原因与数量。

