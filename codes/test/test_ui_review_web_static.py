#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class ReviewWebStaticTests(unittest.TestCase):
    def test_slot_header_includes_bulk_absent_button_and_binding(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        html = (repo_root / "codes" / "application" / "ui_review_web" / "index.html").read_text(
            encoding="utf-8"
        )
        js = (repo_root / "codes" / "application" / "ui_review_web" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="markRemainingAbsentBtn"', html)
        self.assertIn("bulk_mark_remaining_absent", html)
        self.assertIn("function markRemainingSlotsAbsent()", js)
        self.assertIn('refs.markRemainingAbsentBtn.addEventListener("click", markRemainingSlotsAbsent);', js)

    def test_repair_window_client_hooks_exist(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        js = (repo_root / "codes" / "application" / "ui_review_web" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("repairWindow", js)
        self.assertIn("anchor_annotations", js)
        self.assertIn("function isRepairWindow()", js)
        self.assertIn("function advanceRepairWindowAnchor()", js)


if __name__ == "__main__":
    unittest.main()
