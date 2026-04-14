# R3 Issue-Mode Review Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let annotators work in issue-mode from the existing review UI by loading the next issue, seeing issue metadata, and submitting annotations back into the issue queue.

**Architecture:** Keep the large-canvas review page, add a lightweight issue status strip and a `Next Issue` action, and extend the backend with an issue-aware submit path so the UI can stay in issue mode end-to-end.

**Tech Stack:** Python 3, vanilla JavaScript, HTML/CSS, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codex/ui_review_server.py` — add issue-aware submit endpoint built on the existing annotation insertion path.
- Modify: `codex/test_ui_review_server.py` — verify submit-next-issue behavior.
- Modify: `codex/ui_review_web/index.html` — add issue-mode controls and issue summary strip.
- Modify: `codex/ui_review_web/app.js` — add issue-mode state, request/submit flow, and summary rendering.
- Modify: `codex/ui_review_web/styles.css` — style the issue summary strip without shrinking the main canvas.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — mark R3 progress.

### Task 1: Add issue-aware submit behavior in the backend

**Files:**
- Modify: `codex/ui_review_server.py`
- Modify: `codex/test_ui_review_server.py`
- Test: `codex/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Extend `codex/test_ui_review_server.py` with a test that submits one annotation in issue mode and expects an `next_issue` payload instead of `next_frame`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: FAIL because issue-aware submit does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a shared submit helper and a new issue-aware endpoint/method so issue mode can stay on issue navigation after save.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py
git commit -m "Add issue-aware review submit flow"
```

### Task 2: Connect the review frontend to issue mode

**Files:**
- Modify: `codex/ui_review_web/index.html`
- Modify: `codex/ui_review_web/app.js`
- Modify: `codex/ui_review_web/styles.css`
- Test: `codex/ui_review_web/app.js`

- [ ] **Step 1: Write the failing test**

Run:
```bash
rg -n "nextIssueBtn|issueSummary|issueBadge|issueReasonList" codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css
```
Expected: no matches before implementation.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
node --check codex/ui_review_web/app.js
```
Expected: JS syntax passes before implementation while issue-mode UI hooks are still absent.

- [ ] **Step 3: Write minimal implementation**

Add:
- a `Next Issue` button
- a compact issue summary strip
- front-end state for `currentIssue` and `dispatchMode`
- `requestNextIssue()` and issue-aware submit handling
- clear transitions between frame mode and issue mode

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "nextIssueBtn|issueSummary|issueBadge|issueReasonList" codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css
node --check codex/ui_review_web/app.js
```
Expected: issue-mode hooks exist and JS syntax is valid.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css
git commit -m "Connect review UI to issue mode"
```

### Task 3: Verify issue-mode end-to-end on the formal batch

**Files:**
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: running review service + `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run:
```bash
curl -s http://127.0.0.1:10086/api/submit_issue -X POST -H 'Content-Type: application/json' -d '{}'
```
Expected: FAIL before the endpoint is implemented.

- [ ] **Step 2: Run test to verify it fails**

After implementation, exercise:
```bash
curl -s http://127.0.0.1:10086/api/next_issue -X POST -H 'Content-Type: application/json' -d '{"annotator_id":"annotator_issue_ui"}'
```
Capture an issue and submit a minimal valid payload to `submit_issue`.

- [ ] **Step 3: Write minimal implementation**

Fix any payload mismatch or mode transition bug uncovered by the formal batch smoke test.

- [ ] **Step 4: Run test to verify it passes**

Run backend tests, JS syntax checks, and issue-mode curl smoke tests against the formal batch.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Verify issue mode end-to-end on review UI"
```
