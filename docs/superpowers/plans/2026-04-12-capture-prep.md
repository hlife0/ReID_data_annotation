# Capture Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only capture preparation pipeline that converts the latest raw MP4 + IMU dump into `required` session directories suitable for the annotation main flow.

**Architecture:** Put pure preprocessing logic in a small helper module under `codex/`, keep the CLI thin, and stage all generated outputs under `./staging/`. Reuse the upstream pipeline concepts, but adapt timestamp handling and IMU splitting for the new raw format.

**Tech Stack:** Python stdlib, ffprobe/ffmpeg subprocess calls, `unittest`

---

### Task 1: Add TDD Coverage For Core Prep Logic

**Files:**
- Create: `codex/test_prepare_capture_lib.py`
- Create: `codex/prepare_capture_lib.py`

- [ ] Cover video stem parsing, wall-clock to epoch conversion, interval overlap scoring, and session window generation with failing `unittest` cases.
- [ ] Run: `.venv/bin/python codex/test_prepare_capture_lib.py`
- [ ] Verify the new tests fail for the expected missing-symbol reasons.

### Task 2: Implement Pure Helpers

**Files:**
- Modify: `codex/prepare_capture_lib.py`
- Test: `codex/test_prepare_capture_lib.py`

- [ ] Implement the minimal helpers needed to pass the new unit tests.
- [ ] Run: `.venv/bin/python codex/test_prepare_capture_lib.py`
- [ ] Verify all tests pass.

### Task 3: Add Capture Preparation CLI

**Files:**
- Create: `codex/process_prepare_capture_batch.py`
- Modify: `codex/prepare_capture_lib.py`
- Test: `codex/test_prepare_capture_lib.py`

- [ ] Add the CLI that normalizes raw IMU data, computes candidate device pairs, generates approximate frame timestamps, creates session windows, and writes local `staging/required` outputs.
- [ ] Run syntax checks on the new files.

### Task 4: Prepare Latest Capture Locally

**Files:**
- Generate under: `staging/imu_normalized/`
- Generate under: `staging/required/`
- Generate under: `staging/reports/`

- [ ] Run the new CLI against the latest copied raw IMU dump and MP4.
- [ ] Verify the generated sessions each contain local `video/` and `imu/` directories in the expected shape.

### Task 5: Verify And Commit

**Files:**
- Modify: `.gitignore`
- Create: `docs/superpowers/specs/2026-04-12-capture-prep-design.md`
- Create: `docs/superpowers/plans/2026-04-12-capture-prep.md`
- Modify/Create: new `codex/` files

- [ ] Re-run unit tests plus syntax verification.
- [ ] Commit the code and docs.
- [ ] Push to `origin/main`.
