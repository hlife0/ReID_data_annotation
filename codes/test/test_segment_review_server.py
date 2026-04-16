#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import cv2
import numpy as np

from application import ui_review_server as mod


class SegmentReviewServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "pseudo_labels").mkdir(parents=True)
        (self.batch_dir / "segment_prep").mkdir(parents=True)
        (self.batch_dir / "assets").mkdir(parents=True)
        self.video_path = self.batch_dir / "assets" / "sample.mp4"
        self.ts_path = self.batch_dir / "assets" / "sample_frame_timestamps.csv"
        self._write_video(self.video_path)
        self.ts_path.write_text(
            "frame_index,timestamp_ms\n1,1000\n2,1033.333\n3,1066.667\n4,1100\n",
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
            "sample,4,1100,11,20,26,32,42,0.40\n"
            "sample,4,1100,12,84,18,32,42,0.94\n",
            encoding="utf-8",
        )
        with (self.batch_dir / "segment_prep" / "sample.segments.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "video_stem": "sample",
                    "segments": [
                        {
                            "segment_id": "sample_seg_001",
                            "video_stem": "sample",
                            "segment_type": "stable_segment",
                            "start_frame": 1,
                            "end_frame": 3,
                            "representative_frame": 2,
                            "track_ids": [11, 12],
                            "frame_count": 3,
                        },
                        {
                            "segment_id": "sample_seg_002",
                            "video_stem": "sample",
                            "segment_type": "non_simple_single_frame",
                            "start_frame": 4,
                            "end_frame": 4,
                            "representative_frame": 4,
                            "track_ids": [11, 12],
                            "frame_count": 1,
                        },
                    ],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        with (self.batch_dir / "segment_prep" / "sample.segment_frames.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "video_stem": "sample",
                    "frame_to_segment": {
                        "1": "sample_seg_001",
                        "2": "sample_seg_001",
                        "3": "sample_seg_001",
                        "4": "sample_seg_002",
                    },
                },
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

    def _write_video(self, path: Path) -> None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, 30.0, (160, 120))
        self.assertTrue(writer.isOpened())
        for _ in range(4):
            frame = np.full((120, 160, 3), 180, dtype=np.uint8)
            writer.write(frame)
        writer.release()

    def _make_state(self) -> mod.AnnotationState:
        state = mod.AnnotationState(
            batch_dir=self.batch_dir,
            static_dir=Path("codes/application/ui_review_web"),
            seed=123,
            reset_storage=True,
            frame_cache_dir=None,
            frame_cache_prewarm=False,
            frame_cache_max=0,
            frame_cache_quality=88,
        )
        state.initialize()
        return state

    def _write_segment_prep(self, segments: list[dict[str, object]], frame_to_segment: dict[str, str]) -> None:
        with (self.batch_dir / "segment_prep" / "sample.segments.json").open("w", encoding="utf-8") as f:
            json.dump({"video_stem": "sample", "segments": segments}, f, ensure_ascii=False, indent=2)
        with (self.batch_dir / "segment_prep" / "sample.segment_frames.json").open("w", encoding="utf-8") as f:
            json.dump({"video_stem": "sample", "frame_to_segment": frame_to_segment}, f, ensure_ascii=False, indent=2)

    def _write_pseudo_rows(self, rows: list[str]) -> None:
        (self.batch_dir / "pseudo_labels" / "sample.auto.csv").write_text(
            "video_stem,frame_index,timestamp_ms,track_id,bbox_x,bbox_y,bbox_w,bbox_h,score\n" + "".join(rows),
            encoding="utf-8",
        )

    def _insert_annotation(
        self,
        state: mod.AnnotationState,
        annotator_id: str,
        frame_index: int,
        slots: list[dict[str, object]],
    ) -> None:
        record = {
            "annotation_id": f"ann_test_{uuid.uuid4().hex[:8]}",
            "video_stem": "sample",
            "frame_index": frame_index,
            "timestamp_ms": {1: 1000.0, 2: 1033.333, 3: 1066.667, 4: 1100.0}[frame_index],
            "annotator_id": annotator_id,
            "submitted_at": "2026-04-17T00:00:00.000",
            "slots_json": json.dumps(state._validate_slots_payload(slots), ensure_ascii=False),
        }
        conn = state._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            state._insert_annotation(conn, record)
            conn.execute(
                """
                UPDATE frame_counts
                SET annotation_count = annotation_count + 1
                WHERE video_stem=? AND frame_index=?
                """,
                ("sample", frame_index),
            )
            conn.commit()
        finally:
            conn.close()

    def test_segment_pool_loads_and_returns_representative_frame_payload(self) -> None:
        state = self._make_state()
        payload = state.assign_next_segment("annotator_segment")
        self.assertEqual(payload["segment"]["segment_id"], "sample_seg_001")
        self.assertEqual(payload["segment"]["segment_type"], "stable_segment")
        self.assertEqual(payload["frame"]["frame_index"], 2)
        self.assertEqual(payload["segment"]["track_ids"], [11, 12])

    def test_stable_segment_submit_expands_range_and_inferrs_track_from_manual_box(self) -> None:
        state = self._make_state()
        result = state.submit_segment(
            "annotator_segment",
            "sample_seg_001",
            {
                "segment_id": "sample_seg_001",
                "video_stem": "sample",
                "frame_index": 2,
                "timestamp_ms": 1033.333,
                "slots": [
                    {
                        "slot": "p1",
                        "bbox_x": 16,
                        "bbox_y": 24,
                        "bbox_w": 34,
                        "bbox_h": 44,
                        "source": "manual_param",
                        "ai_track_id": "",
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
        self.assertEqual(result["submitted_frame_count"], 3)
        history = state.list_annotations_for_annotator("annotator_segment")
        self.assertEqual(len(history), 3)
        details = [
            state.annotation_detail("annotator_segment", item["annotation_id"])
            for item in history
        ]
        by_frame = {item["frame"]["frame_index"]: item for item in details}
        self.assertEqual(by_frame[1]["annotation"]["slots"][0]["ai_track_id"], "11")
        self.assertEqual(by_frame[2]["annotation"]["slots"][0]["bbox_x"], 16.0)
        self.assertEqual(by_frame[3]["annotation"]["slots"][0]["bbox_x"], 18.0)

    def test_non_simple_single_frame_submit_writes_single_frame(self) -> None:
        state = self._make_state()
        result = state.submit_segment(
            "annotator_segment_single",
            "sample_seg_002",
            {
                "segment_id": "sample_seg_002",
                "video_stem": "sample",
                "frame_index": 4,
                "timestamp_ms": 1100,
                "slots": [
                    {
                        "slot": "p1",
                        "bbox_x": 20,
                        "bbox_y": 26,
                        "bbox_w": 32,
                        "bbox_h": 42,
                        "source": "manual_draw",
                        "ai_track_id": "",
                    },
                    {
                        "slot": "p2",
                        "bbox_x": 84,
                        "bbox_y": 18,
                        "bbox_w": 32,
                        "bbox_h": 42,
                        "source": "ai",
                        "ai_track_id": "12",
                    },
                ],
            },
        )
        self.assertEqual(result["submitted_frame_count"], 1)
        history = state.list_annotations_for_annotator("annotator_segment_single")
        self.assertEqual(len(history), 1)
        detail = state.annotation_detail("annotator_segment_single", history[0]["annotation_id"])
        self.assertEqual(detail["frame"]["frame_index"], 4)

    def test_stable_segment_payload_includes_history_based_recommendations(self) -> None:
        state = self._make_state()
        self._insert_annotation(
            state,
            "annotator_history_a",
            1,
            [
                {
                    "slot": "p1",
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "source": "ai",
                    "ai_track_id": "11",
                },
                {
                    "slot": "p2",
                    "bbox_x": 80,
                    "bbox_y": 18,
                    "bbox_w": 32,
                    "bbox_h": 42,
                    "source": "ai",
                    "ai_track_id": "12",
                },
            ],
        )
        self._insert_annotation(
            state,
            "annotator_history_b",
            3,
            [
                {
                    "slot": "p1",
                    "bbox_x": 14,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "source": "manual_param",
                    "ai_track_id": "11",
                },
                {
                    "slot": "p2",
                    "bbox_x": 84,
                    "bbox_y": 18,
                    "bbox_w": 32,
                    "bbox_h": 42,
                    "source": "manual_param",
                    "ai_track_id": "12",
                },
            ],
        )

        payload = state.assign_next_segment("annotator_segment")
        recommendations = payload["frame"]["recommendations"]
        rec_by_slot = {item["slot"]: item for item in recommendations}

        self.assertEqual(rec_by_slot["p1"]["ai_track_id"], "11")
        self.assertEqual(rec_by_slot["p2"]["ai_track_id"], "12")

    def test_stable_segment_payload_skips_ambiguous_history_recommendation(self) -> None:
        state = self._make_state()
        self._insert_annotation(
            state,
            "annotator_history_a",
            1,
            [
                {
                    "slot": "p1",
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "source": "ai",
                    "ai_track_id": "11",
                },
                {
                    "slot": "p2",
                    "bbox_x": 80,
                    "bbox_y": 18,
                    "bbox_w": 32,
                    "bbox_h": 42,
                    "source": "ai",
                    "ai_track_id": "12",
                },
            ],
        )
        self._insert_annotation(
            state,
            "annotator_history_b",
            3,
            [
                {
                    "slot": "p2",
                    "bbox_x": 14,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "source": "manual_param",
                    "ai_track_id": "11",
                },
            ],
        )

        payload = state.assign_next_segment("annotator_segment")
        recommendations = payload["frame"]["recommendations"]
        rec_by_track = {item["ai_track_id"]: item for item in recommendations}

        self.assertNotIn("11", rec_by_track)
        self.assertEqual(rec_by_track["12"]["slot"], "p2")

    def test_non_simple_segment_payload_includes_history_based_recommendations(self) -> None:
        state = self._make_state()
        self._insert_annotation(
            state,
            "annotator_history_a",
            1,
            [
                {
                    "slot": "p1",
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "source": "ai",
                    "ai_track_id": "11",
                },
                {
                    "slot": "p2",
                    "bbox_x": 80,
                    "bbox_y": 18,
                    "bbox_w": 32,
                    "bbox_h": 42,
                    "source": "ai",
                    "ai_track_id": "12",
                },
            ],
        )

        state.submit_segment(
            "annotator_segment_history",
            "sample_seg_001",
            {
                "segment_id": "sample_seg_001",
                "video_stem": "sample",
                "frame_index": 2,
                "timestamp_ms": 1033.333,
                "slots": [
                    {
                        "slot": "p1",
                        "bbox_x": 12,
                        "bbox_y": 20,
                        "bbox_w": 30,
                        "bbox_h": 40,
                        "source": "ai",
                        "ai_track_id": "11",
                    },
                    {
                        "slot": "p2",
                        "bbox_x": 82,
                        "bbox_y": 18,
                        "bbox_w": 32,
                        "bbox_h": 42,
                        "source": "ai",
                        "ai_track_id": "12",
                    },
                ],
            },
        )

        payload = state.segment_detail("sample_seg_002")
        recommendations = payload["frame"]["recommendations"]
        rec_by_slot = {item["slot"]: item for item in recommendations}

        self.assertEqual(rec_by_slot["p1"]["ai_track_id"], "11")
        self.assertEqual(rec_by_slot["p2"]["ai_track_id"], "12")

    def test_repair_window_payload_includes_anchor_sequence(self) -> None:
        self._write_segment_prep(
            [
                {
                    "segment_id": "sample_seg_001",
                    "video_stem": "sample",
                    "segment_type": "repair_window",
                    "start_frame": 1,
                    "end_frame": 4,
                    "representative_frame": 1,
                    "track_ids": [11, 12],
                    "frame_count": 4,
                    "anchor_candidates": [1, 4],
                    "repairability_score": 0.92,
                    "fragmentation_score": 7,
                    "expected_gain": 2,
                    "trigger_reason": "fragment_cluster",
                }
            ],
            {"1": "sample_seg_001", "2": "sample_seg_001", "3": "sample_seg_001", "4": "sample_seg_001"},
        )

        state = self._make_state()
        payload = state.assign_next_segment("annotator_repair")

        self.assertEqual(payload["segment"]["segment_type"], "repair_window")
        self.assertEqual(payload["frame"]["frame_index"], 1)
        self.assertEqual(payload["repair_window"]["anchor_frames"], [1, 4])
        self.assertEqual(payload["repair_window"]["current_anchor_index"], 0)
        self.assertEqual(payload["repair_window"]["anchor_count"], 2)

    def test_repair_window_submit_writes_filled_frame_records(self) -> None:
        self._write_segment_prep(
            [
                {
                    "segment_id": "sample_seg_001",
                    "video_stem": "sample",
                    "segment_type": "repair_window",
                    "start_frame": 1,
                    "end_frame": 4,
                    "representative_frame": 1,
                    "track_ids": [11, 12],
                    "frame_count": 4,
                    "anchor_candidates": [1, 4],
                    "repairability_score": 0.92,
                    "fragmentation_score": 7,
                    "expected_gain": 2,
                    "trigger_reason": "fragment_cluster",
                }
            ],
            {"1": "sample_seg_001", "2": "sample_seg_001", "3": "sample_seg_001", "4": "sample_seg_001"},
        )

        state = self._make_state()
        result = state.submit_segment(
            "annotator_repair",
            "sample_seg_001",
            {
                "segment_id": "sample_seg_001",
                "anchor_annotations": [
                    {
                        "video_stem": "sample",
                        "frame_index": 1,
                        "timestamp_ms": 1000,
                        "slots": [
                            {
                                "slot": "p1",
                                "bbox_x": 10,
                                "bbox_y": 20,
                                "bbox_w": 30,
                                "bbox_h": 40,
                                "source": "ai",
                                "ai_track_id": "11",
                            },
                            {
                                "slot": "p2",
                                "bbox_x": 80,
                                "bbox_y": 18,
                                "bbox_w": 32,
                                "bbox_h": 42,
                                "source": "ai",
                                "ai_track_id": "12",
                            },
                        ],
                    },
                    {
                        "video_stem": "sample",
                        "frame_index": 4,
                        "timestamp_ms": 1100,
                        "slots": [
                            {
                                "slot": "p1",
                                "bbox_x": 20,
                                "bbox_y": 26,
                                "bbox_w": 32,
                                "bbox_h": 42,
                                "source": "ai",
                                "ai_track_id": "11",
                            },
                            {
                                "slot": "p2",
                                "bbox_x": 84,
                                "bbox_y": 18,
                                "bbox_w": 32,
                                "bbox_h": 42,
                                "source": "ai",
                                "ai_track_id": "12",
                            },
                        ],
                    },
                ],
            },
        )

        self.assertEqual(result["submitted_frame_count"], 4)
        history = state.list_annotations_for_annotator("annotator_repair")
        self.assertEqual(len(history), 4)
        details = [state.annotation_detail("annotator_repair", item["annotation_id"]) for item in history]
        by_frame = {item["frame"]["frame_index"]: item for item in details}
        self.assertEqual(by_frame[2]["annotation"]["slots"][0]["ai_track_id"], "11")
        self.assertEqual(by_frame[3]["annotation"]["slots"][1]["ai_track_id"], "12")

    def test_repair_window_submit_returns_fallback_when_track_missing_midwindow(self) -> None:
        self._write_pseudo_rows(
            [
                "sample,1,1000,11,10,20,30,40,0.95\n",
                "sample,1,1000,12,80,18,32,42,0.94\n",
                "sample,2,1033.333,12,82,18,32,42,0.94\n",
                "sample,3,1066.667,11,14,20,30,40,0.95\n",
                "sample,3,1066.667,12,84,18,32,42,0.94\n",
                "sample,4,1100,11,20,26,32,42,0.94\n",
                "sample,4,1100,12,84,18,32,42,0.94\n",
            ]
        )
        self._write_segment_prep(
            [
                {
                    "segment_id": "sample_seg_001",
                    "video_stem": "sample",
                    "segment_type": "repair_window",
                    "start_frame": 1,
                    "end_frame": 4,
                    "representative_frame": 1,
                    "track_ids": [11, 12],
                    "frame_count": 4,
                    "anchor_candidates": [1, 4],
                    "repairability_score": 0.92,
                    "fragmentation_score": 7,
                    "expected_gain": 2,
                    "trigger_reason": "fragment_cluster",
                }
            ],
            {"1": "sample_seg_001", "2": "sample_seg_001", "3": "sample_seg_001", "4": "sample_seg_001"},
        )

        state = self._make_state()
        result = state.submit_segment(
            "annotator_repair",
            "sample_seg_001",
            {
                "segment_id": "sample_seg_001",
                "anchor_annotations": [
                    {
                        "video_stem": "sample",
                        "frame_index": 1,
                        "timestamp_ms": 1000,
                        "slots": [
                            {
                                "slot": "p1",
                                "bbox_x": 10,
                                "bbox_y": 20,
                                "bbox_w": 30,
                                "bbox_h": 40,
                                "source": "ai",
                                "ai_track_id": "11",
                            },
                            {
                                "slot": "p2",
                                "bbox_x": 80,
                                "bbox_y": 18,
                                "bbox_w": 32,
                                "bbox_h": 42,
                                "source": "ai",
                                "ai_track_id": "12",
                            },
                        ],
                    },
                    {
                        "video_stem": "sample",
                        "frame_index": 4,
                        "timestamp_ms": 1100,
                        "slots": [
                            {
                                "slot": "p1",
                                "bbox_x": 20,
                                "bbox_y": 26,
                                "bbox_w": 32,
                                "bbox_h": 42,
                                "source": "ai",
                                "ai_track_id": "11",
                            },
                            {
                                "slot": "p2",
                                "bbox_x": 84,
                                "bbox_y": 18,
                                "bbox_w": 32,
                                "bbox_h": 42,
                                "source": "ai",
                                "ai_track_id": "12",
                            },
                        ],
                    },
                ],
            },
        )

        self.assertEqual(result["submitted_frame_count"], 0)
        self.assertEqual(result["fallback"]["reason"], "missing_ai_track")
        self.assertEqual(result["fallback"]["missing_frames"], [2])
        history = state.list_annotations_for_annotator("annotator_repair")
        self.assertEqual(history, [])


if __name__ == "__main__":
    unittest.main()
