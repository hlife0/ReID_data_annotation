#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class HumanStage1WebStaticTests(unittest.TestCase):
    def test_human_stage_1_ui_exposes_only_three_coarse_actions(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        html = (
            repo_root / "codes" / "application" / "step3_human_stage_1" / "web" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            repo_root / "codes" / "application" / "step3_human_stage_1" / "web" / "app.js"
        ).read_text(encoding="utf-8")
        css = (
            repo_root / "codes" / "application" / "step3_human_stage_1" / "web" / "styles.css"
        ).read_text(encoding="utf-8")

        self.assertIn("ai_match", html)
        self.assertIn("absent", html)
        self.assertIn("needs_manual", html)
        self.assertIn("ALLOWED_DECISIONS", js)
        self.assertIn("needs_manual", js)
        self.assertIn('const SLOT_NAMES = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]', js)
        self.assertIn('"p1": "P1(赵宇轩)"', js)
        self.assertIn('"p8": "P8(谢灵韵)"', js)
        self.assertIn("function slotDisplayName(", js)
        self.assertIn("slotDisplayName(state.activeSlot)", js)
        self.assertIn("queue_id", js)
        self.assertIn("payload.queue_id = state.task.queue.queue_id", js)
        self.assertIn("if (!state.editing && !state.task?.queue?.queue_id)", js)
        self.assertIn('id="annotatorProgress"', html)
        self.assertIn('id="annotatorProgressBar"', html)
        self.assertIn('id="annotatorProgressText"', html)
        self.assertIn('id="annotatorModal"', html)
        self.assertIn('id="annotatorModalInput"', html)
        self.assertIn('id="annotatorModalSubmitBtn"', html)
        self.assertIn('id="fastSubmitBtn"', html)
        self.assertIn("function submitMissingAndSubmit(", js)
        self.assertIn('location.pathname === "/fast"', js)
        self.assertIn("markRemainingSlotsAbsent();", js)
        self.assertIn("submitCurrent().catch((error) => showToast(error.message, true));", js)
        self.assertIn("function maybePromptAnnotatorModal(", js)
        self.assertIn("function submitAnnotatorModal(", js)
        self.assertIn("function closeAnnotatorModalAndContinue(", js)
        self.assertIn("function renderAnnotatorProgress(", js)
        self.assertIn("2600", js)
        self.assertNotIn('id="nextBtn"', html)
        self.assertNotIn('getElementById("nextBtn")', js)
        self.assertIn("P1(赵宇轩)", html)
        self.assertIn('id="slotTabs"', html)
        self.assertIn('id="activeSlotTitle"', html)
        self.assertIn('id="activeSlotSummary"', html)
        self.assertIn('id="activeAiButtons"', html)
        self.assertIn('id="markRemainingAbsentBtn"', html)
        self.assertIn('id="historyDock"', html)
        self.assertIn('id="historyToggleBtn"', html)
        self.assertIn('id="historyList"', html)
        self.assertIn('id="saveEditBtn"', html)
        self.assertIn("function renderSlotTabs()", js)
        self.assertIn("function syncActiveSlotUI()", js)
        self.assertIn("function markRemainingSlotsAbsent()", js)
        self.assertIn("function renderHistory()", js)
        self.assertIn("function loadHistory(", js)
        self.assertIn("function loadAnnotationDetail(", js)
        self.assertIn("function saveEdit()", js)
        self.assertIn("function overlayLabelForTrackId(", js)
        self.assertIn("function legendLabelForTrackId(", js)
        self.assertIn("t${trackId}:p", js)
        self.assertIn("track ${trackId} (${slotDisplayName(assignedSlot)})", js)
        self.assertIn(".ai-box {", css)
        self.assertIn("border: 3px dashed", css)
        self.assertIn(".ai-box.mapped {", css)
        self.assertIn("border-style: solid", css)
        self.assertIn(".ai-box.active {", css)
        self.assertIn("box-shadow:", css)

        self.assertNotIn("draw_new_box", html)
        self.assertNotIn("manual_draw", html)
        self.assertNotIn('type="number"', html)
        self.assertNotIn("上面看当前选择，下面只编辑当前槽位。", html)
        self.assertNotIn("drawNewBox", js)
        self.assertNotIn("manual_draw", js)
        self.assertNotIn('getElementById("activeX")', js)
        self.assertNotIn('getElementById("activeY")', js)


if __name__ == "__main__":
    unittest.main()
