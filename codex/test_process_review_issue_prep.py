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
        with (self.batch_dir / "manifests" / "annotation_tasks.csv").open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "video_stem",
                    "video_path",
                    "timestamp_path",
                    "imu_paths",
                    "status",
                    "priority",
                ],
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
        track_summary = json.loads(
            (review_prep_dir / "sample.track_summary.json").read_text(encoding="utf-8")
        )
        risk_spans = json.loads(
            (review_prep_dir / "sample.risk_spans.json").read_text(encoding="utf-8")
        )
        with (review_prep_dir / "sample.issue_pool.csv").open("r", encoding="utf-8") as f:
            issue_rows = list(csv.DictReader(f))

        self.assertEqual(track_summary["video_stem"], "sample")
        self.assertEqual(track_summary["track_count"], 2)
        self.assertEqual(track_summary["tracks"][0]["track_id"], 1)
        self.assertGreaterEqual(track_summary["tracks"][0]["max_jump_distance"], 50.0)

        self.assertGreaterEqual(risk_spans["summary"]["risk_span_count"], 1)
        self.assertIn("low_score", risk_spans["risk_spans"][0]["reason_codes"])
        self.assertIn("high_overlap", risk_spans["risk_spans"][0]["reason_codes"])
        self.assertEqual(issue_rows[0]["video_stem"], "sample")
        self.assertIn(issue_rows[0]["severity"], {"yellow", "red"})


if __name__ == "__main__":
    unittest.main()
