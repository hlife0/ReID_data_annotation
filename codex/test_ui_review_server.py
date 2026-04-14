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
        with (self.batch_dir / "manifests" / "annotation_tasks.csv").open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
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

    def _make_state(self) -> mod.AnnotationState:
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
        return state

    def test_assignment_submit_and_edit_round_trip_with_dynamic_slots(self) -> None:
        state = self._make_state()
        frame = state.assign_next_frame("annotator_a", "test")["frame"]
        self.assertEqual(frame["slot_names"], [f"p{i}" for i in range(1, 8)])
        self.assertEqual(len(state.ai_boxes[("sample", 1)]), 2)

        submit_payload = {
            "video_stem": "sample",
            "frame_index": 1,
            "timestamp_ms": 1000,
            "slots": [
                {
                    "slot": "p1",
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 40,
                    "bbox_h": 50,
                    "source": "ai",
                    "ai_track_id": "11",
                },
                {
                    "slot": "p2",
                    "bbox_x": 80,
                    "bbox_y": 30,
                    "bbox_w": 35,
                    "bbox_h": 45,
                    "source": "manual_draw",
                    "ai_track_id": "",
                },
                {
                    "slot": "p3",
                    "bbox_x": 0,
                    "bbox_y": 0,
                    "bbox_w": 0,
                    "bbox_h": 0,
                    "source": "absent",
                    "ai_track_id": "",
                },
            ],
        }

        result = state.submit_and_assign_next("annotator_a", submit_payload)
        self.assertEqual(result["submitted"]["video_stem"], "sample")

        history = state.list_annotations_for_annotator("annotator_a")
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
                    {
                        "slot": "p1",
                        "bbox_x": 12,
                        "bbox_y": 22,
                        "bbox_w": 42,
                        "bbox_h": 52,
                        "source": "manual_param",
                        "ai_track_id": "11",
                    },
                    {
                        "slot": "p2",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_w": 0,
                        "bbox_h": 0,
                        "source": "absent",
                        "ai_track_id": "",
                    },
                ],
            },
        )
        updated = state.annotation_detail("annotator_a", history[0]["annotation_id"])
        self.assertEqual(updated["annotation"]["slots"][0]["source"], "manual_param")
        self.assertEqual(updated["annotation"]["slots"][1]["source"], "absent")
        self.assertIn(
            "P1:manual_param(11)",
            state.list_annotations_for_annotator("annotator_a")[0]["slots_summary"],
        )


if __name__ == "__main__":
    unittest.main()
