# Human Stage 1 Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `human_stage_1`-specific admin monitoring service and UI under `codes/application/step3_human_stage_1/` that tracks queue progress, annotator workload, recent submissions, and segment detail.

**Architecture:** Add a dedicated `ui_human_stage_1_admin_server.py` that reads only `human_stage_1/ui_human_stage_1.sqlite3` plus `human_stage_1_prep/*.segments.json`. Add a dedicated `admin_web/` frontend under the same `step3_human_stage_1` directory, borrowing the old admin panel’s visual structure but using only stage-1 queue and coarse-label metrics.

**Tech Stack:** Python 3, SQLite, `unittest`, vanilla JS/HTML/CSS

---

### Task 1: Add failing tests for the stage-1-specific admin server and static UI

**Files:**
- Create: `codes/test/step3_human_stage_1/test_ui_human_stage_1_admin_server.py`
- Create: `codes/test/step3_human_stage_1/test_ui_human_stage_1_admin_web_static.py`

- [ ] Write failing server tests for `overview()`, `annotator_stats()`, and `segment_detail()`
- [ ] Write failing static tests for `admin_web/index.html`, `admin_web/app.js`, and `admin_web/styles.css`
- [ ] Run the new tests and verify they fail
- [ ] Commit the red tests

### Task 2: Implement the dedicated stage-1 admin server

**Files:**
- Create: `codes/application/step3_human_stage_1/ui_human_stage_1_admin_server.py`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_admin_server.py`

- [ ] Implement a stage-1 admin state object that loads segment metadata from `human_stage_1_prep`
- [ ] Implement `/api/overview`, `/api/annotators`, `/api/recent_annotations`, `/api/segments`, and `/api/segment_detail`
- [ ] Ensure metrics are stage-1-specific: queue totals, pass1/pass2 completion, per-annotator completed frames, and recent stage-1 submissions
- [ ] Run the server tests and verify they pass
- [ ] Commit the backend implementation

### Task 3: Implement the dedicated stage-1 admin frontend

**Files:**
- Create: `codes/application/step3_human_stage_1/admin_web/index.html`
- Create: `codes/application/step3_human_stage_1/admin_web/app.js`
- Create: `codes/application/step3_human_stage_1/admin_web/styles.css`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_admin_web_static.py`

- [ ] Build a single-page admin UI with overview cards, queue/annotator charts, annotator table, recent submissions, and segment detail query
- [ ] Keep the layout visually similar to the old admin panel, but remove old review-specific wording and data assumptions
- [ ] Run JS syntax check and static tests
- [ ] Commit the frontend implementation

### Task 4: Refresh docs, verify, merge, and start the new admin service

**Files:**
- Modify: `docs/ACTIVE_SERVICES.md`
- Modify: `docs/README.md`

- [ ] Document the new `human_stage_1` admin service path and startup command
- [ ] Run final targeted tests plus JS syntax checks
- [ ] Merge back to `main`
- [ ] Start the new admin service on `10087`
- [ ] Verify local availability
