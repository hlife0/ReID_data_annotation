#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class RepoLayoutTests(unittest.TestCase):
    def test_repository_uses_codes_directory_instead_of_codex(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        codes_root = repo_root / "codes"
        self.assertTrue(codes_root.is_dir(), "expected top-level codes/ directory")
        self.assertFalse((repo_root / "codex").exists(), "codex/ should have been renamed to codes/")
        self.assertTrue((codes_root / "application").is_dir(), "expected codes/application/ directory")
        self.assertTrue((codes_root / "process").is_dir(), "expected codes/process/ directory")
        self.assertTrue((codes_root / "test").is_dir(), "expected codes/test/ directory")
        self.assertTrue((codes_root / "README.md").is_file(), "expected codes/README.md")
        self.assertTrue((codes_root / "process" / "README.md").is_file(), "expected codes/process/README.md")

    def test_active_python_files_are_grouped_under_application_process_or_test(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
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
        repo_root = Path(__file__).resolve().parent.parent.parent
        readme = (repo_root / "codes" / "process" / "README.md").read_text(encoding="utf-8")
        self.assertIn("process_prelabel_batch.py", readme)
        self.assertIn("process_segment_review_prep.py", readme)
        self.assertIn("application/ui_review_server.py", readme)
        self.assertIn("application/ui_admin_server.py", readme)


if __name__ == "__main__":
    unittest.main()
