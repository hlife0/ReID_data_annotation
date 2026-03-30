# 需求文档 C：双 IMU 静止/运动比值分析与人物对应辅助（可直接喂给 AI）

## 1. 目标

本阶段目标：对每个视频对应的两个 IMU 做统计分析，输出“最容易区分两个人”的时间点，辅助建立 `P1(绿衣服)`、`P2(灰衣服)` 与 `imu_id` 的对应关系。

交付目标：

1. 对每一帧计算两个 IMU 的比值系数 `k_t`。
2. 对每一帧计算 `m_t = max(k_t, 1 / k_t)`。
3. 对每个视频按 `m_t` 从大到小排序输出 CSV。
4. CSV 必须包含：`k_t`、`m_t`、时间、两个 IMU 的静止系数。
5. 输出结果能直接用于后续“回放视频 + 人工判定人-IMU 对应”。

---

## 2. 输入范围（严格限制）

主输入：

1. `./data/required/<video_stem>/video/<video_stem>_frame_timestamps_retimed.csv`
2. `./data/required/<video_stem>/imu/*.csv`（必须恰好 2 个）

路径规则：

1. 使用当前工作目录下相对路径（`./...`）。
2. 数据盘仅通过软链接 `./data/...` 访问。
3. 禁止把原始绝对路径（`/data/...`）作为业务输入输出约定。

---

## 3. 输出目录与文件规范

写入当前批次目录：

```text
./annotation/batch_<YYYYMMDD>_<vNN>/
├── imu_mapping/
│   ├── <video_stem>.imu_ratio_rank.csv
│   └── <video_stem>.imu_mapping_summary.json
└── logs/
    ├── run.log
    └── errors.log
```

说明：

1. `imu_ratio_rank.csv` 是核心交付物。
2. `imu_mapping_summary.json` 用于记录算法定义、参数、异常处理与人工回放建议。

---

## 4. 核心定义（强制）

对于每个视频，设两块 IMU 分别为 `imu_id_a`、`imu_id_b`，第 `t` 帧时间戳为 `timestamp_ms(t)`。

1. AI 必须自行设计一种“静止系数/运动系数”算法（可选其一或两者同时）。
2. 设用于比值计算的两个系数为 `c_a(t)`、`c_b(t)`，要求严格大于 0。
3. 定义：
- `k_t = c_a(t) / c_b(t)`
- `m_t = max(k_t, 1 / k_t)`
4. 每帧必须同时给出两个 IMU 的静止系数：
- `static_coef_a(t)`
- `static_coef_b(t)`

备注：

1. 若 `c` 使用的是“运动系数”，也必须输出静止系数（可由算法直接定义或可解释转换）。
2. `m_t` 越大，代表该时刻两者状态差异越显著，越适合人工回放判断对应关系。

---

## 5. 算法要求（AI 自主设计，但必须可解释）

AI 可以自由设计具体算法，但必须在日志与 summary 中明确写清：

1. 使用了哪些 IMU 通道（加速度/角速度/模长等）。
2. 去噪、平滑、窗口长度、插值或对齐方法。
3. 帧时间对齐策略（按 `timestamp_ms` 的最近邻或插值规则）。
4. `static_coef` 与 `c` 的公式定义。
5. 缺失值、异常值、噪声尖峰处理规则。

---

## 6. CSV 字段规范（强制）

文件：`<video_stem>.imu_ratio_rank.csv`

必须包含字段：

1. `video_stem`
2. `frame_index`
3. `timestamp_ms`
4. `imu_id_a`
5. `imu_id_b`
6. `static_coef_a`
7. `static_coef_b`
8. `coef_type`（`static` / `motion`）
9. `coef_a`（用于 `k_t` 的 `c_a(t)`）
10. `coef_b`（用于 `k_t` 的 `c_b(t)`）
11. `k_t`
12. `m_t`
13. `rank_m_desc`

排序规则：

1. 按 `m_t` 从大到小排序。
2. 若 `m_t` 相同，按 `timestamp_ms` 从小到大排序。

---

## 7. 执行步骤（强制顺序）

### Step C0：输入巡检

1. 检查每视频时间戳 CSV 是否存在且可读。
2. 检查 IMU 文件数量是否为 2。
3. 不满足条件写入 `logs/errors.log` 并标记该视频 `blocked`。

### Step C1：帧级系数计算

1. 建立帧时间戳与 IMU 数据对齐关系。
2. 计算每帧 `static_coef_a/static_coef_b`。
3. 计算每帧 `coef_a/coef_b`。

### Step C2：比值与排序

1. 计算每帧 `k_t` 与 `m_t`。
2. 按 `m_t` 降序生成排名。

### Step C3：导出

1. 导出 `imu_ratio_rank.csv`。
2. 导出 `imu_mapping_summary.json`（算法说明 + 推荐回放区间）。

---

## 8. 验收标准

全部满足才算通过：

1. 每个可处理视频都生成 `imu_ratio_rank.csv`。
2. CSV 包含 `k_t`、`m_t`、时间、两个 IMU 静止系数。
3. 排序符合 `m_t` 降序规则。
4. 有完整 `run.log`、`errors.log`。
5. `imu_mapping_summary.json` 可解释算法与参数。

---

## 9. 失败处理规则

1. 缺失 IMU 或时间戳文件：该视频标记 `blocked`，必须写错误日志。
2. 某些帧无法对齐：允许跳过，但必须记录跳过数量与原因。
3. 输出字段缺失、`k_t/m_t` 不可计算或排序错误：判定失败，修复后重跑。

---

## 10. 完成定义（DoD）

当且仅当以下条件全部满足：

1. 全部目标视频完成双 IMU 比值分析（或有明确 blocked 原因）。
2. 每视频输出 `imu_ratio_rank.csv`，可直接用于人工回放筛选。
3. 每条记录包含 `k_t`、`m_t`、时间与双 IMU 静止系数。
4. 算法定义、参数、异常处理可追溯。
