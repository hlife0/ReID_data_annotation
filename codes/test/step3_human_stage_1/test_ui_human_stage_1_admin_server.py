#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class HumanStage1AdminServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        self.stage1_prep_dir = self.batch_dir / "human_stage_1_prep"
        self.stage1_dir = self.batch_dir / "human_stage_1"
        self.stage1_prep_dir.mkdir(parents=True)
        self.stage1_dir.mkdir(parents=True)
        self.db_path = self.stage1_dir / "ui_human_stage_1.sqlite3"

        (self.stage1_prep_dir / "sample_a.segments.json").write_text(
            json.dumps(
                {
                    "video_stem": "sample_a",
                    "segments": [
                        {
                            "segment_id": "seg_a_001",
                            "video_stem": "sample_a",
                            "segment_type": "stable_segment",
                            "start_frame": 1,
                            "end_frame": 3,
                            "representative_frame": 2,
                            "track_ids": [11, 12],
                            "frame_count": 3,
                            "source_segment_ids": ["fp_a_001"],
                            "source_segment_types": ["stable_segment"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (self.stage1_prep_dir / "sample_b.segments.json").write_text(
            json.dumps(
                {
                    "video_stem": "sample_b",
                    "segments": [
                        {
                            "segment_id": "seg_b_001",
                            "video_stem": "sample_b",
                            "segment_type": "repair_window",
                            "start_frame": 10,
                            "end_frame": 14,
                            "representative_frame": 12,
                            "track_ids": [21],
                            "frame_count": 5,
                            "source_segment_ids": ["fp_b_001", "fp_b_002"],
                            "source_segment_types": ["non_simple_single_frame", "stable_segment"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE coarse_labels (
                    annotation_id TEXT PRIMARY KEY,
                    segment_id TEXT NOT NULL,
                    segment_type TEXT NOT NULL,
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    annotator_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    slot_decisions_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE stage1_assignment_queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segment_id TEXT NOT NULL,
                    video_stem TEXT NOT NULL,
                    pass_index INTEGER NOT NULL,
                    queue_order INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    annotation_id TEXT NOT NULL DEFAULT '',
                    completed_by TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO coarse_labels (
                    annotation_id,
                    segment_id,
                    segment_type,
                    video_stem,
                    frame_index,
                    annotator_id,
                    submitted_at,
                    slot_decisions_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "ann_a_001",
                        "seg_a_001",
                        "stable_segment",
                        "sample_a",
                        2,
                        "annotator_a",
                        "2026-04-21T10:00:00.000",
                        json.dumps([{"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"}], ensure_ascii=False),
                    ),
                    (
                        "ann_b_001",
                        "seg_a_001",
                        "stable_segment",
                        "sample_a",
                        2,
                        "annotator_b",
                        "2026-04-21T10:00:01.000",
                        json.dumps([{"slot": "p2", "decision_type": "absent", "ai_track_id": ""}], ensure_ascii=False),
                    ),
                    (
                        "ann_a_002",
                        "seg_b_001",
                        "repair_window",
                        "sample_b",
                        12,
                        "annotator_a",
                        "2026-04-21T10:00:02.000",
                        json.dumps([{"slot": "p3", "decision_type": "needs_manual", "ai_track_id": ""}], ensure_ascii=False),
                    ),
                ],
            )
            conn.executemany(
                """
                INSERT INTO stage1_assignment_queue (
                    queue_id,
                    segment_id,
                    video_stem,
                    pass_index,
                    queue_order,
                    status,
                    annotation_id,
                    completed_by,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, "seg_a_001", "sample_a", 1, 1, "completed", "ann_a_001", "annotator_a", "2026-04-21T10:00:00.000"),
                    (2, "seg_b_001", "sample_b", 1, 2, "pending", "", "", ""),
                    (3, "seg_a_001", "sample_a", 2, 3, "completed", "ann_b_001", "annotator_b", "2026-04-21T10:00:01.000"),
                    (4, "seg_b_001", "sample_b", 2, 4, "completed", "ann_a_002", "annotator_a", "2026-04-21T10:00:02.000"),
                ],
            )
            conn.commit()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _subject_module(self):
        return importlib.import_module("application.step3_human_stage_1.ui_human_stage_1_admin_server")

    def _make_state(self):
        subject = self._subject_module()
        state = subject.HumanStage1AdminState(
            batch_dir=self.batch_dir,
            static_dir=Path("codes/application/step3_human_stage_1/admin_web"),
        )
        state.initialize()
        return state

    def test_human_stage_1_admin_overview_uses_stage1_queue_metrics(self) -> None:
        state = self._make_state()

        overview = state.overview()

        self.assertEqual(overview["segment_count"], 2)
        self.assertEqual(overview["queue_total"], 4)
        self.assertEqual(overview["queue_completed"], 3)
        self.assertEqual(overview["pass1_completed"], 1)
        self.assertEqual(overview["pass2_completed"], 2)
        self.assertEqual(overview["annotation_count"], 3)
        self.assertEqual(overview["annotator_count"], 2)
        self.assertEqual(overview["current_queue"]["segment_id"], "seg_b_001")
        self.assertEqual(overview["segment_annotation_bins"], [{"label": "0", "count": 0}, {"label": "1", "count": 1}, {"label": "2", "count": 1}, {"label": "3+", "count": 0}])

    def test_human_stage_1_admin_annotator_stats_reports_completed_submissions(self) -> None:
        state = self._make_state()

        payload = state.annotator_stats()

        annotators = {item["annotator_id"]: item for item in payload["annotators"]}
        self.assertEqual(annotators["annotator_a"]["annotation_count"], 2)
        self.assertEqual(annotators["annotator_a"]["completed_submissions"], 2)
        self.assertAlmostEqual(annotators["annotator_a"]["progress_ratio"], 2 / 2600, places=6)
        self.assertEqual(annotators["annotator_b"]["annotation_count"], 1)
        self.assertEqual(annotators["annotator_b"]["completed_submissions"], 1)

        recent = payload["recent_annotations"]
        self.assertEqual(recent[0]["annotation_id"], "ann_a_002")
        self.assertEqual(recent[0]["pass_index"], 2)
        self.assertIn("P3", recent[0]["slots_summary"])

    def test_human_stage_1_admin_segment_detail_includes_queue_and_annotations(self) -> None:
        state = self._make_state()

        detail = state.segment_detail("seg_a_001")

        self.assertEqual(detail["segment"]["segment_id"], "seg_a_001")
        self.assertEqual(detail["segment"]["frame_count"], 3)
        self.assertEqual(len(detail["queue_items"]), 2)
        self.assertEqual(detail["queue_items"][0]["pass_index"], 1)
        self.assertEqual(detail["queue_items"][1]["pass_index"], 2)
        self.assertEqual(len(detail["annotations"]), 2)
        self.assertEqual(detail["annotations"][0]["annotation_id"], "ann_a_001")

    def test_human_stage_1_admin_segments_lists_stage1_segment_summaries(self) -> None:
        state = self._make_state()

        rows = state.segments()

        self.assertEqual([item["segment_id"] for item in rows], ["seg_a_001", "seg_b_001"])
        self.assertEqual(rows[0]["annotation_count"], 2)
        self.assertEqual(rows[1]["annotation_count"], 1)


if __name__ == "__main__":
    unittest.main()
