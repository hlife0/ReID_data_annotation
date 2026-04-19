#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class TwoStageRepoSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent.parent.parent
        self.codes_root = self.repo_root / "codes"
        self.docs_root = self.repo_root / "docs"

    def test_active_application_surface_excludes_one_shot_result_stack(self) -> None:
        self.assertFalse(
            (self.codes_root / "application" / "ui_review_result_server.py").exists(),
            "ui_review_result_server.py should be archived out of active application/",
        )
        self.assertFalse(
            (self.codes_root / "application" / "ui_review_result_web").exists(),
            "ui_review_result_web should be archived out of active application/",
        )

    def test_active_process_surface_excludes_one_shot_downstream_scripts(self) -> None:
        self.assertFalse(
            (self.codes_root / "process" / "process_annotation_analysis.py").exists(),
            "process_annotation_analysis.py should be archived out of active process/",
        )
        self.assertFalse(
            (self.codes_root / "process" / "process_final_annotation_batch.py").exists(),
            "process_final_annotation_batch.py should be archived out of active process/",
        )
        self.assertFalse(
            (self.codes_root / "process" / "render_final_annotations_video.py").exists(),
            "render_final_annotations_video.py should be archived out of active process/",
        )
        self.assertFalse(
            (self.codes_root / "process" / "process_imu_mapping_batch.py").exists(),
            "process_imu_mapping_batch.py should be archived out of active process/",
        )
        self.assertFalse(
            (self.docs_root / "REQUIREMENTS_IMU_MAPPING.md").exists(),
            "REQUIREMENTS_IMU_MAPPING.md should be archived out of active docs/",
        )

    def test_active_review_server_no_longer_exposes_frame_mode_api(self) -> None:
        source = (
            self.codes_root / "application" / "step5_stage2_review" / "ui_review_server.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("/api/next_frame", source)
        self.assertNotIn('path == "/api/submit"', source)
        self.assertNotIn("def assign_next_frame(", source)
        self.assertNotIn("def submit_and_assign_next(", source)

    def test_archive_contains_restoration_notes_for_one_shot_paths(self) -> None:
        self.assertTrue(
            (self.codes_root / "archive" / "legacy_one_shot_annotation" / "README.md").is_file(),
            "expected archive README for one-shot annotation code",
        )
        self.assertTrue(
            (self.docs_root / "archive" / "legacy_one_shot_annotation" / "SCHEMA.md").is_file(),
            "expected schema notes for archived one-shot annotation stack",
        )
        self.assertTrue(
            (self.codes_root / "archive" / "legacy_auxiliary" / "README.md").is_file(),
            "expected archive README for inactive auxiliary code",
        )
        self.assertTrue(
            (self.docs_root / "archive" / "legacy_auxiliary" / "README.md").is_file(),
            "expected archive README for inactive auxiliary docs",
        )


if __name__ == "__main__":
    unittest.main()
