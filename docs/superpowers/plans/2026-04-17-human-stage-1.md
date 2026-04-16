# Human Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `human_stage_1` pipeline that keeps the existing review UI untouched, reuses current first-pass segmentation, adds second-pass `repair_window` merges, and serves a coarse-labeling UI where annotators only choose `ai_match / absent / needs_manual` on a single frame per segment.

**Architecture:** Add a new offline prep script that first reproduces the current `stable_segment + non_simple_single_frame` output, then merges contiguous fragment runs into `repair_window` records and writes dedicated `human_stage_1_prep/` artifacts. Add a new `ui_human_stage_1_server.py` plus `ui_human_stage_1_web/` that read only the new prep artifacts and store coarse decisions in stage-1-specific storage, with no hand-draw support and no changes to the existing `ui_review_server.py` or `ui_review_web/` stack.

**Tech Stack:** Python 3, `unittest`, SQLite, vanilla JS/HTML/CSS, existing `codes/process` and `codes/application` patterns

---

## File Structure

### New files

- `codes/process/process_human_stage_1_prep.py`
  Purpose: Run stage-1 prep by invoking the current first-pass segmentation logic, then applying second-pass `repair_window` merges and exporting `human_stage_1_prep/` artifacts.

- `codes/application/ui_human_stage_1_server.py`
  Purpose: Serve only first-pass coarse-labeling tasks from `human_stage_1_prep/` and persist `ai_match / absent / needs_manual` decisions.

- `codes/application/ui_human_stage_1_web/index.html`
  Purpose: First-pass coarse-labeling page with no draw controls and only the three slot decisions.

- `codes/application/ui_human_stage_1_web/app.js`
  Purpose: Frontend state machine for assigning AI boxes, marking `absent`, or marking `needs_manual` on one frame.

- `codes/application/ui_human_stage_1_web/styles.css`
  Purpose: Styling for the new stage-1 UI.

- `codes/test/test_process_human_stage_1_prep.py`
  Purpose: Verify first-pass/second-pass prep behavior and exported stage-1 artifacts.

- `codes/test/test_ui_human_stage_1_server.py`
  Purpose: Verify stage-1 server payloads, storage layout, and coarse-decision persistence.

- `codes/test/test_ui_human_stage_1_web_static.py`
  Purpose: Static assertions that the new frontend exposes only the intended coarse-labeling affordances.

### Existing files to reference, not mutate unless required

- `codes/process/process_segment_review_prep.py`
  Purpose: Existing first-pass segmentation source of truth. New prep must reuse its first-pass behavior rather than replace it.

- `codes/process/segment_prep_common.py`
  Purpose: Shared task/detection loading helpers.

- `codes/application/ui_review_server.py`
  Purpose: Existing review implementation. Must remain semantically unchanged.

- `codes/application/ui_review_web/`
  Purpose: Existing review frontend. Must remain semantically unchanged.

---

### Task 1: Lock the first-pass → second-pass prep contract with failing tests

**Files:**
- Create: `codes/test/test_process_human_stage_1_prep.py`
- Reference: `codes/process/process_segment_review_prep.py`
- Reference: `docs/superpowers/specs/2026-04-17-first-pass-coarse-labeling-design.md`

- [ ] **Step 1: Write the failing test for first-pass parity before repair-window merging**

Add a fixture batch in `codes/test/test_process_human_stage_1_prep.py` that writes timestamps, pseudo labels, and a manifest for a small sample video. Write a test named:

```python
def test_human_stage_1_prep_preserves_first_pass_segments_before_second_pass_merge(self):
    ...
```

The test should assert that the new prep can expose both:
- the raw first-pass `stable_segment + non_simple_single_frame` breakdown
- the final stage-1 merged output

It should fail because `process_human_stage_1_prep.py` does not exist yet.

- [ ] **Step 2: Run the targeted parity test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_human_stage_1_prep.HumanStage1PrepTests.test_human_stage_1_prep_preserves_first_pass_segments_before_second_pass_merge -v
```

Expected: FAIL with import or missing-module error for `process_human_stage_1_prep`.

- [ ] **Step 3: Write the failing test for second-pass-only repair-window creation**

In the same file, add a test named:

```python
def test_human_stage_1_prep_creates_repair_window_only_from_first_pass_fragments(self):
    ...
```

The test should build a sample where the current first-pass would yield:
- one or more `stable_segment`
- several contiguous `non_simple_single_frame`

Then assert that the stage-1 output contains a `repair_window` whose frame span overlaps only those contiguous first-pass fragments and does not bypass the first-pass decomposition.

- [ ] **Step 4: Run the targeted repair-window test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_human_stage_1_prep.HumanStage1PrepTests.test_human_stage_1_prep_creates_repair_window_only_from_first_pass_fragments -v
```

Expected: FAIL because the new prep logic does not exist yet.

- [ ] **Step 5: Write the failing test for exported stage-1 prep layout**

Add a third test named:

```python
def test_human_stage_1_prep_writes_human_stage_1_artifacts(self):
    ...
```

Assert that a successful prep run writes:
- `human_stage_1_prep/<video_stem>.segments.json`
- `human_stage_1_prep/<video_stem>.segment_frames.json`
- `human_stage_1_prep/human_stage_1_prep_summary.json`

and that the summary includes counts for:
- `stable_segment_count`
- `non_simple_single_frame_count`
- `repair_window_count`

- [ ] **Step 6: Run the full new prep test module to verify all tests fail**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_human_stage_1_prep -v
```

Expected: FAIL with missing implementation.

- [ ] **Step 7: Commit the red prep tests**

```bash
git add codes/test/test_process_human_stage_1_prep.py
git commit -m "test: add human stage 1 prep contract coverage"
```

### Task 2: Implement `process_human_stage_1_prep.py`

**Files:**
- Create: `codes/process/process_human_stage_1_prep.py`
- Modify: `codes/test/test_process_human_stage_1_prep.py`
- Reference: `codes/process/process_segment_review_prep.py`
- Reference: `codes/process/segment_prep_common.py`

- [ ] **Step 1: Implement the new prep module skeleton**

Create `codes/process/process_human_stage_1_prep.py` with:
- CLI arg parsing for `--batch-dir`
- a public `run_human_stage_1_prep(batch_dir: Path) -> Dict[str, Any]`
- imports from `process_segment_review_prep` so first-pass behavior is reused rather than redefined

Use this minimal structure:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from process import process_segment_review_prep as base_prep
from process import segment_prep_common as common


def run_human_stage_1_prep(batch_dir: Path) -> Dict[str, Any]:
    ...


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare human_stage_1 artifacts")
    parser.add_argument("--batch-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_human_stage_1_prep(args.batch_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Implement first-pass reuse and second-pass merge output**

In `run_human_stage_1_prep`, do the following:
- load tasks from the batch manifest
- load detections per task
- invoke the current first-pass segment builder from `process_segment_review_prep.py`
- derive final stage-1 segment output where `repair_window` is created only after first-pass segments are known
- write `human_stage_1_prep/` JSON artifacts

The implementation may call existing helper functions from `process_segment_review_prep.py`, but it must not modify existing review artifacts under `segment_prep/`.

- [ ] **Step 3: Include first-pass trace information in the prep output**

Ensure the stage-1 segment records include enough metadata to prove provenance from first-pass segmentation, for example:
- `source_segment_types`
- `source_segment_ids`
- or equivalent explicit trace fields

This is required so the second-pass contract is inspectable in tests and future debugging.

- [ ] **Step 4: Run the new prep tests to verify they pass**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_human_stage_1_prep -v
```

Expected: PASS.

- [ ] **Step 5: Run the existing segment-prep tests to verify no regression**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_segment_review_prep -v
```

Expected: PASS.

- [ ] **Step 6: Commit the prep implementation**

```bash
git add codes/process/process_human_stage_1_prep.py \
  codes/test/test_process_human_stage_1_prep.py
git commit -m "feat: add human stage 1 prep pipeline"
```

### Task 3: Lock the independent stage-1 server behavior with failing tests

**Files:**
- Create: `codes/test/test_ui_human_stage_1_server.py`
- Reference: `codes/application/ui_human_stage_1_server.py`

- [ ] **Step 1: Write the failing test for loading only `human_stage_1_prep/` artifacts**

Create `codes/test/test_ui_human_stage_1_server.py` and add a test named:

```python
def test_human_stage_1_server_reads_human_stage_1_prep_only(self):
    ...
```

Build a temporary batch fixture containing:
- valid `human_stage_1_prep/` files
- intentionally divergent `segment_prep/` files

Assert that the new server loads the stage-1 prep payload and ignores the old review prep files.

- [ ] **Step 2: Run the targeted read-source test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_human_stage_1_server.HumanStage1ServerTests.test_human_stage_1_server_reads_human_stage_1_prep_only -v
```

Expected: FAIL because `ui_human_stage_1_server.py` does not exist yet.

- [ ] **Step 3: Write the failing test for first-pass coarse payload semantics**

Add a test named:

```python
def test_human_stage_1_server_returns_single_frame_coarse_task_payload(self):
    ...
```

Assert that:
- `stable_segment` returns only its representative frame
- `repair_window` returns only its middle frame
- the payload exposes only the three decision affordances
- no manual-draw affordance is present in the returned schema

- [ ] **Step 4: Write the failing test for coarse-decision persistence**

Add a test named:

```python
def test_human_stage_1_server_persists_ai_match_absent_needs_manual(self):
    ...
```

Assert that the server can store one submission where different slots use:
- `ai_match`
- `absent`
- `needs_manual`

and that the stored row preserves `segment_id`, `frame_index`, and `segment_type`.

- [ ] **Step 5: Run the full new server test module to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_human_stage_1_server -v
```

Expected: FAIL with missing implementation.

- [ ] **Step 6: Commit the red server tests**

```bash
git add codes/test/test_ui_human_stage_1_server.py
git commit -m "test: add human stage 1 server coverage"
```

### Task 4: Implement `ui_human_stage_1_server.py`

**Files:**
- Create: `codes/application/ui_human_stage_1_server.py`
- Modify: `codes/test/test_ui_human_stage_1_server.py`
- Reference: `codes/application/ui_review_server.py`

- [ ] **Step 1: Implement server bootstrap and stage-1 storage layout**

Create `codes/application/ui_human_stage_1_server.py` by reusing only the infrastructure patterns from `ui_review_server.py`:
- static file serving
- JPEG frame loading
- manifest loading
- SQLite setup

But use stage-1-specific storage paths under:
- `batch_dir / "human_stage_1" / "ui_human_stage_1.sqlite3"`
- `batch_dir / "human_stage_1" / "coarse_labels_raw"`
- `batch_dir / "human_stage_1" / "coarse_labels_export"`

Do not import or reuse the review submission schema directly.

- [ ] **Step 2: Implement segment loading from `human_stage_1_prep/`**

Load only stage-1 prep artifacts and expose a segment payload with:
- `segment_id`
- `segment_type`
- the single frame to label
- visible AI boxes on that frame
- slot names `p1..p7`
- allowed decisions: `ai_match`, `absent`, `needs_manual`

- [ ] **Step 3: Implement coarse-decision validation and storage**

Accept payloads shaped like:

```json
{
  "segment_id": "...",
  "video_stem": "...",
  "frame_index": 123,
  "slot_decisions": [
    {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"},
    {"slot": "p2", "decision_type": "absent", "ai_track_id": ""},
    {"slot": "p3", "decision_type": "needs_manual", "ai_track_id": ""}
  ]
}
```

Validate:
- only the three decision types are accepted
- `ai_match` must point to a visible AI track on that frame
- `absent` and `needs_manual` must have empty `ai_track_id`
- duplicate AI-track assignment across slots is rejected

- [ ] **Step 4: Run the new server tests to verify they pass**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_human_stage_1_server -v
```

Expected: PASS.

- [ ] **Step 5: Run existing review-server tests to verify no regression**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_segment_review_server -v
```

Expected: PASS.

- [ ] **Step 6: Commit the stage-1 server implementation**

```bash
git add codes/application/ui_human_stage_1_server.py \
  codes/test/test_ui_human_stage_1_server.py
git commit -m "feat: add human stage 1 server"
```

### Task 5: Lock and implement the independent `ui_human_stage_1_web/` frontend

**Files:**
- Create: `codes/application/ui_human_stage_1_web/index.html`
- Create: `codes/application/ui_human_stage_1_web/app.js`
- Create: `codes/application/ui_human_stage_1_web/styles.css`
- Create: `codes/test/test_ui_human_stage_1_web_static.py`
- Reference: `codes/application/ui_review_web/`

- [ ] **Step 1: Write the failing static test for stage-1 UI affordances**

Create `codes/test/test_ui_human_stage_1_web_static.py` with a test named:

```python
def test_human_stage_1_ui_exposes_only_three_coarse_actions(self):
    ...
```

Assert that the new HTML/JS include:
- controls for `ai_match`
- controls for `absent`
- controls for `needs_manual`

and explicitly do **not** include:
- draw-new-box controls
- bbox numeric editors
- manual resize/edit affordances

- [ ] **Step 2: Run the static UI test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_human_stage_1_web_static -v
```

Expected: FAIL because the new UI files do not exist yet.

- [ ] **Step 3: Implement the minimal stage-1 frontend**

Create the new HTML/JS/CSS stack with these behaviors only:
- request next stage-1 segment
- render the single assigned frame and AI boxes
- let each slot choose exactly one of:
  - visible AI track
  - absent
  - needs_manual
- submit the coarse decision payload to the new server

Do not copy over draw/edit history functionality from `ui_review_web/` unless needed to make the new flow usable.

- [ ] **Step 4: Run the static UI test and JS syntax verification**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_human_stage_1_web_static -v
node --check codes/application/ui_human_stage_1_web/app.js
```

Expected: PASS.

- [ ] **Step 5: Commit the stage-1 frontend**

```bash
git add codes/application/ui_human_stage_1_web/index.html \
  codes/application/ui_human_stage_1_web/app.js \
  codes/application/ui_human_stage_1_web/styles.css \
  codes/test/test_ui_human_stage_1_web_static.py
git commit -m "feat: add human stage 1 web client"
```

### Task 6: Full verification and plan/spec alignment review

**Files:**
- Modify: `codes/process/process_human_stage_1_prep.py`
- Modify: `codes/application/ui_human_stage_1_server.py`
- Modify: `codes/application/ui_human_stage_1_web/*`
- Modify: `codes/test/test_process_human_stage_1_prep.py`
- Modify: `codes/test/test_ui_human_stage_1_server.py`
- Modify: `codes/test/test_ui_human_stage_1_web_static.py`

- [ ] **Step 1: Run the full automated Python test suite**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest discover -s codes/test
```

Expected: PASS with `0` failures.

- [ ] **Step 2: Run all relevant JS syntax checks**

Run:

```bash
node --check codes/application/ui_human_stage_1_web/app.js
node --check codes/application/ui_review_web/app.js
node --check codes/application/ui_admin_web/app.js
```

Expected: all exit `0`.

- [ ] **Step 3: Verify the untouched-review guarantee**

Run:

```bash
git diff --stat origin/main -- codes/application/ui_review_server.py codes/application/ui_review_web
```

Expected: no semantic changes to the existing review stack for this feature.

- [ ] **Step 4: Review plan/spec coverage manually**

Confirm the implementation covers:
- first-pass segmentation runs before any `repair_window`
- `repair_window` is second-pass only
- stage-1 has its own server, frontend, and storage
- first-pass UI exposes only `ai_match / absent / needs_manual`
- no manual box drawing in stage 1

- [ ] **Step 5: Commit any final verification-only adjustments**

```bash
git status --short
# If verification required tiny fixes, stage and commit them now.
```

- [ ] **Step 6: Prepare for branch completion**

After all verification passes, use `verification-before-completion` principles before making any success claim.
