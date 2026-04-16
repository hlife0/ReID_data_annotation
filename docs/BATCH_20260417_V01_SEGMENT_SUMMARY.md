# Batch `20260417_v01` Segment Summary

最后更新：2026-04-17

---

## 背景

本报告记录一个新的派生 batch：

- `./annotation/batch_20260417_v01`

它不是重新跑 A 阶段预标注得到的 batch，而是从：

- `./annotation/batch_20260413_v01`

派生出来的实验 batch。派生方式是：

- 复用 `manifests/annotation_tasks.csv`
- 复用 `pseudo_labels/*.auto.csv`
- 重新计算 `segment_prep/`
- 初始化一套全新的 review 存储

本次派生 batch 的目标是验证：

- conservative low-score gap bridge

对应实现提交：

- `ae0f959` `feat: add conservative segment gap bridge`

---

## 参数口径

本批次 `segment_prep` 的参数为：

- `low_score_threshold = 0.4`
- `high_overlap_iou = 0.25`
- `bridge_low_score_gaps = true`
- `max_gap_frames = 2`

桥接规则是保守版：

- 仅桥接长度不超过 2 帧的短坏段
- 坏段前后必须都是 simple
- 坏段前后 `track_ids` 必须一致
- 坏段内 `track_ids` 必须与两侧一致
- 仅桥接 `low_only`，不桥接 `overlap_only`

---

## 指标定义

### 1. 段数 `segment_count`

每个 session 被切分后的总段数，满足：

- `segment_count = stable_segment_count + non_simple_single_frame_count`

### 2. 标注压缩率 `compression_rate`

定义为：

```text
compression_rate = 1 - segment_count / frame_count
```

### 3. 标注压缩倍数 `compression_multiple`

定义为：

```text
compression_multiple = frame_count / segment_count
```

---

## 总览

| Metric | Value |
|---|---:|
| Total Frames | 109,634 |
| Total Segments | 21,031 |
| Stable Segments | 4,168 |
| Non-simple Singles | 16,863 |
| Compression Rate | 80.817% |
| Compression Multiple | 5.213x |

---

## 与上一版 `0.4` 无桥接结果对比

这里的对比对象是：

- `batch_20260413_v01`
- `low_score_threshold = 0.4`
- 未开启 gap bridge

| Metric | Previous | Current | Delta |
|---|---:|---:|---:|
| Total Segments | 22,813 | 21,031 | -1,782 |
| Stable Segments | 4,984 | 4,168 | -816 |
| Non-simple Singles | 17,829 | 16,863 | -966 |
| Compression Rate | 79.192% | 80.817% | +1.625 pt |
| Compression Multiple | 4.806x | 5.213x | +0.407x |

说明：

- `non_simple_single_frame` 减少了 `966`
- 总段数减少了 `1,782`
- 平均每个待标注段对应的帧数继续上升

---

## Session Table

| Session | Frames | Segments | Stable | Non-simple singles | Compression Rate | Compression Multiple |
|---|---:|---:|---:|---:|---:|---:|
| `20260410_195433_seg_195631907` | 482 | 68 | 23 | 45 | 85.892% | 7.088x |
| `20260410_195433_seg_200624895` | 20,892 | 7,994 | 1,287 | 6,707 | 61.737% | 2.613x |
| `20260410_195433_seg_202252403` | 436 | 31 | 11 | 20 | 92.890% | 14.065x |
| `20260410_195433_seg_202322593` | 4,298 | 1,854 | 322 | 1,532 | 56.864% | 2.318x |
| `20260410_195433_seg_203019164` | 4,631 | 1,379 | 310 | 1,069 | 70.222% | 3.358x |
| `20260410_195433_seg_203534590` | 4,087 | 422 | 131 | 291 | 89.675% | 9.685x |
| `20260410_195433_seg_203903214` | 1,734 | 8 | 7 | 1 | 99.539% | 216.750x |
| `20260410_195433_seg_204401893` | 6,028 | 1,459 | 315 | 1,144 | 75.796% | 4.132x |
| `20260410_195433_seg_204834788` | 3,885 | 698 | 123 | 575 | 82.033% | 5.566x |
| `20260410_195433_seg_205322033` | 4,157 | 297 | 101 | 196 | 92.855% | 13.997x |
| `20260410_195433_seg_205628547` | 3,870 | 309 | 36 | 273 | 92.016% | 12.524x |
| `20260410_195433_seg_210024755` | 5,659 | 2,401 | 364 | 2,037 | 57.572% | 2.357x |
| `20260410_195433_seg_212054666` | 452 | 12 | 4 | 8 | 97.345% | 37.667x |
| `20260410_195433_seg_212127507` | 22,559 | 3,400 | 863 | 2,537 | 84.928% | 6.635x |
| `20260410_195433_seg_213534240` | 3,901 | 155 | 61 | 94 | 96.027% | 25.168x |
| `20260410_195433_seg_213830886` | 5,378 | 426 | 157 | 269 | 92.079% | 12.624x |
| `20260410_195433_seg_214257369` | 4,146 | 1 | 1 | 0 | 99.976% | 4146.000x |
| `20260410_195433_seg_214542586` | 4,099 | 20 | 9 | 11 | 99.512% | 204.950x |
| `20260410_195433_seg_214832367` | 4,495 | 82 | 35 | 47 | 98.176% | 54.817x |
| `20260410_195433_seg_215134831` | 4,445 | 15 | 8 | 7 | 99.663% | 296.333x |

---

## 读表提示

这版 bridge 后，仍然最难的 session 主要是：

- `20260410_195433_seg_202322593`
- `20260410_195433_seg_210024755`
- `20260410_195433_seg_200624895`

它们的 `compression_multiple` 仍然只有 `2.x`，说明还有进一步降本空间。

压缩效果最好的 session 仍然是：

- `20260410_195433_seg_214257369`
- `20260410_195433_seg_215134831`
- `20260410_195433_seg_214542586`

---

## Review Storage 状态

该派生 batch 已完成 `ui_review_server.py --init-only` 初始化，当前状态为：

- `frames = 109634`
- `annotations = 0`
- `assignments = 0`
- `segment_reviews = 0`
- `frame_counts` 全部为 `0`

因此它是一个干净的新起点，可以直接用于新的 review 流程试运行。
