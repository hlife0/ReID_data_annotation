#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from process import process_prelabel_batch as mod


class StepA0InputInspectionTests(unittest.TestCase):
    def test_discovers_video_stems_from_required_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            required_root = Path(tmpdir) / "required"
            for stem in ["20260410_200624", "20260410_200724"]:
                (required_root / stem / "video").mkdir(parents=True, exist_ok=True)
            stems = mod.discover_target_video_stems(required_root)
            self.assertEqual(stems, ["20260410_200624", "20260410_200724"])

    def test_allows_more_than_two_imu_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            required_root = Path(tmpdir) / "required"
            stem = "sample_video"
            video_dir = required_root / stem / "video"
            imu_dir = required_root / stem / "imu"
            logs_dir = Path(tmpdir) / "logs"
            video_dir.mkdir(parents=True, exist_ok=True)
            imu_dir.mkdir(parents=True, exist_ok=True)

            (video_dir / f"{stem}_retimed.mp4").write_bytes(b"mp4")
            (video_dir / f"{stem}_frame_timestamps_retimed.csv").write_text(
                "frame_index,timestamp_ms\n1,1000\n",
                encoding="utf-8",
            )
            for idx in range(3):
                (imu_dir / f"{stem}_imu_{idx}.csv").write_text("epoch_ms\n1000\n", encoding="utf-8")

            logger = mod.RunLogger(logs_dir / "run.log", logs_dir / "errors.log")
            tasks = mod.step_a0_input_inspection(required_root, logger)

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].status, "todo")
            self.assertEqual(len(tasks[0].imu_paths), 3)


if __name__ == "__main__":
    unittest.main()
