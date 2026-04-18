# Human Stage 1 Segmentation Grid Design

## Goal

Build an independent analysis workflow that measures how many stage-1 human work units remain after:

1. first-pass segmentation
2. second-pass `repair_window` merge

across a grid of parameter configurations for the `human_stage_1` pipeline.

The workflow must not modify the production behavior of:

- `codes/process/process_human_stage_1_prep.py`
- `codes/process/process_segment_review_prep.py`

## Scope

This design covers only:

- offline statistics for the `human_stage_1` branch
- parameter sweeps for first-pass and second-pass segmentation
- export of reproducible summary artifacts

This design does not cover:

- changes to production prep logic
- UI changes
- review-branch statistics
- generalized experiment orchestration beyond this sweep

## Core Metric

For this analysis, a "remaining frame" means a remaining stage-1 human work unit.

The metric is therefore:

```text
remaining_work_unit_ratio = work_unit_count / total_original_frames
```

Where:

- `total_original_frames` is the total number of timestamped frames in the batch
- `first_pass_work_unit_count` is the number of first-pass segments:
  - `stable_segment`
  - `non_simple_single_frame`
- `second_pass_work_unit_count` is the number of final stage-1 segments after `repair_window` merge

Because `human_stage_1` shows one representative frame per segment, segment count is the correct work-unit count.

## Analysis Approach

Add a separate analysis script that reuses the existing segmentation helpers but exposes the configuration knobs needed for the sweep.

The script will:

1. load batch tasks and pseudo labels
2. count total frames from timestamp CSVs
3. run first-pass segmentation for each first-pass configuration
4. record `first_pass_work_unit_count / total_original_frames`
5. run second-pass fragment merging for each second-pass configuration on top of each first-pass result
6. record `second_pass_work_unit_count / total_original_frames`
7. export Markdown, CSV, and JSON summaries

## Parameter Grid

### First-Pass Configurations

Sweep these knobs across the columns of the main table:

- `low_score_threshold`
- `bridge_low_score_gaps`

Keep these fixed unless explicitly overridden:

- `high_overlap_iou = 0.25`
- `max_gap_frames = 2`

Initial column set:

- `FP1`: `low_score=0.40`, `bridge=false`
- `FP2`: `low_score=0.40`, `bridge=true`
- `FP3`: `low_score=0.50`, `bridge=false`
- `FP4`: `low_score=0.50`, `bridge=true`
- `FP5`: `low_score=0.60`, `bridge=false`
- `FP6`: `low_score=0.60`, `bridge=true`

### Second-Pass Configurations

Sweep these knobs across the rows of the main table:

- `micro_stable_max_frames`
- `max_repair_window_frames`

Initial row set:

- `SP1`: `micro_stable_max_frames=1`, `max_repair_window_frames=6`
- `SP2`: `micro_stable_max_frames=2`, `max_repair_window_frames=8`
- `SP3`: `micro_stable_max_frames=3`, `max_repair_window_frames=10`
- `SP4`: `micro_stable_max_frames=4`, `max_repair_window_frames=12`

The stage-1 rule that a merged run must include at least two `non_simple_single_frame` segments remains fixed.

## Outputs

Write outputs under:

```text
annotation/<batch>/analysis/human_stage_1_segmentation_grid/
```

Artifacts:

- `summary.md`
- `first_pass_summary.csv`
- `second_pass_grid.csv`
- `results.json`

`summary.md` must include:

- total frame count
- first-pass summary table
- second-pass grid table
- configuration legend

The main second-pass table must use:

- columns = first-pass configurations
- rows = second-pass configurations
- cell value = `second_pass_work_unit_count / total_original_frames`

## Code Placement

Add an independent analysis entry point:

- `codes/process/analyze_human_stage_1_segmentation_grid.py`

Add focused tests:

- `codes/test/test_analyze_human_stage_1_segmentation_grid.py`

No production prep script should be modified unless a narrowly scoped refactor is required to share pure helper logic.

## Verification

Verification must include:

1. unit tests for first-pass and second-pass work-unit counting on synthetic data
2. unit tests for result export structure
3. one real-batch run against `annotation/batch_20260417_v01` unless the user overrides the batch path

## Success Criteria

This work is complete when:

1. the analysis script runs without changing production prep behavior
2. the requested parameter sweep is reproducible
3. the exported Markdown table clearly shows second-pass ratios with first-pass configurations on the horizontal axis and second-pass configurations on the vertical axis
4. the first-pass work-unit ratios are also exported and reported
