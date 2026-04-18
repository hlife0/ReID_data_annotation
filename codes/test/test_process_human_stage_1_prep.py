#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path

from process import process_segment_review_prep as base_prep
from process import segment_prep_common as common


class HumanStage1PrepTests(unittest.TestCase):
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

    def _subject_module(self):
        return importlib.import_module("process.process_human_stage_1_prep")

    def _run_subject(self) -> dict[str, object]:
        mod = self._subject_module()
        return mod.run_human_stage_1_prep(self.batch_dir)

    def _expected_first_pass_segments(self) -> list[tuple[str, int, int]]:
        task = common.load_tasks(self.batch_dir)[0]
        detections = common.load_detections(task.pseudo_label_path)
        by_frame = common.group_by_frame(detections)
        frame_states = [
            base_prep.classify_frame(
                frame_index,
                by_frame.get(frame_index, []),
                low_score_threshold=base_prep.DEFAULT_LOW_SCORE_THRESHOLD,
                high_overlap_iou=base_prep.DEFAULT_HIGH_OVERLAP_IOU,
            )
            for frame_index in base_prep.load_frame_timestamps(Path(task.timestamp_path))
        ]
        simple_flags = base_prep.bridge_simple_flags(
            frame_states,
            bridge_low_score_gaps=False,
            max_gap_frames=2,
        )
        segments = base_prep._first_pass_segments(task, frame_states, simple_flags)
        return [(item.segment_type, item.start_frame, item.end_frame) for item in segments]

    def test_human_stage_1_prep_preserves_first_pass_segments_before_second_pass_merge(self) -> None:
        summary = self._run_subject()

        self.assertEqual(summary["video_count"], 1)
        payload = json.loads(
            (self.batch_dir / "human_stage_1_prep" / "sample.segments.json").read_text(encoding="utf-8")
        )
        self.assertIn("first_pass_segments", payload)
        self.assertIn("segments", payload)
        self.assertEqual(
            [(item["segment_type"], item["start_frame"], item["end_frame"]) for item in payload["first_pass_segments"]],
            self._expected_first_pass_segments(),
        )
        self.assertLess(len(payload["segments"]), len(payload["first_pass_segments"]))
        self.assertEqual(
            [(item["segment_type"], item["start_frame"], item["end_frame"]) for item in payload["segments"]],
            [
                ("stable_segment", 1, 2),
                ("repair_window", 3, 5),
                ("stable_segment", 6, 7),
            ],
        )

    def test_human_stage_1_prep_creates_repair_window_only_from_first_pass_fragments(self) -> None:
        self._run_subject()

        payload = json.loads(
            (self.batch_dir / "human_stage_1_prep" / "sample.segments.json").read_text(encoding="utf-8")
        )
        first_pass = payload["first_pass_segments"]
        final_segments = payload["segments"]
        repair_windows = [item for item in final_segments if item["segment_type"] == "repair_window"]
        self.assertEqual(len(repair_windows), 1)

        repair_window = repair_windows[0]
        self.assertEqual((repair_window["start_frame"], repair_window["end_frame"]), (3, 5))
        self.assertEqual(
            repair_window["source_segment_types"],
            [
                "non_simple_single_frame",
                "stable_segment",
                "non_simple_single_frame",
            ],
        )
        source_ids = repair_window["source_segment_ids"]
        self.assertEqual(len(source_ids), 3)
        source_lookup = {item["segment_id"]: item for item in first_pass}
        self.assertEqual(set(source_ids), set(source_lookup))
        self.assertEqual(
            [
                (source_lookup[item]["segment_type"], source_lookup[item]["start_frame"], source_lookup[item]["end_frame"])
                for item in source_ids
            ],
            [
                ("non_simple_single_frame", 3, 3),
                ("stable_segment", 4, 4),
                ("non_simple_single_frame", 5, 5),
            ],
        )

    def test_human_stage_1_prep_writes_human_stage_1_artifacts(self) -> None:
        summary = self._run_subject()

        prep_dir = self.batch_dir / "human_stage_1_prep"
        self.assertTrue((prep_dir / "sample.segments.json").exists())
        self.assertTrue((prep_dir / "sample.segment_frames.json").exists())
        self.assertTrue((prep_dir / "human_stage_1_prep_summary.json").exists())
        written_summary = json.loads((prep_dir / "human_stage_1_prep_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["stable_segment_count"], 2)
        self.assertEqual(summary["non_simple_single_frame_count"], 0)
        self.assertEqual(summary["repair_window_count"], 1)
        self.assertEqual(written_summary["stable_segment_count"], 2)
        self.assertEqual(written_summary["non_simple_single_frame_count"], 0)
        self.assertEqual(written_summary["repair_window_count"], 1)


if __name__ == "__main__":
    unittest.main()
