# Segment Gap Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative low-score gap bridge to segment prep, then execute it on a new derived batch without modifying the existing batch.

**Architecture:** Keep the current raw frame classification intact, add a second pass that bridges only short `low_only` bad runs under strict neighboring-track constraints, and reuse the existing segment export format. Execute the new behavior only on a newly created batch so prior review data remains untouched.

**Tech Stack:** Python, unittest, JSON/CSV batch artifacts, git worktrees

---

## File Map

- Modify: `codes/process/process_segment_review_prep.py`
  - Add raw frame-state reasoning and conservative gap-bridge logic
  - Add CLI flags for bridge enablement and max gap length
- Modify: `codes/test/test_process_segment_review_prep.py`
  - Add red/green coverage for bridge-positive and bridge-negative cases
- Create: `docs/superpowers/specs/2026-04-17-segment-gap-bridge-design.md`
- Create: `docs/superpowers/plans/2026-04-17-segment-gap-bridge.md`
- Create: `docs/BATCH_20260417_V01_SEGMENT_SUMMARY.md`

---

### Task 1: Add Failing Tests For Conservative Gap Bridge

**Files:**
- Modify: `codes/test/test_process_segment_review_prep.py`
- Test: `codes/test/test_process_segment_review_prep.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

- one-frame `low_only` gap gets bridged when enabled
- two-frame `low_only` gap gets bridged when enabled
- `overlap_only` gap does not get bridged
- mismatched track-set gap does not get bridged
- disabled bridge preserves current behavior

- [ ] **Step 2: Run the targeted test file to verify failure**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest codes.test.test_process_segment_review_prep
```

Expected:

- FAIL because bridge behavior does not exist yet

- [ ] **Step 3: Commit the red tests**

```bash
git add codes/test/test_process_segment_review_prep.py
git commit -m "test: cover conservative segment gap bridge"
```

---

### Task 2: Implement Conservative Gap Bridge

**Files:**
- Modify: `codes/process/process_segment_review_prep.py`
- Test: `codes/test/test_process_segment_review_prep.py`

- [ ] **Step 1: Add frame-state helpers**

Introduce helpers for:

- raw reason classification per frame
- contiguous bad-run detection
- conservative bridge eligibility checks

- [ ] **Step 2: Thread bridge configuration into the pipeline**

Add CLI and function parameters:

```text
--bridge-low-score-gaps
--max-gap-frames
```

Default behavior must remain unchanged when bridge is disabled.

- [ ] **Step 3: Make segment building consume effective simple states**

Keep the export schema unchanged, but use the bridged classification for stable/non-simple decisions.

- [ ] **Step 4: Run targeted tests to verify green**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest codes.test.test_process_segment_review_prep
```

Expected:

- PASS

- [ ] **Step 5: Commit the implementation**

```bash
git add codes/process/process_segment_review_prep.py codes/test/test_process_segment_review_prep.py
git commit -m "feat: add conservative segment gap bridge"
```

---

### Task 3: Run Full Regression Verification

**Files:**
- Verify only

- [ ] **Step 1: Run the active Python test suite**

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest discover -s codes/test
```

Expected:

- PASS

- [ ] **Step 2: Run JS syntax verification**

```bash
node --check codes/application/ui_review_web/app.js
node --check codes/application/ui_admin_web/app.js
node --check codes/application/ui_review_result_web/app.js
```

Expected:

- all commands exit 0

---

### Task 4: Create A New Derived Batch

**Files:**
- Create under: `annotation/batch_20260417_v01/`

- [ ] **Step 1: Create a fresh derived batch directory**

Create:

- `annotation/batch_20260417_v01/manifests/`
- `annotation/batch_20260417_v01/pseudo_labels/`
- `annotation/batch_20260417_v01/logs/`

- [ ] **Step 2: Copy or hardlink upstream artifacts**

Carry over:

- `manifests/annotation_tasks.csv`
- all `pseudo_labels/*.auto.csv`

Source batch:

- `annotation/batch_20260413_v01`

- [ ] **Step 3: Confirm the new batch contains no review database**

Expected:

- no `ui_tasks/ui_review.sqlite3`
- no carried-over `reviewed/*.csv`
- no carried-over `reviewed_raw/*.jsonl`

---

### Task 5: Execute New Segment Prep On The Derived Batch

**Files:**
- Generate: `annotation/batch_20260417_v01/segment_prep/*`

- [ ] **Step 1: Run segment prep with bridge enabled**

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python codes/process/process_segment_review_prep.py \
  --batch-dir ./annotation/batch_20260417_v01 \
  --low-score-threshold 0.4 \
  --bridge-low-score-gaps \
  --max-gap-frames 2
```

- [ ] **Step 2: Initialize clean review storage for the new batch**

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python codes/application/ui_review_server.py \
  --batch-dir ./annotation/batch_20260417_v01 \
  --init-only
```

- [ ] **Step 3: Validate the new batch is clean**

Check:

- `annotations = 0`
- `assignments = 0`
- `segment_reviews = 0`

---

### Task 6: Write The New Batch Summary Report

**Files:**
- Create: `docs/BATCH_20260417_V01_SEGMENT_SUMMARY.md`

- [ ] **Step 1: Summarize total batch metrics**

Include:

- total frames
- total segments
- stable segments
- non-simple singles
- compression rate
- compression multiple

- [ ] **Step 2: Add the per-session markdown table**

For each session include:

- frame count
- segment count
- stable count
- non-simple count
- compression rate
- compression multiple

- [ ] **Step 3: Add short interpretation notes**

Highlight:

- the most difficult sessions
- the sessions with the highest compression
- the fact that this batch is a clean derived batch

---

### Task 7: Final Verification And Git Hygiene

**Files:**
- Verify all changed docs/code

- [ ] **Step 1: Re-run full verification after batch execution**

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest discover -s codes/test
```

- [ ] **Step 2: Inspect git status**

```bash
git status --short
```

Expected:

- only intended code/doc changes are tracked
- generated batch artifacts remain untracked

- [ ] **Step 3: Commit docs for the executed batch**

```bash
git add docs/superpowers/specs/2026-04-17-segment-gap-bridge-design.md \
        docs/superpowers/plans/2026-04-17-segment-gap-bridge.md \
        docs/BATCH_20260417_V01_SEGMENT_SUMMARY.md
git commit -m "docs: record segment gap bridge design and batch summary"
```

---

## Self-Review

- Spec coverage:
  - conservative bridge behavior: covered by Tasks 1-2
  - new batch execution: covered by Tasks 4-5
  - clean review storage: covered by Task 5
  - markdown reporting: covered by Task 6
- No placeholders remain for files, commands, or verification points.
- Scope stays within one subsystem: offline segment prep plus new-batch execution.
