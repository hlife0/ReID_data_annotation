# Human Stage 1 Eight-Slot Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the active `human_stage_1` UI stack from 7 slots to 8 slots and render annotator-facing slot labels as `P<n>(Name)` while keeping persisted slot IDs as `p1` through `p8`.

**Architecture:** Add one authoritative slot-configuration mapping in the `human_stage_1` backend, expose both ordered slot IDs and display labels in API payloads, and let the browser render all user-facing slot text from that mapping. Keep submission payloads and stored JSON keyed by raw slot IDs so no storage migration is required.

**Tech Stack:** Python 3, `unittest`, vanilla JS/HTML/CSS, existing `human_stage_1` HTTP server

---

## File Structure

### Files to modify

- `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
  Purpose: Define the 8-slot configuration, format user-facing slot summaries, and return slot display-label metadata with assignment/detail payloads.

- `codes/application/step3_human_stage_1/web/app.js`
  Purpose: Render slot tabs, active-slot title, legend labels, and validation toasts with `P<n>(Name)` labels while still submitting raw slot IDs.

- `codes/application/step3_human_stage_1/web/index.html`
  Purpose: Keep the default active-slot placeholder aligned with the new named-slot UI.

- `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`
  Purpose: Lock the 8-slot API contract and named history-summary formatting.

- `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`
  Purpose: Lock the static frontend contract for named slot labels.

- `docs/README.md`
  Purpose: Update the active `human_stage_1` description from `P1-P7` to the new 8-person named slot layout.

### Files to reference only

- `docs/superpowers/specs/2026-04-20-human-stage-1-eight-slot-display-design.md`
  Purpose: Approved design and exact name mapping.

---

### Task 1: Lock the backend contract with failing tests

**Files:**
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`
- Reference: `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`

- [ ] **Step 1: Update the payload contract test to expect 8 slots and named labels**

In `test_human_stage_1_server_returns_single_frame_coarse_task_payload`, change the slot assertions to:

```python
        self.assertEqual(stable_payload["slot_names"], [f"p{i}" for i in range(1, 9)])
        self.assertEqual(
            stable_payload["slot_display_names"],
            {
                "p1": "P1(赵宇轩)",
                "p2": "P2(张络屹)",
                "p3": "P3(Alison)",
                "p4": "P4(刘浩贤)",
                "p5": "P5(何炳毅)",
                "p6": "P6(李泓睿)",
                "p7": "P7(梁芳舟)",
                "p8": "P8(谢灵韵)",
            },
        )
```

- [ ] **Step 2: Add a failing history-summary test for named slot labels**

Add this new test method in `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`:

```python
    def test_human_stage_1_server_uses_named_slot_labels_in_history_summary(self) -> None:
        state = self._make_state()
        result = state.submit_segment(
            "annotator_stage1",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [
                    {
                        "slot": "p1",
                        "decision_type": "ai_match",
                        "ai_track_id": "11",
                        "selection_source": "recommended_confirmed",
                    },
                    {"slot": "p8", "decision_type": "absent", "ai_track_id": ""},
                ],
            },
        )

        history = state.list_annotations_for_annotator("annotator_stage1")

        self.assertEqual(history[0]["annotation_id"], result["annotation_id"])
        self.assertIn("P1(赵宇轩):ai_match(11|recommended_confirmed)", history[0]["slots_summary"])
        self.assertIn("P8(谢灵韵):absent", history[0]["slots_summary"])
```

- [ ] **Step 3: Run the payload test to verify it fails for the expected reason**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server.HumanStage1ServerTests.test_human_stage_1_server_returns_single_frame_coarse_task_payload -v
```

Expected: FAIL because the server still returns only `p1` through `p7` and does not include `slot_display_names`.

- [ ] **Step 4: Run the named-summary test to verify it fails for the expected reason**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server.HumanStage1ServerTests.test_human_stage_1_server_uses_named_slot_labels_in_history_summary -v
```

Expected: FAIL because the history summary still formats slots as bare `P1` / `P8` without names.

- [ ] **Step 5: Commit the red backend tests**

```bash
git add codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py
git commit -m "test: lock human stage 1 eight-slot backend contract"
```

### Task 2: Implement the backend slot configuration and payload metadata

**Files:**
- Modify: `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`

- [ ] **Step 1: Replace the fixed 7-slot list with an 8-slot config plus helpers**

Near the top of `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`, replace the slot constants with:

```python
SLOT_CONFIG = [
    ("p1", "P1(赵宇轩)"),
    ("p2", "P2(张络屹)"),
    ("p3", "P3(Alison)"),
    ("p4", "P4(刘浩贤)"),
    ("p5", "P5(何炳毅)"),
    ("p6", "P6(李泓睿)"),
    ("p7", "P7(梁芳舟)"),
    ("p8", "P8(谢灵韵)"),
]
SLOT_NAMES = [slot for slot, _display_name in SLOT_CONFIG]
SLOT_DISPLAY_NAMES = {slot: display_name for slot, display_name in SLOT_CONFIG}
ALLOWED_DECISIONS = ["ai_match", "absent", "needs_manual"]
AI_SELECTION_SOURCES = {"recommended_confirmed", "manual_selected"}


def slot_display_name(slot: str) -> str:
    normalized = str(slot).strip().lower()
    return SLOT_DISPLAY_NAMES.get(normalized, normalized.upper())
```

- [ ] **Step 2: Format history summaries with named labels**

Update `slot_summary_from_json()` so it uses the helper instead of `slot.upper()`:

```python
        slot = str(item.get("slot", "")).strip().lower()
        decision_type = str(item.get("decision_type", "")).strip()
        ai_track_id = str(item.get("ai_track_id", "") or "").strip()
        selection_source = str(item.get("selection_source", "") or "").strip()
        if not slot or not decision_type:
            continue
        piece = f"{slot_display_name(slot)}:{decision_type}"
```

- [ ] **Step 3: Expose display-label metadata in assignment/detail payloads**

In `_segment_payload()`, add the extra field right next to `slot_names`:

```python
            "slot_names": SLOT_NAMES,
            "slot_display_names": SLOT_DISPLAY_NAMES,
            "allowed_decisions": ALLOWED_DECISIONS,
            "manual_draw_enabled": False,
```

- [ ] **Step 4: Run the full backend test module to verify it passes**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server -v
```

Expected: PASS, including the new 8-slot payload contract and named summary formatting.

- [ ] **Step 5: Commit the backend implementation**

```bash
git add codes/application/step3_human_stage_1/ui_human_stage_1_server.py \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py
git commit -m "feat: add named eight-slot human stage 1 backend"
```

### Task 3: Lock and implement the frontend named-slot rendering

**Files:**
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`
- Modify: `codes/application/step3_human_stage_1/web/app.js`
- Modify: `codes/application/step3_human_stage_1/web/index.html`

- [ ] **Step 1: Add a failing static test for named slot labels**

Append these assertions in `test_human_stage_1_ui_exposes_only_three_coarse_actions`:

```python
        self.assertIn('const SLOT_NAMES = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]', js)
        self.assertIn('"p1": "P1(赵宇轩)"', js)
        self.assertIn('"p8": "P8(谢灵韵)"', js)
        self.assertIn("function slotDisplayName(", js)
        self.assertIn("slotDisplayName(state.activeSlot)", js)
        self.assertIn("P1(赵宇轩)", html)
```

- [ ] **Step 2: Run the static test to verify it fails**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static.HumanStage1WebStaticTests.test_human_stage_1_ui_exposes_only_three_coarse_actions -v
```

Expected: FAIL because the browser code still hardcodes 7 slots and does not contain the named-slot helper or placeholder label.

- [ ] **Step 3: Add the frontend display-name mapping and helper**

At the top of `codes/application/step3_human_stage_1/web/app.js`, replace the slot constants and initial state with:

```javascript
const SLOT_NAMES = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"];
const DEFAULT_SLOT_DISPLAY_NAMES = {
  p1: "P1(赵宇轩)",
  p2: "P2(张络屹)",
  p3: "P3(Alison)",
  p4: "P4(刘浩贤)",
  p5: "P5(何炳毅)",
  p6: "P6(李泓睿)",
  p7: "P7(梁芳舟)",
  p8: "P8(谢灵韵)",
};
const ALLOWED_DECISIONS = ["ai_match", "absent", "needs_manual"];
```

and add this helper below `activeDecision()`:

```javascript
function slotDisplayName(slot) {
  const normalized = String(slot || "").trim().toLowerCase();
  return state.slotDisplayNames[normalized] || DEFAULT_SLOT_DISPLAY_NAMES[normalized] || normalized.toUpperCase();
}
```

- [ ] **Step 4: Wire all user-facing slot text through the helper**

Make these exact replacements in `codes/application/step3_human_stage_1/web/app.js`:

```javascript
const state = {
  task: null,
  slotNames: SLOT_NAMES.slice(),
  slotDisplayNames: { ...DEFAULT_SLOT_DISPLAY_NAMES },
  slotDecisions: new Map(),
  activeSlot: "p1",
  history: [],
  editing: false,
  editingAnnotationId: "",
  lastAssignedTask: null,
};
```

```javascript
  state.slotNames = payload.slot_names || SLOT_NAMES.slice();
  state.slotDisplayNames = { ...DEFAULT_SLOT_DISPLAY_NAMES, ...(payload.slot_display_names || {}) };
```

```javascript
  if (assignedSlot) {
    return `track ${trackId} (${slotDisplayName(assignedSlot)})`;
  }
```

```javascript
      <span class="slot-tab-label">${slotDisplayName(slot)}</span>
```

```javascript
  refs.activeSlotTitle.textContent = slotDisplayName(state.activeSlot);
```

```javascript
    throw new Error(`${slotDisplayName(pending.slot)} 还没设置`);
```

- [ ] **Step 5: Update the static HTML placeholder label**

In `codes/application/step3_human_stage_1/web/index.html`, change the default title node to:

```html
                  <h2 id="activeSlotTitle">P1(赵宇轩)</h2>
```

- [ ] **Step 6: Run syntax and static tests to verify they pass**

Run:

```bash
node --check codes/application/step3_human_stage_1/web/app.js
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
```

Expected:
- `node --check` exits cleanly with no output
- the static test module reports PASS

- [ ] **Step 7: Commit the frontend implementation**

```bash
git add codes/application/step3_human_stage_1/web/app.js \
  codes/application/step3_human_stage_1/web/index.html \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py
git commit -m "feat: render named eight-slot human stage 1 UI"
```

### Task 4: Refresh active docs and run the final verification bundle

**Files:**
- Modify: `docs/README.md`

- [ ] **Step 1: Update the active README description**

In the `human_stage_1 UI 该怎么理解` section of `docs/README.md`, replace:

```markdown
- 上面一排 `P1-P7` 槽位按钮
```

with:

```markdown
- 上面一排 `P1(赵宇轩)` 到 `P8(谢灵韵)` 槽位按钮
```

- [ ] **Step 2: Run the final targeted verification bundle**

Run:

```bash
PYTHONPATH=codes .venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
node --check codes/application/step3_human_stage_1/web/app.js
```

Expected:
- both Python test modules report PASS
- `node --check` exits cleanly with no output

- [ ] **Step 3: Commit the docs and verification pass**

```bash
git add docs/README.md
git commit -m "docs: describe named eight-slot human stage 1 UI"
```

