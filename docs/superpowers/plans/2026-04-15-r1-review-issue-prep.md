# R1 Review Issue Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate batch-local `track_summary`, `risk_spans`, and `issue_pool` outputs from AI pseudo labels so review can move from frame sampling toward issue-driven triage.

**Architecture:** Add one offline batch processor that reads `annotation_tasks.csv` and each session's `.auto.csv`, computes per-track summaries plus simple heuristic risk events, merges them into risk spans, and exports machine-readable JSON/CSV files under `batch_dir/review_prep/`. Keep the current review stack unchanged for now; this phase only produces stable intermediate artifacts.

**Tech Stack:** Python 3, csv, json, dataclasses, pathlib, unittest

---

## File Map

- Create: `codex/process_review_issue_prep.py` — offline batch processor and reusable analysis helpers for track summaries, frame risk scoring, merged spans, and CSV/JSON export.
- Create: `codex/test_process_review_issue_prep.py` — regression tests covering summary generation, risk span merging, and batch output layout.
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md` — mark R1 as started/completed once outputs exist.

### Task 1: Add failing regression tests for track and risk preparation

**Files:**
- Create: `codex/test_process_review_issue_prep.py`
- Create: `codex/process_review_issue_prep.py`
- Test: `codex/test_process_review_issue_prep.py`

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import process_review_issue_prep as mod


class ReviewIssuePrepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "pseudo_labels").mkdir(parents=True)
        self.pseudo_path = self.batch_dir / "pseudo_labels" / "sample.auto.csv"
        self.pseudo_path.write_text(
            "video_stem,frame_index,timestamp_ms,track_id,bbox_x,bbox_y,bbox_w,bbox_h,score,class_name,imu_id,source,review_state\n"
            "sample,1,1000,1,10,10,20,40,0.95,person,unknown,auto,pending\n"
            "sample,1,1000,2,100,12,22,41,0.93,person,unknown,auto,pending\n"
            "sample,2,1033,1,12,10,20,40,0.94,person,unknown,auto,pending\n"
            "sample,2,1033,2,98,12,22,41,0.92,person,unknown,auto,pending\n"
            "sample,3,1066,1,70,10,20,40,0.52,person,unknown,auto,pending\n"
            "sample,3,1066,2,72,12,22,41,0.51,person,unknown,auto,pending\n"
            "sample,4,1100,1,74,10,20,40,0.93,person,unknown,auto,pending\n",
            encoding="utf-8",
        )
        with (self.batch_dir / "manifests" / "annotation_tasks.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["video_stem", "video_path", "timestamp_path", "imu_paths", "status", "priority"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "video_stem": "sample",
                    "video_path": "/tmp/sample.mp4",
                    "timestamp_path": "/tmp/sample_ts.csv",
                    "imu_paths": "/tmp/a.csv;/tmp/b.csv;/tmp/c.csv",
                    "status": "todo",
                    "priority": "1",
                }
            )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_analyze_batch_emits_track_summary_risk_spans_and_issue_pool(self) -> None:
        summary = mod.run_review_issue_prep(batch_dir=self.batch_dir)
        self.assertEqual(summary["video_count"], 1)
        review_prep_dir = self.batch_dir / "review_prep"
        track_summary = json.loads((review_prep_dir / "sample.track_summary.json").read_text(encoding="utf-8"))
        risk_spans = json.loads((review_prep_dir / "sample.risk_spans.json").read_text(encoding="utf-8"))
        issue_rows = list(csv.DictReader((review_prep_dir / "sample.issue_pool.csv").open("r", encoding="utf-8")))

        self.assertEqual(track_summary["video_stem"], "sample")
        self.assertEqual(track_summary["track_count"], 2)
        self.assertEqual(track_summary["tracks"][0]["track_id"], 1)
        self.assertGreaterEqual(track_summary["tracks"][0]["max_jump_distance"], 50.0)

        self.assertGreaterEqual(risk_spans["summary"]["risk_span_count"], 1)
        self.assertIn("low_score", risk_spans["risk_spans"][0]["reason_codes"])
        self.assertIn("high_overlap", risk_spans["risk_spans"][0]["reason_codes"])
        self.assertEqual(issue_rows[0]["video_stem"], "sample")
        self.assertIn(issue_rows[0]["severity"], {"yellow", "red"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python codex/test_process_review_issue_prep.py`
Expected: FAIL because `process_review_issue_prep.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement the smallest analysis library needed to:
- parse pseudo label rows
- build per-track summaries
- derive frame-level risk events (`low_score`, `bbox_jump`, `count_change`, `high_overlap`, `track_boundary`, `segment_edge`)
- merge nearby risky frames into risk spans
- export `track_summary.json`, `risk_spans.json`, and `issue_pool.csv`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python codex/test_process_review_issue_prep.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add codex/process_review_issue_prep.py codex/test_process_review_issue_prep.py
git commit -m "Add review issue preparation pipeline"
```

### Task 2: Run R1 on the formal batch and verify exported outputs

**Files:**
- Modify: `codex/process_review_issue_prep.py`
- Modify: `docs/REQUIREMENTS_TRAJECTORY_REVIEW.md`
- Test: `annotation/batch_20260413_v01/review_prep/*`

- [ ] **Step 1: Write the failing test**

Run:
```bash
test -d annotation/batch_20260413_v01/review_prep && find annotation/batch_20260413_v01/review_prep -maxdepth 1 -type f | wc -l
```
Expected: directory missing or empty before running the new processor.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python codex/process_review_issue_prep.py --batch-dir ./annotation/batch_20260413_v01
```
Expected: first successful generation pass, then verify outputs.

- [ ] **Step 3: Write minimal implementation**

If batch execution reveals missing manifest assumptions or real-data issues, patch only what is needed so the formal batch exports all review-prep artifacts cleanly.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python codex/test_process_review_issue_prep.py
.venv/bin/python codex/process_review_issue_prep.py --batch-dir ./annotation/batch_20260413_v01
find annotation/batch_20260413_v01/review_prep -maxdepth 1 -type f | sort | sed -n '1,80p'
.venv/bin/python - <<'PY'
import csv, json
from pathlib import Path
root = Path('annotation/batch_20260413_v01/review_prep')
track_files = sorted(root.glob('*.track_summary.json'))
risk_files = sorted(root.glob('*.risk_spans.json'))
issue_files = sorted(root.glob('*.issue_pool.csv'))
summary = json.loads((root / 'review_prep_summary.json').read_text(encoding='utf-8'))
print({
    'track_files': len(track_files),
    'risk_files': len(risk_files),
    'issue_files': len(issue_files),
    'video_count': summary['video_count'],
    'issue_count': summary['issue_count'],
})
PY
```
Expected:
- test suite passes
- all 20 sessions produce track/risk/issue outputs
- summary file exists and reports non-zero issue count

- [ ] **Step 5: Commit**

```bash
git add codex/process_review_issue_prep.py docs/REQUIREMENTS_TRAJECTORY_REVIEW.md annotation/batch_20260413_v01/review_prep
git commit -m "Generate review issue prep outputs for formal batch"
```
