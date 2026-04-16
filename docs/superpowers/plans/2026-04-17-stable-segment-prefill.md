# Segment Prefill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add history-based per-segment recommendations in the backend and auto-prefill the recommended AI boxes in the review UI.

**Architecture:** Compute recommendations directly from existing `annotations.slots_json` per `video_stem`, return them in the existing `frame.recommendations` payload for any segment, and let the browser auto-apply them when a segment is opened. Reuse current slot state shape and current `source = ai` semantics.

**Tech Stack:** Python, sqlite3, JSON, vanilla JavaScript, unittest

---

## File Map

- Modify: `codes/application/ui_review_server.py`
- Modify: `codes/application/ui_review_web/app.js`
- Modify: `codes/test/test_segment_review_server.py`
- Create: `docs/superpowers/specs/2026-04-17-stable-segment-prefill-design.md`
- Create: `docs/superpowers/plans/2026-04-17-stable-segment-prefill.md`

---

### Task 1: Add Backend Failing Tests

**Files:**
- Modify: `codes/test/test_segment_review_server.py`
- Test: `codes/test/test_segment_review_server.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

- stable segment payload includes recommendations from annotation history
- ambiguous history ties do not emit a recommendation
- non-simple segment payload also includes recommendations

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_segment_review_server
```

Expected:

- FAIL because `recommendations` are still empty

- [ ] **Step 3: Commit**

```bash
git add codes/test/test_segment_review_server.py
git commit -m "test: cover stable segment prefill recommendations"
```

---

### Task 2: Implement Backend Recommendation Generation

**Files:**
- Modify: `codes/application/ui_review_server.py`
- Test: `codes/test/test_segment_review_server.py`

- [ ] **Step 1: Add history vote aggregation helpers**

Implement helpers that:

- read same-video historical annotations
- parse `slots_json`
- count `ai_track_id -> slot`

- [ ] **Step 2: Build deterministic recommendation candidates**

Return recommendations only when:

- best slot is unique
- slot/track assignment stays one-to-one

- [ ] **Step 3: Attach recommendations to all segment payloads**

Reuse the same history logic for both stable and non-simple segments.

- [ ] **Step 4: Run tests to verify green**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest codes.test.test_segment_review_server
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add codes/application/ui_review_server.py codes/test/test_segment_review_server.py
git commit -m "feat: add stable segment recommendation payloads"
```

---

### Task 3: Implement Frontend Auto-Prefill

**Files:**
- Modify: `codes/application/ui_review_web/app.js`

- [ ] **Step 1: Add a quiet AI-apply helper**

Refactor the existing AI apply path so recommendations can populate slots without toast spam.

- [ ] **Step 2: Auto-apply recommendations on segment load**

Only do this after:

- `ai_boxes` are loaded
- slots have been reset

- [ ] **Step 3: Run syntax verification**

Run:

```bash
node --check codes/application/ui_review_web/app.js
```

Expected:

- exit 0

- [ ] **Step 4: Commit**

```bash
git add codes/application/ui_review_web/app.js
git commit -m "feat: auto-prefill stable segment recommendations"
```

---

### Task 4: Run Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run full Python suite**

```bash
PYTHONPATH=codes .venv/bin/python -m unittest discover -s codes/test
```

- [ ] **Step 2: Run JS syntax checks**

```bash
node --check codes/application/ui_review_web/app.js
node --check codes/application/ui_admin_web/app.js
node --check codes/application/ui_review_result_web/app.js
```

- [ ] **Step 3: Inspect git status**

```bash
git status --short
```

---

## Self-Review

- Spec coverage:
  - backend recommendation generation: Task 2
  - all-segment auto-prefill: Task 3
  - verification: Task 4
- No placeholders remain for files or commands.
- Scope stays intentionally small: no DB schema changes, no auto-submit.
