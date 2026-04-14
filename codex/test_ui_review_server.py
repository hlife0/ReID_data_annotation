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
        (self.batch_dir / "review_prep").mkdir(parents=True)
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
            "sample,1,1000,12,80,30,35,45,0.90\n"
            "sample,2,1033.333,11,12,22,42,52,0.93\n"
            "sample,2,1033.333,12,78,28,34,44,0.89\n"
            "sample,2,1033.333,13,120,40,20,30,0.81\n",
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
        (self.batch_dir / "review_prep" / "sample.issue_pool.csv").write_text(
            "issue_id,video_stem,severity,priority_score,start_frame,end_frame,start_timestamp_ms,end_timestamp_ms,frame_count,primary_track_ids,reason_codes,min_score,max_overlap_iou,max_jump_distance,imu_count\n"
            "sample_issue_001,sample,red,9.500,1,2,1000,1033.333,2,11;12,low_score;high_overlap,0.510,0.670,58.000,3\n",
            encoding="utf-8",
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

    def test_issue_pool_loads_and_returns_issue_payloads(self) -> None:
        state = self._make_state()

        self.assertEqual(len(state.issue_pool), 1)
        listed = state.list_issues(limit=10)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["issue_id"], "sample_issue_001")
        self.assertEqual(state.list_issues(video_stem="sample", limit=10)[0]["video_stem"], "sample")
        issue_payload = state.assign_next_issue("annotator_issue")
        self.assertEqual(issue_payload["issue"]["issue_id"], "sample_issue_001")
        self.assertEqual(issue_payload["issue"]["video_stem"], "sample")
        self.assertEqual(issue_payload["frame"]["slot_names"], [f"p{i}" for i in range(1, 8)])

        detail = state.issue_detail("sample_issue_001")
        self.assertEqual(detail["issue"]["issue_id"], "sample_issue_001")
        self.assertEqual(detail["frame"]["frame_index"], 1)
        stepped = state.issue_frame("sample_issue_001", 2)
        self.assertEqual(stepped["issue"]["issue_id"], "sample_issue_001")
        self.assertEqual(stepped["frame"]["frame_index"], 2)

    def test_issue_mode_submit_returns_next_issue_payload(self) -> None:
        state = self._make_state()
        self.assertEqual(len(state.list_issues(limit=10)), 1)
        result = state.submit_and_assign_next_issue(
            "annotator_issue",
            {
                "issue_id": "sample_issue_001",
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
        self.assertIn("submitted", result)
        self.assertIn("next_issue", result)
        self.assertIsNone(result["next_issue"])
        self.assertEqual(state.list_issues(limit=10), [])
        detail = state.issue_detail("sample_issue_001")
        self.assertEqual(detail["issue"]["issue_id"], "sample_issue_001")

    def test_issue_range_submit_expands_across_issue_frames(self) -> None:
        state = self._make_state()
        result = state.submit_issue_range(
            "annotator_issue_range",
            "sample_issue_001",
            {
                "issue_id": "sample_issue_001",
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
        self.assertEqual(result["submitted_frame_count"], 2)
        self.assertIsNone(result["next_issue"])
        self.assertEqual(state.list_issues(limit=10), [])
        history = state.list_annotations_for_annotator("annotator_issue_range")
        self.assertEqual(len(history), 2)
        details = [
            state.annotation_detail("annotator_issue_range", item["annotation_id"])
            for item in history
        ]
        by_frame = {item["frame"]["frame_index"]: item for item in details}
        detail_f1 = by_frame[1]
        detail_f2 = by_frame[2]
        self.assertEqual(detail_f1["frame"]["frame_index"], 1)
        self.assertEqual(detail_f2["frame"]["frame_index"], 2)
        self.assertEqual(detail_f1["annotation"]["slots"][0]["bbox_x"], 10.0)
        self.assertEqual(detail_f2["annotation"]["slots"][0]["bbox_x"], 12.0)
        self.assertEqual(detail_f1["annotation"]["slots"][1]["source"], "absent")
        self.assertEqual(detail_f2["annotation"]["slots"][1]["source"], "absent")


if __name__ == "__main__":
    unittest.main()
