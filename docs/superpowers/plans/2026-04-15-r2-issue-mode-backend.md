# R2 Issue-Mode Review Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the review backend to consume `review_prep/issue_pool` and expose issue-based assignment/detail APIs alongside the existing frame APIs.

**Architecture:** Extend `AnnotationState` with issue-pool loading and in-memory issue dispatch, keeping frame-mode untouched. Add `/api/next_issue` and `/api/issue_detail` that return issue metadata plus a focus-frame payload compatible with the current front-end frame shape.

**Tech Stack:** Python 3, sqlite3, csv, json, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codex/ui_review_server.py` — add issue dataclass/loading, assignment helpers, and new HTTP handlers.
- Modify: `codex/test_ui_review_server.py` — add backend regression tests for issue loading and issue payload shape.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — mark R2 progress once issue APIs exist.

### Task 1: Add failing tests for issue-pool loading and assignment

**Files:**
- Modify: `codex/test_ui_review_server.py`
- Modify: `codex/ui_review_server.py`
- Test: `codex/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Add a second test that:
- creates a tiny `review_prep/sample.issue_pool.csv`
- initializes `AnnotationState`
- verifies issue pool loads
- verifies `next_issue()` returns issue metadata plus a frame payload with `slot_names`
- verifies `issue_detail()` resolves by `issue_id`

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: FAIL because issue-mode state/helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement only the minimum backend behavior needed to load issue rows and return issue payloads.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py
git commit -m "Add issue-mode review backend APIs"
```

### Task 2: Verify issue APIs on the formal batch

**Files:**
- Modify: `codex/ui_review_server.py`
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: `annotation/batch_20260413_v01/review_prep/*`

- [ ] **Step 1: Write the failing test**

Run:
```bash
curl -s http://127.0.0.1:10086/api/next_issue -X POST -H 'Content-Type: application/json' -d '{"annotator_id":"annotator_issue_smoke"}'
```
Expected: FAIL before the endpoint is implemented.

- [ ] **Step 2: Run test to verify it fails**

Once the endpoint exists, run both:
```bash
curl -s http://127.0.0.1:10086/api/next_issue -X POST -H 'Content-Type: application/json' -d '{"annotator_id":"annotator_issue_smoke"}'
curl -s 'http://127.0.0.1:10086/api/issue_detail?issue_id=<issue_id>'
```
Expected: valid JSON containing issue metadata and a frame payload.

- [ ] **Step 3: Write minimal implementation**

Patch any remaining payload or lookup mismatches revealed by the formal batch.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python codex/test_ui_review_server.py
curl -s http://127.0.0.1:10086/api/next_issue -X POST -H 'Content-Type: application/json' -d '{"annotator_id":"annotator_issue_smoke"}'
```
Expected: tests pass and issue API returns a non-empty issue payload.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Verify issue-mode APIs on formal batch"
```
