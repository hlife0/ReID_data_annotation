# R4C Issue-Local Frame Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let annotators move within the currently loaded issue span so issue mode supports keyframe-style browsing instead of only jumping between issues.

**Architecture:** Add one review backend API that returns the same issue payload but with a caller-selected frame inside the issue bounds. Add `Prev` / `Next` frame-in-issue controls in the issue summary strip and keep issue context while the canvas frame changes.

**Tech Stack:** Python 3, vanilla JavaScript, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codes/ui_review_server.py` — add issue-local frame payload API.
- Modify: `codes/test_ui_review_server.py` — verify navigating to another frame in the same issue.
- Modify: `codes/ui_review_web/index.html` — add issue-local prev/next controls.
- Modify: `codes/ui_review_web/app.js` — wire issue-local navigation and keep current issue state.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — update progress.

### Task 1: Add backend tests and API for issue-local frame payloads

**Files:**
- Modify: `codes/test_ui_review_server.py`
- Modify: `codes/ui_review_server.py`
- Test: `codes/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Add a test that calls `issue_frame(issue_id='sample_issue_001', frame_index=2)` and expects:
- same issue metadata
- frame payload for frame 2
- `slot_names` still present

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codes/test_ui_review_server.py`
Expected: FAIL because issue-local frame lookup does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add helper + endpoint:
- `GET /api/issue_frame?issue_id=...&frame_index=...`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codes/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_server.py codes/test_ui_review_server.py
git commit -m "Add issue-local frame review API"
```

### Task 2: Add issue-local prev/next controls in the UI

**Files:**
- Modify: `codes/ui_review_web/index.html`
- Modify: `codes/ui_review_web/app.js`
- Test: `codes/ui_review_web/app.js`

- [ ] **Step 1: Write the failing test**

Run:
```bash
rg -n "issuePrevFrameBtn|issueNextFrameBtn|loadIssueFrame|stepIssueFrame" codes/ui_review_web/index.html codes/ui_review_web/app.js
```
Expected: no matches before implementation.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --check codes/ui_review_web/app.js`
Expected: syntax passes before the hooks exist.

- [ ] **Step 3: Write minimal implementation**

Add prev/next issue-frame controls that:
- only appear in issue mode
- clamp within the issue span
- load a new frame while keeping current issue metadata

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "issuePrevFrameBtn|issueNextFrameBtn|loadIssueFrame|stepIssueFrame" codes/ui_review_web/index.html codes/ui_review_web/app.js
node --check codes/ui_review_web/app.js
```
Expected: hooks exist and syntax is valid.

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_web/index.html codes/ui_review_web/app.js
git commit -m "Add issue-local frame navigation"
```

### Task 3: Verify issue-local navigation on the formal batch

**Files:**
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: running review service + `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run:
```bash
curl -s 'http://127.0.0.1:10086/api/issue_frame?issue_id=<issue_id>&frame_index=<inside_span>'
```
Expected: FAIL before endpoint implementation.

- [ ] **Step 2: Run test to verify it fails**

After implementation, verify the response changes frame index but preserves issue context.

- [ ] **Step 3: Write minimal implementation**

Patch any bounds or payload mismatch revealed by the formal batch.

- [ ] **Step 4: Run test to verify it passes**

Run backend tests, JS syntax checks, and formal-batch issue-frame curls.

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_server.py codes/test_ui_review_server.py codes/ui_review_web/index.html codes/ui_review_web/app.js docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Verify issue-local frame navigation"
```
