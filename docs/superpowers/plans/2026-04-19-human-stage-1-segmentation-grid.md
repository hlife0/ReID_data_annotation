# Human Stage 1 Segmentation Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent analysis tool that sweeps `human_stage_1` first-pass and second-pass segmentation parameters and exports work-unit ratio tables without changing production prep behavior.

**Architecture:** Add one standalone analysis script under `codes/process/` that reuses the existing segmentation helpers to compute first-pass segments and stage-1 second-pass merged segments for a parameter grid. Keep production prep code unchanged, add focused tests for counting and export behavior, and write Markdown/CSV/JSON outputs under the target batch.

**Tech Stack:** Python 3, existing `codes/process` helpers, `unittest`, CSV/JSON/Markdown file output

---

### Task 1: Add Failing Analysis Tests

**Files:**
- Create: `codes/test/test_analyze_human_stage_1_segmentation_grid.py`
- Test: `codes/test/test_analyze_human_stage_1_segmentation_grid.py`

- [ ] **Step 1: Write the failing test file**

Add tests that:

- build a synthetic batch similar to `test_process_human_stage_1_prep.py`
- verify total frame counting
- verify first-pass work-unit counting
- verify second-pass merge counting for configurable thresholds
- verify result export files exist and contain the expected table labels

- [ ] **Step 2: Run the new test file to verify it fails**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_analyze_human_stage_1_segmentation_grid -v
```

Expected:

- import failure because the new analysis module does not exist yet

- [ ] **Step 3: Keep the tests focused on pure counting/output behavior**

Use assertions on:

- `total_frames`
- `first_pass_work_units`
- `second_pass_work_units`
- exported file paths and key strings

- [ ] **Step 4: Re-run the targeted test file and confirm it still fails for missing implementation**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_analyze_human_stage_1_segmentation_grid -v
```

Expected:

- still fails because the analysis module/functions are not implemented

### Task 2: Implement the Independent Analysis Module

**Files:**
- Create: `codes/process/analyze_human_stage_1_segmentation_grid.py`
- Test: `codes/test/test_analyze_human_stage_1_segmentation_grid.py`

- [ ] **Step 1: Add configuration data structures and pure helpers**

Implement:

- first-pass config records
- second-pass config records
- total frame counting
- first-pass segment generation using existing helpers
- stage-1 second-pass merge using parameterized logic local to the analysis module

- [ ] **Step 2: Add batch-level sweep logic**

Implement functions that:

- iterate all videos in a batch
- accumulate total frame count
- compute first-pass counts per first-pass config
- compute second-pass counts for each `(second-pass, first-pass)` pair
- store ratios as `count / total_frames`

- [ ] **Step 3: Add summary export helpers**

Implement helpers that write:

- Markdown summary
- first-pass CSV
- second-pass grid CSV
- JSON result payload

- [ ] **Step 4: Add a CLI entry point**

Support:

- `--batch-dir`
- optional output directory override

Default behavior should target:

- `annotation/<batch>/analysis/human_stage_1_segmentation_grid/`

- [ ] **Step 5: Run the targeted tests and verify they pass**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_analyze_human_stage_1_segmentation_grid -v
```

Expected:

- all tests pass

### Task 3: Verify Integration Against Existing Prep Semantics

**Files:**
- Modify: `codes/test/test_analyze_human_stage_1_segmentation_grid.py`
- Test: `codes/test/test_process_human_stage_1_prep.py`

- [ ] **Step 1: Add one compatibility-oriented assertion**

Add a test case that uses the synthetic fragment cluster and checks that the default analysis second-pass settings match the current stage-1 prep behavior for the same sample.

- [ ] **Step 2: Run both test files**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_analyze_human_stage_1_segmentation_grid codes.test.test_process_human_stage_1_prep -v
```

Expected:

- both test files pass

- [ ] **Step 3: Refactor only if duplication is hurting readability**

Keep production prep untouched unless a tiny pure-helper extraction is clearly necessary.

### Task 4: Execute the Real Batch Sweep

**Files:**
- Read/Write: `annotation/batch_20260417_v01/analysis/human_stage_1_segmentation_grid/`

- [ ] **Step 1: Run the analysis CLI on the target batch**

Run:

```bash
PYTHONPATH=codes .venv/bin/python codes/process/analyze_human_stage_1_segmentation_grid.py --batch-dir annotation/batch_20260417_v01
```

Expected:

- the command completes successfully
- output artifacts are created under the batch analysis directory

- [ ] **Step 2: Inspect the generated summary**

Check:

- total frame count is present
- first-pass summary table is populated
- second-pass grid table is populated

- [ ] **Step 3: Report results back to the user**

Summarize:

- total original frames
- first-pass work-unit ratios by first-pass config
- second-pass ratio table
- artifact paths

### Task 5: Final Verification

**Files:**
- Test: `codes/test/test_analyze_human_stage_1_segmentation_grid.py`
- Test: `codes/test/test_process_human_stage_1_prep.py`
- Run: `codes/process/analyze_human_stage_1_segmentation_grid.py`

- [ ] **Step 1: Run the targeted analysis tests**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_analyze_human_stage_1_segmentation_grid codes.test.test_process_human_stage_1_prep -v
```

Expected:

- PASS

- [ ] **Step 2: Re-run the real analysis command**

Run:

```bash
PYTHONPATH=codes .venv/bin/python codes/process/analyze_human_stage_1_segmentation_grid.py --batch-dir annotation/batch_20260417_v01
```

Expected:

- PASS
- exported files are updated

- [ ] **Step 3: Confirm no production behavior was changed**

Check that only the new analysis script, its tests, and output artifacts were added for this task.
