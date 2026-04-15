#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class RepoLayoutTests(unittest.TestCase):
    def test_repository_uses_codes_directory_instead_of_codex(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self.assertTrue((repo_root / "codes").is_dir(), "expected top-level codes/ directory")
        self.assertFalse((repo_root / "codex").exists(), "codex/ should have been renamed to codes/")


if __name__ == "__main__":
    unittest.main()
