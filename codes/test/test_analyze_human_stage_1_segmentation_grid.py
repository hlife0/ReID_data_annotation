#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path


class HumanStage1SegmentationGridAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "pseudo_labels").mkdir(parents=True)
        (self.batch_dir / "assets").mkdir(parents=True)
        self.video_path = self.batch_dir / "assets" / "sample.mp4"
        self.timestamp_path = self.batch_dir / "assets" / "sample_frame_timestamps.csv"
        self.video_path.write_bytes(b"mp4")
        self._write_timestamps(7)
        self._write_fragment_cluster_rows()
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

    def _subject_module(self):
        return importlib.import_module("process.analyze_human_stage_1_segmentation_grid")

    def _write_timestamps(self, frame_count: int) -> None:
        rows = ["frame_index,timestamp_ms\n"]
        for idx in range(1, frame_count + 1):
            rows.append(f"{idx},{1000 + (idx - 1) * 33}\n")
        self.timestamp_path.write_text("".join(rows), encoding="utf-8")

    def _write_fragment_cluster_rows(self) -> None:
        pseudo_path = self.batch_dir / "pseudo_labels" / "sample.auto.csv"
        pseudo_path.write_text(
            "video_stem,frame_index,timestamp_ms,track_id,bbox_x,bbox_y,bbox_w,bbox_h,score\n"
            "sample,1,1000,1,10,10,20,40,0.95\n"
            "sample,1,1000,2,100,12,22,41,0.94\n"
            "sample,2,1033,1,12,10,20,40,0.96\n"
            "sample,2,1033,2,98,12,22,41,0.95\n"
            "sample,3,1066,1,14,10,20,40,0.95\n"
            "sample,3,1066,2,96,12,22,41,0.40\n"
            "sample,4,1099,1,16,10,20,40,0.96\n"
            "sample,4,1099,2,94,12,22,41,0.96\n"
            "sample,5,1132,1,18,10,20,40,0.95\n"
            "sample,5,1132,2,92,12,22,41,0.40\n"
            "sample,6,1165,1,20,10,20,40,0.95\n"
            "sample,6,1165,2,90,12,22,41,0.95\n"
            "sample,7,1198,1,22,10,20,40,0.96\n"
            "sample,7,1198,2,88,12,22,41,0.96\n",
            encoding="utf-8",
        )

    def test_analyze_batch_reports_total_frames_and_work_unit_counts(self) -> None:
        subject = self._subject_module()
        first_pass_configs = [
            subject.FirstPassConfig(
                key="fp_default",
                low_score_threshold=0.60,
                high_overlap_iou=0.25,
                bridge_low_score_gaps=False,
                max_gap_frames=2,
            ),
            subject.FirstPassConfig(
                key="fp_relaxed",
                low_score_threshold=0.40,
                high_overlap_iou=0.25,
                bridge_low_score_gaps=False,
                max_gap_frames=2,
            ),
        ]
        second_pass_configs = [
            subject.SecondPassConfig(
                key="sp_default",
                micro_stable_max_frames=3,
                max_repair_window_frames=10,
                min_non_simple_segments=2,
            ),
            subject.SecondPassConfig(
                key="sp_tight",
                micro_stable_max_frames=3,
                max_repair_window_frames=2,
                min_non_simple_segments=2,
            ),
        ]

        result = subject.analyze_batch(
            batch_dir=self.batch_dir,
            first_pass_configs=first_pass_configs,
            second_pass_configs=second_pass_configs,
        )

        self.assertEqual(result["total_frames"], 7)
        self.assertEqual(result["first_pass"]["fp_default"]["work_unit_count"], 5)
        self.assertEqual(result["first_pass"]["fp_relaxed"]["work_unit_count"], 1)
        self.assertEqual(result["second_pass"]["sp_default"]["fp_default"]["work_unit_count"], 3)
        self.assertEqual(result["second_pass"]["sp_tight"]["fp_default"]["work_unit_count"], 5)
        self.assertEqual(result["second_pass"]["sp_default"]["fp_relaxed"]["work_unit_count"], 1)

    def test_analyze_batch_matches_current_stage1_defaults_on_fragment_cluster(self) -> None:
        subject = self._subject_module()

        result = subject.analyze_batch(
            batch_dir=self.batch_dir,
            first_pass_configs=[subject.FirstPassConfig.default()],
            second_pass_configs=[subject.SecondPassConfig.default()],
        )

        self.assertEqual(result["first_pass"]["fp_default"]["work_unit_count"], 5)
        self.assertEqual(result["second_pass"]["sp_default"]["fp_default"]["work_unit_count"], 3)

    def test_write_outputs_creates_summary_csv_and_json(self) -> None:
        subject = self._subject_module()
        output_dir = self.batch_dir / "analysis-output"
        result = subject.analyze_batch(
            batch_dir=self.batch_dir,
            first_pass_configs=[subject.FirstPassConfig.default()],
            second_pass_configs=[subject.SecondPassConfig.default()],
            output_dir=output_dir,
        )

        self.assertEqual(result["output_dir"], str(output_dir))
        self.assertTrue((output_dir / "summary.md").exists())
        self.assertTrue((output_dir / "first_pass_summary.csv").exists())
        self.assertTrue((output_dir / "second_pass_grid.csv").exists())
        self.assertTrue((output_dir / "results.json").exists())

        summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("Total Frames", summary_text)
        self.assertIn("fp_default", summary_text)
        self.assertIn("sp_default", summary_text)

        written = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(written["total_frames"], 7)
        self.assertIn("first_pass", written)
        self.assertIn("second_pass", written)


if __name__ == "__main__":
    unittest.main()
