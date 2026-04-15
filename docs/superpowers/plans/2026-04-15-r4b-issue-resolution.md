# R4B Issue Resolution State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist issue resolution state so `next_issue` and the issue list stop resurfacing already-handled issues.

**Architecture:** Add a small `issue_reviews` table to the review sqlite database. When an issue is handled through `submit_issue` or `submit_issue_range`, mark it resolved. `next_issue` and `list_issues` will filter out resolved issues by default, while `issue_detail` remains available for direct lookup.

**Tech Stack:** Python 3, sqlite3, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codes/ui_review_server.py` — add issue review persistence and unresolved filtering.
- Modify: `codes/test_ui_review_server.py` — add regression tests proving resolved issues stop reappearing.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — note that issue-mode now has completion state.

### Task 1: Add failing tests for issue resolution state

**Files:**
- Modify: `codes/test_ui_review_server.py`
- Modify: `codes/ui_review_server.py`
- Test: `codes/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Add tests that:
- after `submit_and_assign_next_issue`, the handled issue disappears from `list_issues()`
- after `submit_issue_range`, the handled issue disappears from `list_issues()`
- `issue_detail(issue_id)` still works for resolved issues

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codes/test_ui_review_server.py`
Expected: FAIL because issue resolution state is not persisted yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- sqlite table for issue reviews/resolution
- helper to mark an issue resolved
- unresolved filtering in `next_issue` / `list_issues`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codes/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_server.py codes/test_ui_review_server.py
git commit -m "Persist issue resolution state"
```

### Task 2: Verify unresolved filtering on the formal batch

**Files:**
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: running review service + `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run a real `next_issue`, then submit it, then request `issues` again and confirm the same issue no longer appears at the top.

- [ ] **Step 2: Run test to verify it fails**

Before implementation, the same handled issue can reappear.

- [ ] **Step 3: Write minimal implementation**

Patch any filtering/persistence bug revealed by the formal batch.

- [ ] **Step 4: Run test to verify it passes**

Run backend tests and formal-batch issue handling smoke tests.

- [ ] **Step 5: Commit**

```bash
git add codes/ui_review_server.py codes/test_ui_review_server.py docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Filter resolved issues from issue workflow"
```
