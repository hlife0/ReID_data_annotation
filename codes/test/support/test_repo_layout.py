#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class RepoLayoutTests(unittest.TestCase):
    def test_repository_uses_codes_directory_instead_of_codex(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        codes_root = repo_root / "codes"
        self.assertTrue(codes_root.is_dir(), "expected top-level codes/ directory")
        self.assertFalse((repo_root / "codex").exists(), "codex/ should have been renamed to codes/")
        self.assertTrue((codes_root / "application").is_dir(), "expected codes/application/ directory")
        self.assertTrue((codes_root / "process").is_dir(), "expected codes/process/ directory")
        self.assertTrue((codes_root / "test").is_dir(), "expected codes/test/ directory")
        self.assertTrue((codes_root / "README.md").is_file(), "expected codes/README.md")
        self.assertTrue((codes_root / "process" / "README.md").is_file(), "expected codes/process/README.md")

    def test_active_python_files_are_grouped_under_application_process_or_test(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        codes_root = repo_root / "codes"
        active_python = [
            path.relative_to(codes_root)
            for path in codes_root.glob("*.py")
            if path.is_file()
        ]
        self.assertEqual(
            active_python,
            [],
            f"expected no active Python files directly under codes/, found: {active_python}",
        )

    def test_process_readme_records_pipeline_order(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        readme = (repo_root / "codes" / "process" / "README.md").read_text(encoding="utf-8")
        self.assertIn("process_prelabel_batch.py", readme)
        self.assertIn("process_segment_review_prep.py", readme)
        self.assertIn("application/step5_stage2_review/ui_review_server.py", readme)
        self.assertIn("application/support/ui_admin_server.py", readme)

    def test_active_process_code_is_grouped_by_step(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        process_root = repo_root / "codes" / "process"
        expected_dirs = {
            "step0_preprocess",
            "step1_prelabel",
            "step2_stage1_prep",
            "step4_stage2_task_pool",
            "step5_stage2_review_prep",
            "shared",
            "devtools",
        }
        existing_dirs = {path.name for path in process_root.iterdir() if path.is_dir()}
        for name in expected_dirs:
            self.assertIn(name, existing_dirs, f"expected codes/process/{name}/")

    def test_active_application_code_is_grouped_by_step(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        app_root = repo_root / "codes" / "application"
        expected_dirs = {
            "step3_human_stage_1",
            "step5_stage2_review",
            "support",
        }
        existing_dirs = {path.name for path in app_root.iterdir() if path.is_dir()}
        for name in expected_dirs:
            self.assertIn(name, existing_dirs, f"expected codes/application/{name}/")

    def test_active_tests_are_grouped_by_step(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        test_root = repo_root / "codes" / "test"
        expected_dirs = {
            "step0_preprocess",
            "step1_prelabel",
            "step2_stage1_prep",
            "step3_human_stage_1",
            "step5_stage2_review",
            "support",
            "devtools",
        }
        existing_dirs = {path.name for path in test_root.iterdir() if path.is_dir()}
        for name in expected_dirs:
            self.assertIn(name, existing_dirs, f"expected codes/test/{name}/")


if __name__ == "__main__":
    unittest.main()
