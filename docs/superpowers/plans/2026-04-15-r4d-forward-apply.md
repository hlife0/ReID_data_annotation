# R4D Forward Range Apply From Current Frame Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let annotators apply the current slot decisions from the current frame forward to the end of the current issue, creating a first keyframe-style partial propagation workflow.

**Architecture:** Reuse the existing issue-range expansion logic, but let the caller supply a subrange inside the issue. Add one new backend endpoint and one frontend action button for "apply from here to issue end". Keep the current full-issue range apply untouched.

**Tech Stack:** Python 3, vanilla JavaScript, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codex/ui_review_server.py` — add partial issue range submission helper.
- Modify: `codex/test_ui_review_server.py` — verify partial forward range submission semantics.
- Modify: `codex/ui_review_web/index.html` — add forward apply button.
- Modify: `codex/ui_review_web/app.js` — wire forward apply flow in issue mode.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — update progress.

### Task 1: Add backend tests for partial forward range submission

**Files:**
- Modify: `codex/test_ui_review_server.py`
- Modify: `codex/ui_review_server.py`
- Test: `codex/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Add a test where issue `sample_issue_001` spans frames 1-2, but the partial submit starts at frame 2 and ends at frame 2. Expect exactly one annotation record to be created.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: FAIL because partial issue range submission does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement one backend path for `submit_issue_partial_range(issue_id, start_frame, end_frame, payload)` with clamped frame bounds inside the issue.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py
git commit -m "Add partial issue range submission"
```

### Task 2: Add a forward-apply control in the issue UI

**Files:**
- Modify: `codex/ui_review_web/index.html`
- Modify: `codex/ui_review_web/app.js`
- Test: `codex/ui_review_web/app.js`

- [ ] **Step 1: Write the failing test**

Run:
```bash
rg -n "submitIssueForwardBtn|submit_issue_partial_range|submitIssueForwardRange" codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_server.py
```
Expected: no matches before implementation.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --check codex/ui_review_web/app.js`
Expected: syntax passes while forward-apply hooks are absent.

- [ ] **Step 3: Write minimal implementation**

Add one extra button for issue mode:
- “从当前帧向后应用”
- sends `issue_id`, `start_frame=current_frame`, `end_frame=issue.end_frame`
- loads the returned next issue or keeps current issue if applicable

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "submitIssueForwardBtn|submit_issue_partial_range|submitIssueForwardRange" codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_server.py
node --check codex/ui_review_web/app.js
```
Expected: hooks exist and syntax is valid.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_server.py
git commit -m "Add forward apply control for issue mode"
```

### Task 3: Verify partial forward range apply on the formal batch

**Files:**
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: review service + `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run a real issue payload through the new partial-range endpoint using `start_frame=current frame`.

- [ ] **Step 2: Run test to verify it fails**

Before implementation the endpoint does not exist.

- [ ] **Step 3: Write minimal implementation**

Patch any real-data mismatch found on the formal batch.

- [ ] **Step 4: Run test to verify it passes**

Run backend tests, JS syntax checks, and a formal-batch partial-range smoke test.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py codex/ui_review_web/index.html codex/ui_review_web/app.js docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Verify forward apply workflow on formal batch"
```
