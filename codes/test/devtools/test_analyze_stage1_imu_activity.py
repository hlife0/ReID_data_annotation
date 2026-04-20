#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path


class Stage1ImuActivityAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.batch_dir = Path(self.tmpdir.name) / "batch"
        (self.batch_dir / "manifests").mkdir(parents=True)
        (self.batch_dir / "assets").mkdir(parents=True)
        self.timestamp_path = self.batch_dir / "assets" / "sample_frame_timestamps.csv"
        self.video_path = self.batch_dir / "assets" / "sample.mp4"
        self.video_path.write_bytes(b"mp4")
        self._write_frame_timestamps(
            [
                (1, 1000.0),
                (2, 2000.0),
                (3, 3000.0),
                (4, 4000.0),
            ]
        )
        self.imu_a_path = self.batch_dir / "assets" / "sample_imu_a.csv"
        self.imu_b_path = self.batch_dir / "assets" / "sample_imu_b.csv"
        self._write_imu_csv(
            self.imu_a_path,
            device_name="imu_a",
            rows=[
                (900.0, 1.0, 0.0, 0.0),
                (2100.0, 1.0, 0.0, 0.0),
                (3100.0, 2.0, 0.0, 0.0),
            ],
        )
        self._write_imu_csv(
            self.imu_b_path,
            device_name="imu_b",
            rows=[
                (1800.0, 7.0, 0.0, 0.0),
                (3500.0, 8.0, 0.0, 0.0),
            ],
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
                    "imu_paths": f"{self.imu_a_path};{self.imu_b_path}",
                    "status": "todo",
                    "priority": "1",
                }
            )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _subject_module(self):
        return importlib.import_module("process.devtools.analyze_stage1_imu_activity")

    def _write_frame_timestamps(self, rows: list[tuple[int, float]]) -> None:
        with self.timestamp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame_index", "timestamp_ms"])
            for frame_index, timestamp_ms in rows:
                writer.writerow([frame_index, f"{timestamp_ms:.3f}"])

    def _write_imu_csv(
        self,
        path: Path,
        device_name: str,
        rows: list[tuple[float, float, float, float]],
    ) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "时间",
                    "设备名称",
                    "片上时间()",
                    "加速度X(g)",
                    "加速度Y(g)",
                    "加速度Z(g)",
                    "epoch_ms",
                    "source_folder",
                    "source_file",
                ]
            )
            for epoch_ms, acc_x, acc_y, acc_z in rows:
                writer.writerow(
                    [
                        " 19:56:31.968",
                        device_name,
                        " 2026-04-10 19:56:23:120",
                        f" {acc_x:.3f}",
                        f" {acc_y:.3f}",
                        f" {acc_z:.3f}",
                        f"{epoch_ms:.3f}",
                        "folder",
                        "file.csv",
                    ]
                )

    def test_analyze_batch_marks_only_payload_changes_as_active(self) -> None:
        subject = self._subject_module()

        result = subject.analyze_batch(batch_dir=self.batch_dir)

        self.assertEqual(result["session_count"], 1)
        session = result["sessions"][0]
        self.assertEqual(session["video_stem"], "sample")
        self.assertEqual([point["active_imu_ids"] for point in session["points"]], [[], ["imu_b"], [], ["imu_a", "imu_b"]])
        self.assertEqual([point["active_imu_count"] for point in session["points"]], [0, 1, 0, 2])

    def test_analyze_batch_uses_last_payload_for_duplicate_epoch(self) -> None:
        subject = self._subject_module()
        self._write_imu_csv(
            self.imu_a_path,
            device_name="imu_a",
            rows=[
                (900.0, 1.0, 0.0, 0.0),
                (2100.0, 1.0, 0.0, 0.0),
                (2100.0, 9.0, 0.0, 0.0),
            ],
        )

        result = subject.analyze_batch(batch_dir=self.batch_dir)

        session = result["sessions"][0]
        self.assertEqual(session["points"][2]["active_imu_ids"], ["imu_a"])
        self.assertEqual(session["points"][2]["active_imu_count"], 1)

    def test_analyze_batch_writes_per_session_json_and_summary(self) -> None:
        subject = self._subject_module()
        output_dir = self.batch_dir / "analysis" / "stage1_imu_activity"

        result = subject.analyze_batch(batch_dir=self.batch_dir, output_dir=output_dir)

        self.assertEqual(result["output_dir"], str(output_dir))
        self.assertTrue((output_dir / "sample.active_imu_timeline.json").exists())
        self.assertTrue((output_dir / "summary.json").exists())

        written_session = json.loads((output_dir / "sample.active_imu_timeline.json").read_text(encoding="utf-8"))
        self.assertEqual(written_session["time_axis"], "frame_timestamp_ms")
        self.assertEqual(written_session["points"][1]["active_imu_ids"], ["imu_b"])

        written_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(written_summary["session_count"], 1)
        self.assertEqual(written_summary["video_stems"], ["sample"])


if __name__ == "__main__":
    unittest.main()
