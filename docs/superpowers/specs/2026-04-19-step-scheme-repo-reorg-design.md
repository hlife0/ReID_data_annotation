# Step-Scheme Repository Reorganization Design

## Goal

Reorganize the active repository so that the codebase clearly reflects the agreed `Step 0` to `Step 5` workflow.

The active repository must remain split into:

- `codes/process/`
- `codes/application/`

But within those directories, resources must be grouped into step-specific subdirectories instead of mixed flat files.

## Workflow Model

The agreed step model is:

1. `Step 0`: raw capture preparation into standardized required inputs
2. `Step 1`: AI prelabel generation
3. `Step 2`: stage-1 task generation
4. `Step 3`: stage-1 human coarse labeling
5. `Step 4`: post-stage-1 processing and stage-2 task-pool generation
6. `Step 5`: stage-2 detailed review / refinement (currently not the completed active mainline)

Additional tools such as admin panels and development-only analysis utilities are not steps and should be separated accordingly.

## Active Code Mapping

### Process

- `Step 0`
  - `process_prepare_capture_batch.py`
  - `prepare_capture_lib.py`
- `Step 1`
  - `process_prelabel_batch.py`
- `Step 2`
  - `process_human_stage_1_prep.py`
- `Step 4`
  - currently no production implementation; create an explicit placeholder step directory so the workflow is visible
- `Step 5`
  - `process_segment_review_prep.py`
- Shared
  - `segment_prep_common.py`
- Dev-only
  - `analyze_human_stage_1_segmentation_grid.py`

### Application

- `Step 3`
  - `ui_human_stage_1_server.py`
  - `ui_human_stage_1_web/`
- `Step 5`
  - `ui_review_server.py`
  - `ui_review_web/`
- Support
  - `ui_admin_server.py`
  - `ui_admin_web/`

## Directory Layout

### `codes/process/`

Use:

- `codes/process/step0_preprocess/`
- `codes/process/step1_prelabel/`
- `codes/process/step2_stage1_prep/`
- `codes/process/step4_stage2_task_pool/`
- `codes/process/step5_stage2_review_prep/`
- `codes/process/shared/`
- `codes/process/devtools/`

### `codes/application/`

Use:

- `codes/application/step3_human_stage_1/`
- `codes/application/step5_stage2_review/`
- `codes/application/support/`

### `codes/test/`

Tests should also be grouped by responsibility:

- `codes/test/step0_preprocess/`
- `codes/test/step1_prelabel/`
- `codes/test/step2_stage1_prep/`
- `codes/test/step3_human_stage_1/`
- `codes/test/step5_stage2_review/`
- `codes/test/support/`
- `codes/test/devtools/`

## Step 4 Placeholder

`Step 4` currently lacks a production implementation, but it is part of the approved workflow model.

The reorganization must make that explicit by creating a dedicated active directory with:

- a README describing its intended responsibility
- no fake production implementation

This keeps the workflow honest and makes the gap visible.

## Archive Boundary

Previously archived one-shot and auxiliary resources remain archived.

This reorganization should not reactivate them.

## Required Follow-Up Changes

The reorganization must update:

- imports
- tests
- README files
- active documentation path references
- repo layout tests

## Verification

Verification must prove:

1. active code now lives under step-specific directories
2. imports resolve correctly
3. active tests still pass
4. docs point to the new active paths
