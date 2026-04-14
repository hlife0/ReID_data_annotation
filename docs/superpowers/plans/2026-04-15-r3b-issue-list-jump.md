# R3B Issue List And Jump UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visible issue list and direct issue jump capability so annotators can browse concrete problems instead of relying only on the `Next Issue` button.

**Architecture:** Extend the review backend with issue listing APIs and keep the current `next_issue`/`issue_detail` contract. On the frontend, add a compact issue list panel in the existing right-side control area and wire it to fetch/select issue detail without shrinking the left canvas.

**Tech Stack:** Python 3, vanilla JavaScript, HTML/CSS, unittest, HTTP JSON APIs

---

## File Map

- Modify: `codex/ui_review_server.py` — add issue list endpoints and filtering helpers.
- Modify: `codex/test_ui_review_server.py` — add regression tests for listing and retrieving issues.
- Modify: `codex/ui_review_web/index.html` — add issue list container.
- Modify: `codex/ui_review_web/app.js` — load and render issue lists, support jump-to-issue.
- Modify: `codex/ui_review_web/styles.css` — style the compact issue list block.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — advance progress state.

### Task 1: Add backend tests and APIs for issue listing

**Files:**
- Modify: `codex/test_ui_review_server.py`
- Modify: `codex/ui_review_server.py`
- Test: `codex/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

Add tests for:
- `list_issues(video_stem=None, limit=...)`
- `list_issues(video_stem='sample', limit=...)`
- result order by priority descending
- `issue_detail(issue_id)` still works on listed issues

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: FAIL because issue list helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add issue list helpers and HTTP endpoints:
- `GET /api/issues`
- optional `video_stem` and `limit` filters

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py
git commit -m "Add issue list review APIs"
```

### Task 2: Add compact issue list UI and jump behavior

**Files:**
- Modify: `codex/ui_review_web/index.html`
- Modify: `codex/ui_review_web/app.js`
- Modify: `codex/ui_review_web/styles.css`
- Test: `codex/ui_review_web/app.js`

- [ ] **Step 1: Write the failing test**

Run:
```bash
rg -n "issueList|issueListBody|refreshIssuesBtn|loadIssues|loadIssueDetail|renderIssueList" codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css
```
Expected: no matches before implementation.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
node --check codex/ui_review_web/app.js
```
Expected: syntax passes while issue list hooks are still missing.

- [ ] **Step 3: Write minimal implementation**

Add a compact issue list block that:
- shows top issues by priority
- lets the user refresh the list
- lets the user click an issue to jump via `issue_detail`
- highlights the current issue
- stays in the right column and preserves the left canvas size

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "issueList|issueListBody|refreshIssuesBtn|loadIssues|loadIssueDetail|renderIssueList" codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css
node --check codex/ui_review_web/app.js
```
Expected: hooks exist and JS syntax is valid.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css
git commit -m "Add issue list and jump UI"
```

### Task 3: Verify list/jump flow on the formal batch

**Files:**
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: review service on `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run:
```bash
curl -s 'http://127.0.0.1:10086/api/issues?limit=5'
```
Expected: FAIL before the endpoint is implemented.

- [ ] **Step 2: Run test to verify it fails**

After implementation, run both:
```bash
curl -s 'http://127.0.0.1:10086/api/issues?limit=5'
curl -s 'http://127.0.0.1:10086/api/issue_detail?issue_id=<issue_id_from_list>'
```
Expected: valid JSON with top issues and jumpable detail.

- [ ] **Step 3: Write minimal implementation**

Patch any ordering/filtering/payload mismatch revealed by the formal batch.

- [ ] **Step 4: Run test to verify it passes**

Run backend tests, JS syntax checks, and list/detail curls against the formal batch.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/test_ui_review_server.py codex/ui_review_web/index.html codex/ui_review_web/app.js codex/ui_review_web/styles.css docs/REQUIREMENTS_TRAJECTORY_REVIEW.md
git commit -m "Verify issue list and jump flow"
```
