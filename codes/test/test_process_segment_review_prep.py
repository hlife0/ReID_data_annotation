#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from process import process_segment_review_prep as mod


class SegmentReviewPrepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "pseudo_labels").mkdir(parents=True)
        (self.batch_dir / "assets").mkdir(parents=True)
        self.video_path = self.batch_dir / "assets" / "sample.mp4"
        self.timestamp_path = self.batch_dir / "assets" / "sample_frame_timestamps.csv"
        self.video_path.write_bytes(b"mp4")
        self.timestamp_path.write_text(
            "frame_index,timestamp_ms\n"
            "1,1000\n"
            "2,1033\n"
            "3,1066\n"
            "4,1100\n"
            "5,1133\n"
            "6,1166\n",
            encoding="utf-8",
        )
        self.pseudo_path = self.batch_dir / "pseudo_labels" / "sample.auto.csv"
        self.pseudo_path.write_text(
            "video_stem,frame_index,timestamp_ms,track_id,bbox_x,bbox_y,bbox_w,bbox_h,score\n"
            "sample,1,1000,1,10,10,20,40,0.95\n"
            "sample,1,1000,2,100,12,22,41,0.94\n"
            "sample,2,1033,1,12,10,20,40,0.96\n"
            "sample,2,1033,2,98,12,22,41,0.95\n"
            "sample,3,1066,1,14,10,20,40,0.95\n"
            "sample,3,1066,2,96,12,22,41,0.40\n"
            "sample,4,1100,1,16,10,20,40,0.96\n"
            "sample,4,1100,2,94,12,22,41,0.96\n"
            "sample,5,1133,1,18,10,20,40,0.95\n"
            "sample,5,1133,2,92,12,22,41,0.95\n"
            "sample,5,1133,3,150,20,24,44,0.95\n"
            "sample,6,1166,1,20,10,20,40,0.95\n"
            "sample,6,1166,2,90,12,22,41,0.95\n"
            "sample,6,1166,3,148,20,24,44,0.95\n",
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
                    "video_path": str(self.video_path),
                    "timestamp_path": str(self.timestamp_path),
                    "imu_paths": "/tmp/a.csv;/tmp/b.csv",
                    "status": "todo",
                    "priority": "1",
                }
            )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_segment_prep_splits_stable_segments_and_non_simple_single_frames(self) -> None:
        summary = mod.run_segment_review_prep(batch_dir=self.batch_dir)
        self.assertEqual(summary["video_count"], 1)

        segment_dir = self.batch_dir / "segment_prep"
        segments_payload = json.loads(
            (segment_dir / "sample.segments.json").read_text(encoding="utf-8")
        )
        frame_map_payload = json.loads(
            (segment_dir / "sample.segment_frames.json").read_text(encoding="utf-8")
        )
        batch_summary = json.loads(
            (segment_dir / "segment_prep_summary.json").read_text(encoding="utf-8")
        )

        segments = segments_payload["segments"]
        self.assertEqual(
            [(item["segment_type"], item["start_frame"], item["end_frame"]) for item in segments],
            [
                ("stable_segment", 1, 2),
                ("non_simple_single_frame", 3, 3),
                ("stable_segment", 4, 4),
                ("stable_segment", 5, 6),
            ],
        )
        self.assertEqual(segments[0]["representative_frame"], 1)
        self.assertEqual(segments[1]["representative_frame"], 3)
        self.assertEqual(segments[3]["representative_frame"], 5)
        self.assertEqual(frame_map_payload["frame_to_segment"]["3"], segments[1]["segment_id"])
        self.assertEqual(batch_summary["stable_segment_count"], 3)
        self.assertEqual(batch_summary["non_simple_single_frame_count"], 1)

    def test_segment_prep_accepts_custom_low_score_threshold(self) -> None:
        summary = mod.run_segment_review_prep(
            batch_dir=self.batch_dir,
            low_score_threshold=0.4,
        )
        self.assertEqual(summary["video_count"], 1)

        segment_dir = self.batch_dir / "segment_prep"
        segments_payload = json.loads(
            (segment_dir / "sample.segments.json").read_text(encoding="utf-8")
        )

        segments = segments_payload["segments"]
        self.assertEqual(
            [(item["segment_type"], item["start_frame"], item["end_frame"]) for item in segments],
            [
                ("stable_segment", 1, 4),
                ("stable_segment", 5, 6),
            ],
        )
        self.assertEqual(summary["stable_segment_count"], 2)
        self.assertEqual(summary["non_simple_single_frame_count"], 0)


if __name__ == "__main__":
    unittest.main()
