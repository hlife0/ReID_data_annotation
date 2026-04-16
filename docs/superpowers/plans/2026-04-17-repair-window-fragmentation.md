# Repair Window Fragmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative `repair_window` workflow that reduces severe segment fragmentation by grouping short, repairable fragment clusters into short windows with anchor labeling, auto-fill, and fallback.

**Architecture:** Keep the existing first-pass `stable_segment` / `non_simple_single_frame` pipeline intact, then run a second-pass fragment scan that may replace local fragment clusters with `repair_window` entries. Extend the review server to serve and submit `repair_window` segments, using short-window anchor labeling plus conservative slot filling and fallback. Update the web client to guide annotators through anchor frames and final confirmation without changing the core slot editing model.

**Tech Stack:** Python 3, `unittest`, SQLite, vanilla JS, existing review server/client stack

---

### Task 1: Add failing tests for offline repair-window detection

**Files:**
- Modify: `codes/test/test_process_segment_review_prep.py`
- Reference: `codes/process/process_segment_review_prep.py`

- [ ] **Step 1: Write the failing test for repair-window generation from fragmented clusters**

Add a new test case in `codes/test/test_process_segment_review_prep.py` that builds a synthetic pseudo-label session where a `<= 10` frame region is fragmented into multiple single-frame and micro-stable segments with nearly constant track sets. Assert that the new prep output contains one `repair_window` entry covering the full fragmented region instead of multiple tiny work units.

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_segment_review_prep.SegmentReviewPrepTests.test_segment_prep_emits_repair_window_for_short_repairable_fragment_cluster -v
```

Expected: FAIL because `repair_window` does not exist yet.

- [ ] **Step 3: Write the failing test for rejecting non-repairable clusters**

Add a second test that uses a similarly short fragmented region but injects a hard-break pattern, such as repeated `both`, large track-set changes, or a long `overlap_only` run. Assert that the output stays as the original `stable_segment` / `non_simple_single_frame` sequence and never emits `repair_window`.

- [ ] **Step 4: Run the targeted rejection test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_segment_review_prep.SegmentReviewPrepTests.test_segment_prep_keeps_non_repairable_fragment_cluster_split -v
```

Expected: FAIL because the rejection/selection logic does not exist yet.

- [ ] **Step 5: Commit the red tests**

```bash
git add codes/test/test_process_segment_review_prep.py
git commit -m "test: cover repair window segment prep selection"
```

### Task 2: Implement second-pass repair-window scanning in segment prep

**Files:**
- Modify: `codes/process/process_segment_review_prep.py`
- Modify: `codes/test/test_process_segment_review_prep.py`

- [ ] **Step 1: Implement frame feature capture and repair-window candidate selection**

In `codes/process/process_segment_review_prep.py`, add internal helpers to:

- capture per-frame descriptors needed for fragment scanning
- build first-pass segments as today
- scan those segments for short fragment clusters
- score candidates using the thresholds from the spec
- greedily select non-overlapping `repair_window` regions

Keep the original first-pass behavior intact when no candidate qualifies.

- [ ] **Step 2: Extend exported segment payloads**

Update the emitted `segments.json` payload so that `repair_window` entries include:

- `segment_type`
- `anchor_candidates`
- `repairability_score`
- `fragmentation_score`
- `expected_gain`
- `trigger_reason`

Also ensure `frame_to_segment` maps all covered frames to the final selected `repair_window` id.

- [ ] **Step 3: Run the focused segment-prep tests**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_process_segment_review_prep -v
```

Expected: PASS.

- [ ] **Step 4: Refactor only if needed while keeping tests green**

If `process_segment_review_prep.py` becomes unwieldy, extract small internal helpers within the same file rather than broad file churn. Re-run the focused tests after any cleanup.

- [ ] **Step 5: Commit the offline implementation**

```bash
git add codes/process/process_segment_review_prep.py codes/test/test_process_segment_review_prep.py
git commit -m "feat: add repair window fragment scanning"
```

### Task 3: Add failing tests for review-server repair-window semantics

**Files:**
- Modify: `codes/test/test_segment_review_server.py`
- Reference: `codes/application/ui_review_server.py`

- [ ] **Step 1: Write the failing test for serving a repair-window payload**

Add a test fixture that loads a `repair_window` segment from synthetic `segment_prep` data and asserts that `assign_next_segment()` returns:

- `segment_type = repair_window`
- a populated `anchor_frames` or equivalent anchor metadata payload
- the first anchor frame as the current editable frame

- [ ] **Step 2: Run the targeted payload test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_segment_review_server.SegmentReviewServerTests.test_repair_window_payload_includes_anchor_sequence -v
```

Expected: FAIL because the server does not yet understand `repair_window`.

- [ ] **Step 3: Write the failing test for repair-window submission and fill**

Add a test that submits anchor annotations for a short repair window where both endpoints reference the same tracks, then asserts:

- the server writes frame-level annotations for every frame in the window
- filled intermediate frames use conservative propagated sources
- the segment is marked resolved

- [ ] **Step 4: Write the failing test for repair-window fallback**

Add a test where a required track disappears in an intermediate frame, or where anchor constraints conflict. Assert that the server refuses unsafe fill and returns a fallback signal instead of silently writing invalid propagated rows.

- [ ] **Step 5: Run the server repair-window tests to verify they fail**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_segment_review_server -v
```

Expected: FAIL in the newly added repair-window tests.

- [ ] **Step 6: Commit the red server tests**

```bash
git add codes/test/test_segment_review_server.py
git commit -m "test: cover repair window review server flow"
```

### Task 4: Implement repair-window server fill and fallback

**Files:**
- Modify: `codes/application/ui_review_server.py`
- Modify: `codes/test/test_segment_review_server.py`

- [ ] **Step 1: Extend server segment loading and payload building**

Update `codes/application/ui_review_server.py` so `SegmentRecord` and segment loading preserve repair-window metadata. Extend `_segment_payload()` to emit repair-window-specific fields, including ordered anchor frame metadata and the current anchor index.

- [ ] **Step 2: Add server-side repair-window submission flow**

Implement a dedicated repair-window submission path that:

- accepts anchor slot payloads
- validates anchor coverage and ordering
- fills non-anchor frames conservatively
- writes frame-level `annotations`
- records provenance for filled slots
- marks the segment resolved on success

- [ ] **Step 3: Add repair-window fallback handling**

Implement bounded fallback semantics:

- if safe fill is impossible, return structured fallback information
- allow at most one extra anchor frame
- if fill still fails, split or reject the window rather than writing unsafe rows

Do not silently coerce a failed repair window into a normal stable segment.

- [ ] **Step 4: Run the focused server tests**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_segment_review_server -v
```

Expected: PASS.

- [ ] **Step 5: Commit the server implementation**

```bash
git add codes/application/ui_review_server.py codes/test/test_segment_review_server.py
git commit -m "feat: add repair window review execution"
```

### Task 5: Add failing client tests/checks and implement repair-window UI flow

**Files:**
- Modify: `codes/application/ui_review_web/app.js`
- Modify: `codes/test/test_ui_review_server.py`
- Reference: `codes/test/test_ui_review_web_static.py`

- [ ] **Step 1: Write the failing backend-facing test for repair-window API expectations**

Extend `codes/test/test_ui_review_server.py` or the nearest existing UI-review test to assert that repair-window responses expose the fields the client needs:

- ordered anchors
- current anchor index
- total anchor count
- final confirmation behavior

- [ ] **Step 2: Run the targeted UI-server test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_review_server -v
```

Expected: FAIL because repair-window UI fields are not yet wired.

- [ ] **Step 3: Implement minimal client flow for anchor progression**

Update `codes/application/ui_review_web/app.js` to:

- recognize `repair_window`
- show progress through anchor frames
- preserve slot editing behavior per anchor
- submit anchor payloads and accept final preview/confirmation
- avoid changing the existing stable/non-simple flows

Keep the interaction intentionally narrow: no timeline editor, no unbounded anchor count.

- [ ] **Step 4: Run syntax and UI-adjacent tests**

Run:

```bash
node --check codes/application/ui_review_web/app.js
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.test_ui_review_server -v
```

Expected: PASS.

- [ ] **Step 5: Commit the client implementation**

```bash
git add codes/application/ui_review_web/app.js codes/test/test_ui_review_server.py
git commit -m "feat: add repair window client workflow"
```

### Task 6: Full verification and shadow-evaluation wiring

**Files:**
- Modify: `codes/test/test_process_segment_review_prep.py`
- Modify: `codes/test/test_segment_review_server.py`
- Modify: `codes/test/test_ui_review_server.py`
- Modify: `codes/process/process_segment_review_prep.py`
- Modify: `codes/application/ui_review_server.py`
- Modify: `codes/application/ui_review_web/app.js`

- [ ] **Step 1: Run the full automated test suite**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest discover -s codes/test
```

Expected: PASS with `0` failures.

- [ ] **Step 2: Run JS syntax verification**

Run:

```bash
node --check codes/application/ui_review_web/app.js
node --check codes/application/ui_admin_web/app.js
```

Expected: both exit `0`.

- [ ] **Step 3: Review diff for plan/spec alignment**

Manually compare the implementation against:

- `docs/superpowers/specs/2026-04-17-repair-window-fragmentation-design.md`
- this plan

Confirm the delivered behavior includes:

- second-pass fragment scan
- `repair_window` segment type
- anchor labeling flow
- conservative fill
- bounded fallback

- [ ] **Step 4: Create the final implementation commit if needed**

```bash
git status --short
git add codes/process/process_segment_review_prep.py \
  codes/application/ui_review_server.py \
  codes/application/ui_review_web/app.js \
  codes/test/test_process_segment_review_prep.py \
  codes/test/test_segment_review_server.py \
  codes/test/test_ui_review_server.py
git commit -m "feat: implement repair window fragmentation reduction"
```

- [ ] **Step 5: Prepare for branch completion**

After all verification passes, use `verification-before-completion` principles before making any success claim.
