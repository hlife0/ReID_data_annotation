# R4 Minimal Issue Range Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first range-level operation for issue mode so annotators can apply the current slot decisions across the whole issue span and jump to the next issue.

**Architecture:** Extend the review backend with an `submit_issue_range` path that expands one issue-level payload into many frame-level annotation records over the issue span. AI-backed slots reuse the same `track_id` and pull per-frame AI boxes; absent slots stay absent; manual boxes use the same bbox across the range for this first version. The frontend only needs one extra button to trigger the range operation in issue mode.

**Tech Stack:** Python 3, sqlite3, vanilla JavaScript, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codes/ui_review_server.py` — implement range expansion and `submit_issue_range` endpoint.
- Modify: `codes/test_ui_review_server.py` — add regression tests for range submission semantics.
- Modify: `codes/ui_review_web/index.html` — add range submit button.
- Modify: `codes/ui_review_web/app.js` — wire issue-range submit flow.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — update progress.

### Task 1: Add backend tests for issue-range submission

**Files:**
- Modify: `codes/test_ui_review_server.py`
- Modify: `codes/ui_review_server.py`
- Test: `codes/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Add a test where one issue spans frames 1-2 and the payload contains:
- `p1` with `source=ai`, `ai_track_id=11`
- `p2` with `source=absent`
Expect:
- two annotations written for the annotator across frames 1 and 2
- `p1` on frame 1 uses AI bbox from frame 1
- `p1` on frame 2 uses AI bbox from frame 2
- `p2` stays absent on both frames
- response returns `submitted_frame_count`

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codes/test_ui_review_server.py`
Expected: FAIL because range submission does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement range expansion only for the tested behaviors:
- `ai` slots track-follow per frame when the same `track_id` exists
- `absent` slots remain absent
- manual slots reuse the same bbox across the span

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codes/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_server.py codes/test_ui_review_server.py
git commit -m "Add minimal issue range submission"
```

### Task 2: Add issue-range submit control to the frontend

**Files:**
- Modify: `codes/ui_review_web/index.html`
- Modify: `codes/ui_review_web/app.js`
- Test: `codes/ui_review_web/app.js`

- [ ] **Step 1: Write the failing test**

Run:
```bash
rg -n "submitIssueRangeBtn|submit_issue_range|submitIssueRange" codes/ui_review_web/index.html codes/ui_review_web/app.js
```
Expected: no matches before implementation.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --check codes/ui_review_web/app.js`
Expected: syntax passes while range-submit hooks are absent.

- [ ] **Step 3: Write minimal implementation**

Add one extra issue-mode button:
- visible/usable in issue mode
- posts current payload to `/api/submit_issue_range`
- loads returned `next_issue`

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "submitIssueRangeBtn|submit_issue_range|submitIssueRange" codes/ui_review_web/index.html codes/ui_review_web/app.js
node --check codes/ui_review_web/app.js
```
Expected: hooks exist and JS syntax is valid.

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_web/index.html codes/ui_review_web/app.js
git commit -m "Add issue range apply control"
```

### Task 3: Verify issue-range submission on the formal batch

**Files:**
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: running review service + `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run:
```bash
curl -s http://127.0.0.1:10086/api/submit_issue_range -X POST -H 'Content-Type: application/json' -d '{}'
```
Expected: FAIL before the endpoint is implemented.

- [ ] **Step 2: Run test to verify it fails**

After implementation, use a real issue from `next_issue`, submit a minimal valid range payload, and inspect the response.

- [ ] **Step 3: Write minimal implementation**

Fix any real-data mismatches uncovered by the formal batch.

- [ ] **Step 4: Run test to verify it passes**

Run backend tests, JS syntax checks, and a formal-batch `submit_issue_range` smoke test.

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_server.py codes/test_ui_review_server.py codes/ui_review_web/index.html codes/ui_review_web/app.js docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Verify minimal range apply workflow"
```
