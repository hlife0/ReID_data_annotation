# R0 Dynamic Slot Review Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the new `P1-P7` review baseline so the current batch can be annotated reliably with dynamic slot payloads, compact right-side controls, and matching admin visibility.

**Architecture:** Keep the current batch/session model and existing frame-based review flow, but finish the migration from fixed `P1/P2` fields to dynamic slot JSON. Backend stays manifest-driven and exports frame-level records; frontend keeps the large canvas and switches to a compact shared slot editor plus generic admin summaries.

**Tech Stack:** Python 3, sqlite3, BaseHTTPRequestHandler, vanilla JavaScript, HTML/CSS, unittest, Node syntax check

---

## File Map

- Modify: `codex/ui_review_server.py` — stabilize slot payload validation, annotation detail/export shape, and remove remaining hardcoded dual-slot assumptions that affect current review flow.
- Modify: `codex/ui_admin_server.py` — keep admin APIs aligned with generic slot summaries and frame detail rendering.
- Modify: `codex/ui_review_web/app.js` — finish dynamic slot UI behavior, remove stale P1/P2 language, and keep editing/submit flows consistent.
- Modify: `codex/ui_review_web/index.html` — keep compact slot layout and generic copy.
- Modify: `codex/ui_review_web/styles.css` — preserve large left canvas and compress the right editor for many slots.
- Modify: `codex/ui_admin_web/app.js` — remove stale P1/P2-specific labels in the admin UI.
- Create: `codex/test_ui_review_server.py` — backend regression tests for dynamic-slot assignment, submit, edit, and export behavior.

### Task 1: Add backend regression tests for dynamic-slot review state

**Files:**
- Create: `codex/test_ui_review_server.py`
- Modify: `codex/ui_review_server.py`
- Test: `codex/test_ui_review_server.py`

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

import ui_review_server as mod


class DynamicSlotReviewStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "pseudo_labels").mkdir(parents=True)
        (self.batch_dir / "assets").mkdir(parents=True)
        self.video_path = self.batch_dir / "assets" / "sample.mp4"
        self.ts_path = self.batch_dir / "assets" / "sample_frame_timestamps.csv"
        self._write_video(self.video_path)
        self.ts_path.write_text(
            "frame_index,timestamp_ms\n1,1000\n2,1033.333\n",
            encoding="utf-8",
        )
        (self.batch_dir / "pseudo_labels" / "sample.auto.csv").write_text(
            "video_stem,frame_index,timestamp_ms,track_id,bbox_x,bbox_y,bbox_w,bbox_h,score\n"
            "sample,1,1000,11,10,20,40,50,0.95\n"
            "sample,1,1000,12,80,30,35,45,0.90\n",
            encoding="utf-8",
        )
        with (self.batch_dir / "manifests" / "annotation_tasks.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "video_stem",
                    "task_status",
                    "status_reason",
                    "video_path",
                    "timestamp_path",
                    "imu_count",
                    "imu_paths",
                    "pseudo_label_path",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "video_stem": "sample",
                    "task_status": "todo",
                    "status_reason": "",
                    "video_path": str(self.video_path),
                    "timestamp_path": str(self.ts_path),
                    "imu_count": "3",
                    "imu_paths": "a.csv;b.csv;c.csv",
                    "pseudo_label_path": str(self.batch_dir / "pseudo_labels" / "sample.auto.csv"),
                }
            )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write_video(self, path: Path) -> None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, 30.0, (160, 120))
        self.assertTrue(writer.isOpened())
        for _ in range(2):
            frame = np.full((120, 160, 3), 200, dtype=np.uint8)
            writer.write(frame)
        writer.release()

    def test_assignment_submit_and_edit_round_trip_with_dynamic_slots(self) -> None:
        state = mod.AnnotationState(
            batch_dir=self.batch_dir,
            static_dir=Path("codex/ui_review_web"),
            seed=123,
            reset_storage=True,
            frame_cache_dir=None,
            frame_cache_prewarm=False,
            frame_cache_max=0,
            frame_cache_quality=88,
        )
        state.initialize()
        frame = state.assign_next_frame("annotator_a", "test")["frame"]
        self.assertEqual(frame["slot_names"], [f"p{i}" for i in range(1, 8)])
        self.assertEqual(len(frame["ai_boxes"]), 2)

        submit_payload = {
            "video_stem": "sample",
            "frame_index": 1,
            "timestamp_ms": 1000,
            "slots": [
                {"slot": "p1", "bbox_x": 10, "bbox_y": 20, "bbox_w": 40, "bbox_h": 50, "source": "ai", "ai_track_id": "11"},
                {"slot": "p2", "bbox_x": 80, "bbox_y": 30, "bbox_w": 35, "bbox_h": 45, "source": "manual_draw", "ai_track_id": ""},
                {"slot": "p3", "bbox_x": 0, "bbox_y": 0, "bbox_w": 0, "bbox_h": 0, "source": "absent", "ai_track_id": ""},
            ],
        }
        result = state.submit_annotation("annotator_a", submit_payload)
        self.assertEqual(result["submitted"]["video_stem"], "sample")

        history = state.list_annotations("annotator_a")
        self.assertEqual(len(history), 1)
        detail = state.annotation_detail("annotator_a", history[0]["annotation_id"])
        self.assertEqual(detail["frame"]["slot_names"], [f"p{i}" for i in range(1, 8)])
        self.assertEqual(detail["annotation"]["slots"][0]["slot"], "p1")
        self.assertEqual(detail["annotation"]["slots"][2]["source"], "absent")
        self.assertEqual(detail["annotation"]["slots"][6]["slot"], "p7")

        state.update_annotation(
            "annotator_a",
            {
                "annotation_id": history[0]["annotation_id"],
                "video_stem": "sample",
                "frame_index": 1,
                "timestamp_ms": 1000,
                "slots": [
                    {"slot": "p1", "bbox_x": 12, "bbox_y": 22, "bbox_w": 42, "bbox_h": 52, "source": "manual_param", "ai_track_id": "11"},
                    {"slot": "p2", "bbox_x": 0, "bbox_y": 0, "bbox_w": 0, "bbox_h": 0, "source": "absent", "ai_track_id": ""},
                ],
            },
        )
        updated = state.annotation_detail("annotator_a", history[0]["annotation_id"])
        self.assertEqual(updated["annotation"]["slots"][0]["source"], "manual_param")
        self.assertEqual(updated["annotation"]["slots"][1]["source"], "absent")
        self.assertIn("P1:manual_param(11)", state.list_annotations("annotator_a")[0]["slots_summary"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: FAIL because the current review state still has dynamic-slot regressions or missing compatibility behavior.

- [ ] **Step 3: Write minimal implementation**

Implement only the backend changes needed to make the new regression test pass. Focus on slot normalization, annotation detail shape, summary text, and update/submit consistency.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codex/test_ui_review_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codex/test_ui_review_server.py codex/ui_review_server.py
git commit -m "Stabilize dynamic slot review state"
```

### Task 2: Finish the review frontend migration to a compact shared P1-P7 editor

**Files:**
- Modify: `codex/ui_review_web/app.js`
- Modify: `codex/ui_review_web/index.html`
- Modify: `codex/ui_review_web/styles.css`
- Test: `codex/ui_review_web/app.js`

- [ ] **Step 1: Write the failing test**

Use a lightweight regression target instead of a browser harness: identify stale dual-slot language and incomplete dynamic-slot wiring, then make those checks fail by searching for forbidden strings and running JS syntax checks.

Run:
```bash
rg -n "P1/P2|历史推荐 P1/P2|Applied historical P1/P2|双人框标注复核|双人" codex/ui_review_web/app.js codex/ui_review_web/index.html codex/ui_review_web/styles.css
```
Expected: FINDS stale dual-slot strings before cleanup.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
node --check codex/ui_review_web/app.js
```
Expected: PASS syntax-wise, while the `rg` command still reports stale dual-slot assumptions to remove.

- [ ] **Step 3: Write minimal implementation**

Make the frontend consistently dynamic-slot-first:
- Remove stale P1/P2-only copy and recommendation toasts.
- Keep the left canvas sizing unchanged.
- Keep the right side as compact slot tabs + shared editor.
- Ensure edit/save/submit paths use `state.slotNames` everywhere and keep the current active slot coherent.
- Make the visible labels generic for multi-person review.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "P1/P2|历史推荐 P1/P2|Applied historical P1/P2|双人框标注复核|双人" codex/ui_review_web/app.js codex/ui_review_web/index.html codex/ui_review_web/styles.css
node --check codex/ui_review_web/app.js
```
Expected:
- `rg` returns no stale dual-slot UI strings.
- `node --check` exits 0.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_web/app.js codex/ui_review_web/index.html codex/ui_review_web/styles.css
git commit -m "Finish compact dynamic slot review UI"
```

### Task 3: Align admin summaries and review metadata with generic slots

**Files:**
- Modify: `codex/ui_admin_server.py`
- Modify: `codex/ui_admin_web/app.js`
- Test: `codex/ui_admin_web/app.js`

- [ ] **Step 1: Write the failing test**

Run:
```bash
rg -n "th_p1|th_p2|P1 source|P2 source|P1 来源|P2 来源" codex/ui_admin_web/app.js codex/ui_admin_web/index.html
```
Expected: FINDS stale dual-slot admin labels.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
node --check codex/ui_admin_web/app.js
```
Expected: PASS syntax-wise, while `rg` still reports stale labels.

- [ ] **Step 3: Write minimal implementation**

Replace the stale admin labels with generic slot-oriented language and ensure recent/frame-detail tables keep rendering `slots_summary` from the server rather than dual-slot columns.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
rg -n "th_p1|th_p2|P1 source|P2 source|P1 来源|P2 来源" codex/ui_admin_web/app.js codex/ui_admin_web/index.html
node --check codex/ui_admin_web/app.js
```
Expected:
- `rg` returns no stale dual-slot admin labels.
- `node --check` exits 0.

- [ ] **Step 5: Commit**

```bash
git add codex/ui_admin_web/app.js codex/ui_admin_server.py
git commit -m "Align admin UI with generic slot summaries"
```

### Task 4: Run service-level verification against the formal batch

**Files:**
- Modify: `codex/ui_review_server.py`
- Modify: `codex/ui_admin_server.py`
- Test: `annotation/batch_20260413_v01`

- [ ] **Step 1: Write the failing test**

Run the live services against the formal batch and capture the exact API surface we need:

```bash
nohup .venv/bin/python codex/ui_review_server.py --batch-dir ./annotation/batch_20260413_v01 --port 10086 --frame-cache-disk --frame-cache-max 512 >/tmp/ui_review_10086.log 2>&1 &
nohup .venv/bin/python codex/ui_admin_server.py --batch-dir ./annotation/batch_20260413_v01 --port 10087 >/tmp/ui_admin_10087.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:10086/api/next_frame -X POST -H 'Content-Type: application/json' -d '{"annotator_id":"annotator_smoke"}'
curl -s 'http://127.0.0.1:10086/api/my_annotations?annotator_id=annotator_smoke'
curl -s http://127.0.0.1:10087/api/videos
```
Expected: At least one of these responses will show a mismatch that must be fixed before claiming R0 is stable.

- [ ] **Step 2: Run test to verify it fails**

If any API returns malformed slot data, missing slot names, or runtime errors, capture that exact failure and fix only that behavior.

- [ ] **Step 3: Write minimal implementation**

Adjust the review/admin server behavior only as needed so the formal batch returns consistent slot-aware payloads for assignment, history, annotation detail, and admin listings.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python codex/test_ui_review_server.py
node --check codex/ui_review_web/app.js
node --check codex/ui_admin_web/app.js
curl -s http://127.0.0.1:10086/api/status
curl -s http://127.0.0.1:10086/api/next_frame -X POST -H 'Content-Type: application/json' -d '{"annotator_id":"annotator_smoke"}'
curl -s 'http://127.0.0.1:10086/api/my_annotations?annotator_id=annotator_smoke'
curl -s http://127.0.0.1:10087/api/videos
```
Expected:
- backend test passes
- both JS syntax checks pass
- review/admin APIs return slot-aware JSON successfully

- [ ] **Step 5: Commit**

```bash
git add codex/ui_review_server.py codex/ui_admin_server.py codex/ui_review_web/app.js codex/ui_review_web/index.html codex/ui_review_web/styles.css codex/ui_admin_web/app.js codex/test_ui_review_server.py
git commit -m "Verify dynamic slot review stack on formal batch"
```
