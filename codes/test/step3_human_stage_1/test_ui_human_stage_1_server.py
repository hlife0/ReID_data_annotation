#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import cv2
import numpy as np


class HumanStage1ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "pseudo_labels").mkdir(parents=True)
        (self.batch_dir / "human_stage_1_prep").mkdir(parents=True)
        (self.batch_dir / "segment_prep").mkdir(parents=True)
        (self.batch_dir / "assets").mkdir(parents=True)
        self.video_path = self.batch_dir / "assets" / "sample.mp4"
        self.ts_path = self.batch_dir / "assets" / "sample_frame_timestamps.csv"
        self._write_video(self.video_path)
        self.ts_path.write_text(
            "frame_index,timestamp_ms\n1,1000\n2,1033.333\n3,1066.667\n4,1100\n5,1133.333\n6,1166.667\n",
            encoding="utf-8",
        )
        (self.batch_dir / "pseudo_labels" / "sample.auto.csv").write_text(
            "video_stem,frame_index,timestamp_ms,track_id,bbox_x,bbox_y,bbox_w,bbox_h,score\n"
            "sample,1,1000,11,10,20,30,40,0.95\n"
            "sample,1,1000,12,80,18,32,42,0.94\n"
            "sample,2,1033.333,11,12,20,30,40,0.95\n"
            "sample,2,1033.333,12,82,18,32,42,0.94\n"
            "sample,3,1066.667,11,14,20,30,40,0.95\n"
            "sample,3,1066.667,12,84,18,32,42,0.94\n"
            "sample,4,1100,11,16,20,30,40,0.95\n"
            "sample,4,1100,12,86,18,32,42,0.94\n"
            "sample,5,1133.333,11,18,20,30,40,0.95\n"
            "sample,5,1133.333,12,88,18,32,42,0.94\n"
            "sample,6,1166.667,11,20,20,30,40,0.95\n"
            "sample,6,1166.667,12,90,18,32,42,0.94\n",
            encoding="utf-8",
        )
        with (self.batch_dir / "human_stage_1_prep" / "sample.segments.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "video_stem": "sample",
                    "first_pass_segments": [
                        {
                            "segment_id": "sample_first_pass_000001",
                            "video_stem": "sample",
                            "segment_type": "stable_segment",
                            "start_frame": 1,
                            "end_frame": 3,
                            "representative_frame": 2,
                            "track_ids": [11, 12],
                            "frame_count": 3,
                        },
                        {
                            "segment_id": "sample_first_pass_000002",
                            "video_stem": "sample",
                            "segment_type": "non_simple_single_frame",
                            "start_frame": 4,
                            "end_frame": 4,
                            "representative_frame": 4,
                            "track_ids": [11, 12],
                            "frame_count": 1,
                        },
                        {
                            "segment_id": "sample_first_pass_000003",
                            "video_stem": "sample",
                            "segment_type": "stable_segment",
                            "start_frame": 5,
                            "end_frame": 5,
                            "representative_frame": 5,
                            "track_ids": [11, 12],
                            "frame_count": 1,
                        },
                        {
                            "segment_id": "sample_first_pass_000004",
                            "video_stem": "sample",
                            "segment_type": "non_simple_single_frame",
                            "start_frame": 6,
                            "end_frame": 6,
                            "representative_frame": 6,
                            "track_ids": [11, 12],
                            "frame_count": 1,
                        },
                    ],
                    "segments": [
                        {
                            "segment_id": "sample_stage1_seg_000001",
                            "video_stem": "sample",
                            "segment_type": "stable_segment",
                            "start_frame": 1,
                            "end_frame": 3,
                            "representative_frame": 2,
                            "track_ids": [11, 12],
                            "frame_count": 3,
                            "source_segment_ids": ["sample_first_pass_000001"],
                            "source_segment_types": ["stable_segment"],
                        },
                        {
                            "segment_id": "sample_stage1_seg_000002",
                            "video_stem": "sample",
                            "segment_type": "repair_window",
                            "start_frame": 4,
                            "end_frame": 6,
                            "representative_frame": 5,
                            "track_ids": [11, 12],
                            "frame_count": 3,
                            "source_segment_ids": [
                                "sample_first_pass_000002",
                                "sample_first_pass_000003",
                                "sample_first_pass_000004",
                            ],
                            "source_segment_types": [
                                "non_simple_single_frame",
                                "stable_segment",
                                "non_simple_single_frame",
                            ],
                        },
                    ],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        with (self.batch_dir / "human_stage_1_prep" / "sample.segment_frames.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "video_stem": "sample",
                    "frame_to_segment": {
                        "1": "sample_stage1_seg_000001",
                        "2": "sample_stage1_seg_000001",
                        "3": "sample_stage1_seg_000001",
                        "4": "sample_stage1_seg_000002",
                        "5": "sample_stage1_seg_000002",
                        "6": "sample_stage1_seg_000002",
                    },
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        with (self.batch_dir / "segment_prep" / "sample.segments.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "video_stem": "sample",
                    "segments": [
                        {
                            "segment_id": "legacy_seg_001",
                            "video_stem": "sample",
                            "segment_type": "stable_segment",
                            "start_frame": 1,
                            "end_frame": 2,
                            "representative_frame": 1,
                            "track_ids": [11],
                            "frame_count": 2,
                        }
                    ],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        with (self.batch_dir / "segment_prep" / "sample.segment_frames.json").open("w", encoding="utf-8") as f:
            json.dump(
                {"video_stem": "sample", "frame_to_segment": {"1": "legacy_seg_001", "2": "legacy_seg_001"}},
                f,
                ensure_ascii=False,
                indent=2,
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
                    "imu_count": "2",
                    "imu_paths": "imu_a.csv;imu_b.csv",
                    "pseudo_label_path": str(self.batch_dir / "pseudo_labels" / "sample.auto.csv"),
                }
            )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _subject_module(self):
        return importlib.import_module("application.step3_human_stage_1.ui_human_stage_1_server")

    def _make_state(self):
        mod = self._subject_module()
        state = mod.HumanStage1State(
            batch_dir=self.batch_dir,
            static_dir=Path("codes/application/step3_human_stage_1/web"),
            seed=123,
            reset_storage=True,
        )
        state.initialize()
        return state

    def _write_video(self, path: Path) -> None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, 30.0, (160, 120))
        self.assertTrue(writer.isOpened())
        for _ in range(6):
            frame = np.full((120, 160, 3), 180, dtype=np.uint8)
            writer.write(frame)
        writer.release()

    def test_human_stage_1_server_reads_human_stage_1_prep_only(self) -> None:
        state = self._make_state()

        payload = state.assign_next_segment("annotator_stage1")

        self.assertEqual(payload["segment"]["segment_id"], "sample_stage1_seg_000001")
        self.assertEqual(payload["segment"]["segment_type"], "stable_segment")
        self.assertEqual(payload["frame"]["frame_index"], 2)
        self.assertNotEqual(payload["segment"]["segment_id"], "legacy_seg_001")

    def test_human_stage_1_server_returns_single_frame_coarse_task_payload(self) -> None:
        state = self._make_state()

        stable_payload = state.assign_next_segment("annotator_stage1")
        repair_payload = state.segment_detail("sample_stage1_seg_000002")

        self.assertEqual(stable_payload["frame"]["frame_index"], 2)
        self.assertEqual(repair_payload["frame"]["frame_index"], 5)
        self.assertEqual(stable_payload["allowed_decisions"], ["ai_match", "absent", "needs_manual"])
        self.assertEqual(repair_payload["allowed_decisions"], ["ai_match", "absent", "needs_manual"])
        self.assertEqual(stable_payload["slot_names"], [f"p{i}" for i in range(1, 9)])
        self.assertEqual(
            stable_payload["slot_display_names"],
            {
                "p1": "P1(赵宇轩)",
                "p2": "P2(张络屹)",
                "p3": "P3(Alison)",
                "p4": "P4(刘浩贤)",
                "p5": "P5(何炳毅)",
                "p6": "P6(李泓睿)",
                "p7": "P7(梁芳舟)",
                "p8": "P8(谢灵韵)",
            },
        )
        self.assertFalse(stable_payload.get("manual_draw_enabled", False))
        self.assertFalse(repair_payload.get("manual_draw_enabled", False))

    def test_human_stage_1_server_returns_history_based_recommendations(self) -> None:
        state = self._make_state()
        state.submit_segment(
            "annotator_history_a",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"},
                    {"slot": "p2", "decision_type": "ai_match", "ai_track_id": "12"},
                ],
            },
        )
        state.submit_segment(
            "annotator_history_b",
            "sample_stage1_seg_000002",
            {
                "segment_id": "sample_stage1_seg_000002",
                "video_stem": "sample",
                "frame_index": 5,
                "slot_decisions": [
                    {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"},
                    {"slot": "p2", "decision_type": "ai_match", "ai_track_id": "12"},
                ],
            },
        )
        state.submit_segment(
            "annotator_history_c",
            "sample_stage1_seg_000002",
            {
                "segment_id": "sample_stage1_seg_000002",
                "video_stem": "sample",
                "frame_index": 5,
                "slot_decisions": [
                    {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "12"},
                    {"slot": "p2", "decision_type": "absent", "ai_track_id": ""},
                ],
            },
        )

        payload = state.assign_next_segment("annotator_stage1")
        rec_by_slot = {item["slot"]: item for item in payload["frame"]["recommendations"]}

        self.assertEqual(rec_by_slot["p1"]["ai_track_id"], "11")
        self.assertEqual(rec_by_slot["p1"]["vote_count"], 2)
        self.assertEqual(rec_by_slot["p2"]["ai_track_id"], "12")
        self.assertEqual(rec_by_slot["p2"]["vote_count"], 2)

    def test_human_stage_1_server_persists_ai_match_absent_needs_manual(self) -> None:
        state = self._make_state()

        result = state.submit_segment(
            "annotator_stage1",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"},
                    {"slot": "p2", "decision_type": "absent", "ai_track_id": ""},
                    {"slot": "p3", "decision_type": "needs_manual", "ai_track_id": ""},
                ],
            },
        )

        self.assertEqual(result["segment_id"], "sample_stage1_seg_000001")
        self.assertEqual(result["frame_index"], 2)
        self.assertEqual(result["submitted_slot_count"], 3)
        with closing(sqlite3.connect(state.db_path)) as conn:
            row = conn.execute(
                """
                SELECT segment_id, segment_type, frame_index, slot_decisions_json
                FROM coarse_labels
                WHERE annotator_id=?
                """,
                ("annotator_stage1",),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "sample_stage1_seg_000001")
        self.assertEqual(row[1], "stable_segment")
        self.assertEqual(row[2], 2)
        stored = json.loads(row[3])
        self.assertEqual(
            [(item["slot"], item["decision_type"], item["ai_track_id"]) for item in stored],
            [
                ("p1", "ai_match", "11"),
                ("p2", "absent", ""),
                ("p3", "needs_manual", ""),
            ],
        )

    def test_human_stage_1_server_lists_annotation_history_and_detail(self) -> None:
        state = self._make_state()
        result = state.submit_segment(
            "annotator_stage1",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {
                        "slot": "p1",
                        "decision_type": "ai_match",
                        "ai_track_id": "11",
                        "selection_source": "recommended_confirmed",
                    },
                    {"slot": "p2", "decision_type": "absent", "ai_track_id": ""},
                ],
            },
        )

        history = state.list_annotations_for_annotator("annotator_stage1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["annotation_id"], result["annotation_id"])
        self.assertIn("P1(赵宇轩):ai_match(11|recommended_confirmed)", history[0]["slots_summary"])
        self.assertIn("P2(张络屹):absent", history[0]["slots_summary"])

        detail = state.annotation_detail("annotator_stage1", result["annotation_id"])
        self.assertEqual(detail["annotation"]["annotation_id"], result["annotation_id"])
        self.assertEqual(detail["frame"]["frame_index"], 2)
        self.assertEqual(detail["annotation"]["slot_decisions"][0]["slot"], "p1")

    def test_human_stage_1_server_uses_named_slot_labels_in_history_summary(self) -> None:
        state = self._make_state()
        result = state.submit_segment(
            "annotator_stage1",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {
                        "slot": "p1",
                        "decision_type": "ai_match",
                        "ai_track_id": "11",
                        "selection_source": "recommended_confirmed",
                    },
                    {"slot": "p8", "decision_type": "absent", "ai_track_id": ""},
                ],
            },
        )

        history = state.list_annotations_for_annotator("annotator_stage1")

        self.assertEqual(history[0]["annotation_id"], result["annotation_id"])
        self.assertIn("P1(赵宇轩):ai_match(11|recommended_confirmed)", history[0]["slots_summary"])
        self.assertIn("P8(谢灵韵):absent", history[0]["slots_summary"])

    def test_human_stage_1_server_updates_existing_annotation(self) -> None:
        state = self._make_state()
        result = state.submit_segment(
            "annotator_stage1",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {
                        "slot": "p1",
                        "decision_type": "ai_match",
                        "ai_track_id": "11",
                        "selection_source": "manual_selected",
                    },
                    {"slot": "p2", "decision_type": "absent", "ai_track_id": ""},
                ],
            },
        )

        update_result = state.update_annotation(
            "annotator_stage1",
            {
                "annotation_id": result["annotation_id"],
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {
                        "slot": "p1",
                        "decision_type": "ai_match",
                        "ai_track_id": "11",
                        "selection_source": "recommended_confirmed",
                    },
                    {"slot": "p2", "decision_type": "needs_manual", "ai_track_id": ""},
                ],
            },
        )

        self.assertEqual(update_result["annotation_id"], result["annotation_id"])
        detail = state.annotation_detail("annotator_stage1", result["annotation_id"])
        self.assertEqual(
            [
                (
                    item["slot"],
                    item["decision_type"],
                    item["ai_track_id"],
                    item["selection_source"],
                )
                for item in detail["annotation"]["slot_decisions"]
            ],
            [
                ("p1", "ai_match", "11", "recommended_confirmed"),
                ("p2", "needs_manual", "", "needs_manual"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
