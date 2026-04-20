# Human Stage 1 Progress Bar And Submit-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the top-level `下一段` button from `human_stage_1` and add a per-annotator progress bar that displays submitted workload as `completed_frames / 2600`.

**Architecture:** Keep the UI change minimal by computing annotator progress on the server from existing annotation history and returning it with the existing assignment/history responses. Update the browser header to replace the manual advance button with a compact progress component, and let annotator changes plus successful submits drive both task refresh and progress refresh automatically.

**Tech Stack:** Python 3, SQLite, `unittest`, vanilla JS/HTML/CSS, existing `human_stage_1` stack

---

## File Structure

### Files to modify

- `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
  Purpose: Compute per-annotator completed-frame progress and attach it to assignment/history/detail payloads.

- `codes/application/step3_human_stage_1/web/index.html`
  Purpose: Remove the `下一段` button and add the progress bar container between the annotator field and submit button.

- `codes/application/step3_human_stage_1/web/app.js`
  Purpose: Render progress, refresh it when annotator/task state changes, and automatically reload the next task on annotator changes now that the explicit next button is gone.

- `codes/application/step3_human_stage_1/web/styles.css`
  Purpose: Style the compact progress bar in the header action row.

- `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`
  Purpose: Lock the server-side progress semantics.

- `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`
  Purpose: Lock the static UI contract for the submit-only header and progress component.

- `docs/README.md`
  Purpose: Keep the active UI description aligned with the new header behavior if needed.

### Files to reference only

- `docs/superpowers/specs/2026-04-21-human-stage-1-progress-bar-and-submit-only-design.md`
  Purpose: Approved design for progress semantics and header layout.

---

### Task 1: Add failing tests for per-annotator progress and submit-only header

**Files:**
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`

- [ ] **Step 1: Add a failing backend test for annotator progress totals**

Add this test to `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`:

```python
    def test_human_stage_1_server_reports_annotator_progress_in_frames(self) -> None:
        state = self._make_state()

        self._submit_next_segment(
            state,
            "annotator_stage1",
            [{"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"}],
        )
        self._submit_next_segment(
            state,
            "annotator_stage1",
            [{"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"}],
        )

        payload = state.assign_next_segment("annotator_stage1")

        self.assertEqual(payload["annotator_progress"]["completed_frames"], 6)
        self.assertEqual(payload["annotator_progress"]["target_frames"], 2600)
        self.assertAlmostEqual(payload["annotator_progress"]["ratio"], 6 / 2600, places=6)
```

- [ ] **Step 2: Add a failing backend test showing edits do not increase progress**

Add this test:

```python
    def test_human_stage_1_server_edit_does_not_increase_progress(self) -> None:
        state = self._make_state()
        payload, result = self._submit_next_segment(
            state,
            "annotator_stage1",
            [{"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"}],
        )

        before = state.assign_next_segment("annotator_stage1")["annotator_progress"]["completed_frames"]

        state.update_annotation(
            "annotator_stage1",
            {
                "annotation_id": result["annotation_id"],
                "video_stem": payload["segment"]["video_stem"],
                "frame_index": payload["frame"]["frame_index"],
                "slot_decisions": [{"slot": "p1", "decision_type": "absent", "ai_track_id": ""}],
            },
        )

        after = state.assign_next_segment("annotator_stage1")["annotator_progress"]["completed_frames"]

        self.assertEqual(before, 3)
        self.assertEqual(after, 3)
```

- [ ] **Step 3: Add a failing static test for the header layout change**

Append these assertions to `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`:

```python
        self.assertIn('id="annotatorProgress"', html)
        self.assertIn('id="annotatorProgressBar"', html)
        self.assertIn('id="annotatorProgressText"', html)
        self.assertIn("function renderAnnotatorProgress(", js)
        self.assertIn("2600", js)
        self.assertNotIn('id="nextBtn"', html)
        self.assertNotIn('getElementById("nextBtn")', js)
```

- [ ] **Step 4: Run the targeted test modules to verify they fail**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
```

Expected: FAIL because the server does not return annotator progress and the static UI still contains the `nextBtn` control.

- [ ] **Step 5: Commit the red tests**

```bash
git add codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py
git commit -m "test: lock stage 1 progress bar and submit-only header"
```

### Task 2: Implement annotator progress in the server

**Files:**
- Modify: `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`

- [ ] **Step 1: Add a helper that sums submitted frame counts for one annotator**

In `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`, add:

```python
TARGET_ANNOTATOR_FRAMES = 2600
```

and add a helper method:

```python
    def _annotator_progress(self, annotator_id: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT segment_id
                FROM coarse_labels
                WHERE annotator_id=?
                """,
                (annotator_id,),
            ).fetchall()
        finally:
            conn.close()

        completed_frames = 0
        for row in rows:
            segment = self.segment_lookup.get(str(row["segment_id"]))
            if segment is None:
                continue
            completed_frames += int(segment.frame_count)

        return {
            "completed_frames": completed_frames,
            "target_frames": TARGET_ANNOTATOR_FRAMES,
            "ratio": completed_frames / TARGET_ANNOTATOR_FRAMES if TARGET_ANNOTATOR_FRAMES > 0 else 0.0,
        }
```

- [ ] **Step 2: Attach progress to existing payloads**

Update `assign_next_segment()`:

```python
        payload["annotator_progress"] = self._annotator_progress(annotator_id)
```

Update `list_annotations_for_annotator()` to return both annotations and progress:

```python
    def list_annotations_for_annotator(self, annotator_id: str) -> Dict[str, Any]:
        ...
        return {
            "annotations": [...],
            "annotator_progress": self._annotator_progress(annotator_id),
        }
```

Then adjust `_handle_my_annotations()` accordingly:

```python
            payload = self.server.state.list_annotations_for_annotator(annotator_id)
            self._send_json(payload)
```

Optionally add progress to `annotation_detail()` as well:

```python
        payload["annotator_progress"] = self._annotator_progress(annotator_id)
```

- [ ] **Step 3: Run the server tests to verify they pass**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server -v
```

Expected: PASS.

- [ ] **Step 4: Commit the backend progress implementation**

```bash
git add codes/application/step3_human_stage_1/ui_human_stage_1_server.py \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py
git commit -m "feat: add stage 1 annotator progress metadata"
```

### Task 3: Remove the next button and render the progress bar

**Files:**
- Modify: `codes/application/step3_human_stage_1/web/index.html`
- Modify: `codes/application/step3_human_stage_1/web/app.js`
- Modify: `codes/application/step3_human_stage_1/web/styles.css`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`

- [ ] **Step 1: Replace the header action layout in HTML**

In `codes/application/step3_human_stage_1/web/index.html`, replace:

```html
            <button id="nextBtn" class="btn subtle" type="button">下一段</button>
            <button id="submitBtn" class="btn" type="button">提交</button>
```

with:

```html
            <div id="annotatorProgress" class="annotator-progress">
              <span class="annotator-progress-label">进度</span>
              <div class="annotator-progress-track">
                <div id="annotatorProgressBar" class="annotator-progress-bar"></div>
              </div>
              <span id="annotatorProgressText" class="annotator-progress-text">0 / 2600 帧</span>
            </div>
            <button id="submitBtn" class="btn" type="button">提交</button>
```

- [ ] **Step 2: Add progress refs, state, and rendering logic in JS**

In `codes/application/step3_human_stage_1/web/app.js`, add refs:

```javascript
  annotatorProgress: document.getElementById("annotatorProgress"),
  annotatorProgressBar: document.getElementById("annotatorProgressBar"),
  annotatorProgressText: document.getElementById("annotatorProgressText"),
```

Add state:

```javascript
  annotatorProgress: { completed_frames: 0, target_frames: 2600, ratio: 0 },
```

In `setTaskFromPayload()`, capture the payload:

```javascript
  state.annotatorProgress = payload.annotator_progress || { completed_frames: 0, target_frames: 2600, ratio: 0 };
```

Add a render helper:

```javascript
function renderAnnotatorProgress(progress = state.annotatorProgress) {
  const completed = Number(progress?.completed_frames || 0);
  const target = Number(progress?.target_frames || 2600);
  const ratio = Math.max(0, Math.min(1, Number(progress?.ratio || 0)));
  refs.annotatorProgressBar.style.width = `${ratio * 100}%`;
  refs.annotatorProgressText.textContent = `${completed} / ${target} 帧`;
}
```

Call `renderAnnotatorProgress()` from:

```javascript
  renderTask();
```

and inside `renderTask()` before returning control.

- [ ] **Step 3: Remove manual next-button handling and auto-refresh on annotator changes**

Delete:

```javascript
  nextBtn: document.getElementById("nextBtn"),
```

and delete the `refs.nextBtn.addEventListener(...)` block.

Update the annotator change handler to:

```javascript
  refs.annotatorId.addEventListener("change", () => {
    localStorage.setItem(ANNOTATOR_STORAGE_KEY, annotatorId());
    loadHistory({ silent: true });
    loadNextSegment().catch((error) => showToast(error.message, true));
  });
```

Update `loadHistory()` so it captures progress:

```javascript
    state.history = payload.annotations || [];
    state.annotatorProgress = payload.annotator_progress || state.annotatorProgress;
    renderAnnotatorProgress();
```

- [ ] **Step 4: Style the compact progress component**

Add this block to `codes/application/step3_human_stage_1/web/styles.css`:

```css
.annotator-progress {
  min-width: 220px;
  display: grid;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
}

.annotator-progress-label,
.annotator-progress-text {
  font-size: 0.76rem;
  color: var(--muted);
}

.annotator-progress-track {
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(33, 57, 79, 0.12);
}

.annotator-progress-bar {
  width: 0%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent) 0%, #28a38f 100%);
  transition: width 160ms ease;
}
```

- [ ] **Step 5: Run syntax and static tests**

Run:

```bash
node --check codes/application/step3_human_stage_1/web/app.js
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
```

Expected: PASS.

- [ ] **Step 6: Commit the frontend changes**

```bash
git add codes/application/step3_human_stage_1/web/index.html \
  codes/application/step3_human_stage_1/web/app.js \
  codes/application/step3_human_stage_1/web/styles.css \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py
git commit -m "feat: add stage 1 progress bar and submit-only header"
```

### Task 4: Refresh docs and run the final verification bundle

**Files:**
- Modify: `docs/README.md`

- [ ] **Step 1: Update the active UI description if needed**

In `docs/README.md`, add one short note under the `human_stage_1` UI section:

```markdown
- 顶部不再提供“下一段”按钮；annotator 右侧会显示个人进度条，按已提交帧数累计到 `2600`
```

- [ ] **Step 2: Run the final verification bundle**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
node --check codes/application/step3_human_stage_1/web/app.js
```

Expected: all checks pass.

- [ ] **Step 3: Commit docs and final verification state**

```bash
git add docs/README.md
git commit -m "docs: describe stage 1 progress bar header"
```

