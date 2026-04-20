# Human Stage 1 Global Double-Pass Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-annotator stage-1 assignment with one shared global queue that walks the full ordered segment list twice and advances only on successful submit.

**Architecture:** Add a materialized `stage1_assignment_queue` table to the existing stage-1 SQLite database, derive it from the current ordered `segment_pool`, and backfill completion state from existing `coarse_labels`. Keep `coarse_labels` as the source of annotation content, but move task selection to the queue table so `next_segment` returns the earliest global pending queue item. Update the browser to submit `queue_id` with new assignments while leaving annotation editing semantics unchanged.

**Tech Stack:** Python 3, SQLite, `unittest`, vanilla JS/HTML/CSS, existing `human_stage_1` server/web stack

---

## File Structure

### Files to modify

- `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
  Purpose: Define the queue schema, initialize/migrate the queue from segment pool plus historical annotations, assign next items from the global queue, and complete queue items on submit.

- `codes/application/step3_human_stage_1/web/app.js`
  Purpose: Carry `queue_id` through assignment and submission without changing the visible editing model.

- `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`
  Purpose: Lock the new queue semantics, migration behavior, duplicate-submit acceptance, and pass-2 reassignment behavior.

- `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`
  Purpose: Lock the frontend payload wiring for `queue_id`.

- `docs/README.md`
  Purpose: Update the active workflow wording so the current stage-1 queue semantics are not misdescribed.

### Files to reference only

- `docs/superpowers/specs/2026-04-21-human-stage-1-global-double-pass-queue-design.md`
  Purpose: Approved design and exact queue semantics.

---

### Task 1: Add failing backend tests for the global double-pass queue

**Files:**
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`
- Reference: `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`

- [ ] **Step 1: Add a failing test for queue initialization order**

Add this test in `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`:

```python
    def test_human_stage_1_server_initializes_global_queue_with_two_passes(self) -> None:
        state = self._make_state()

        with closing(sqlite3.connect(state.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT segment_id, pass_index, queue_order, status
                FROM stage1_assignment_queue
                ORDER BY queue_order ASC
                """
            ).fetchall()

        self.assertEqual(
            rows,
            [
                ("sample_stage1_seg_000001", 1, 1, "pending"),
                ("sample_stage1_seg_000002", 1, 2, "pending"),
                ("sample_stage1_seg_000001", 2, 3, "pending"),
                ("sample_stage1_seg_000002", 2, 4, "pending"),
            ],
        )
```

- [ ] **Step 2: Add a failing test for shared global assignment**

Add this test:

```python
    def test_human_stage_1_server_assigns_same_global_item_to_multiple_annotators_before_submit(self) -> None:
        state = self._make_state()

        payload_a = state.assign_next_segment("annotator_a")
        payload_b = state.assign_next_segment("annotator_b")

        self.assertEqual(payload_a["queue"]["queue_id"], payload_b["queue"]["queue_id"])
        self.assertEqual(payload_a["queue"]["pass_index"], 1)
        self.assertEqual(payload_a["segment"]["segment_id"], "sample_stage1_seg_000001")
```

- [ ] **Step 3: Add a failing test for submit-driven queue advancement**

Add this test:

```python
    def test_human_stage_1_server_advances_global_queue_only_after_submit(self) -> None:
        state = self._make_state()

        payload = state.assign_next_segment("annotator_a")
        state.submit_segment(
            "annotator_a",
            payload["segment"]["segment_id"],
            {
                "queue_id": payload["queue"]["queue_id"],
                "segment_id": payload["segment"]["segment_id"],
                "video_stem": payload["segment"]["video_stem"],
                "frame_index": payload["frame"]["frame_index"],
                "slot_decisions": [
                    {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"},
                ],
            },
        )

        next_payload = state.assign_next_segment("annotator_b")

        self.assertEqual(next_payload["segment"]["segment_id"], "sample_stage1_seg_000002")
        self.assertEqual(next_payload["queue"]["pass_index"], 1)
```

- [ ] **Step 4: Add a failing test for duplicate submit acceptance without double advancement**

Add this test:

```python
    def test_human_stage_1_server_accepts_duplicate_submit_without_advancing_twice(self) -> None:
        state = self._make_state()

        payload = state.assign_next_segment("annotator_a")
        submit_payload = {
            "queue_id": payload["queue"]["queue_id"],
            "segment_id": payload["segment"]["segment_id"],
            "video_stem": payload["segment"]["video_stem"],
            "frame_index": payload["frame"]["frame_index"],
            "slot_decisions": [
                {"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"},
            ],
        }

        first = state.submit_segment("annotator_a", payload["segment"]["segment_id"], submit_payload)
        second = state.submit_segment("annotator_b", payload["segment"]["segment_id"], submit_payload)

        self.assertEqual(first["queue_completed"], True)
        self.assertEqual(second["queue_completed"], False)

        next_payload = state.assign_next_segment("annotator_c")
        self.assertEqual(next_payload["segment"]["segment_id"], "sample_stage1_seg_000002")
```

- [ ] **Step 5: Add a failing test for startup migration from historical annotations**

Add this test:

```python
    def test_human_stage_1_server_migrates_existing_annotations_into_queue_progress(self) -> None:
        state = self._make_state()
        state.submit_segment(
            "annotator_a",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [{"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"}],
            },
        )
        state.submit_segment(
            "annotator_b",
            "sample_stage1_seg_000001",
            {
                "segment_id": "sample_stage1_seg_000001",
                "video_stem": "sample",
                "frame_index": 2,
                "slot_decisions": [{"slot": "p1", "decision_type": "ai_match", "ai_track_id": "11"}],
            },
        )
        state.close()

        subject = self._subject_module()
        migrated = subject.HumanStage1State(
            batch_dir=self.batch_dir,
            static_dir=Path("codes/application/step3_human_stage_1/web"),
            seed=123,
            reset_storage=False,
        )
        migrated.initialize()

        next_payload = migrated.assign_next_segment("annotator_c")

        self.assertEqual(next_payload["segment"]["segment_id"], "sample_stage1_seg_000002")
        self.assertEqual(next_payload["queue"]["pass_index"], 1)
```

- [ ] **Step 6: Run the targeted server tests to verify they fail**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server -v
```

Expected: FAIL because `stage1_assignment_queue`, `queue_id`, and global queue semantics do not exist yet.

- [ ] **Step 7: Commit the red backend tests**

```bash
git add codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py
git commit -m "test: lock stage 1 global queue semantics"
```

### Task 2: Implement the backend queue table, migration, and submit semantics

**Files:**
- Modify: `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py`

- [ ] **Step 1: Add queue data structures and schema helpers**

At the top-level dataclass section in `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`, add:

```python
@dataclass(frozen=True)
class QueueRecord:
    queue_id: int
    segment_id: str
    pass_index: int
    queue_order: int
    status: str
    annotation_id: str
    completed_by: str
    completed_at: str
```

and add a lookup field in `HumanStage1State.__init__`:

```python
        self.queue_lookup: Dict[int, QueueRecord] = {}
```

- [ ] **Step 2: Create and backfill the queue during initialization**

In `initialize()`, load the segment pool first, then call a new helper and populate `queue_lookup`:

```python
        self.segment_pool = self._load_segment_pool()
        self.segment_lookup = {segment.segment_id: segment for segment in self.segment_pool}
        self._init_database()
        self._init_assignment_log()
        self._init_assignment_queue()
        self.queue_lookup = self._load_queue_lookup()
```

Implement `_init_assignment_queue()` so it:

1. creates the table if absent
2. inserts two rows per segment when the table is empty
3. replays existing `coarse_labels` ordered by `submitted_at, annotation_id` into the earliest pending queue row for each `segment_id`

Use this schema:

```python
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stage1_assignment_queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segment_id TEXT NOT NULL,
                    video_stem TEXT NOT NULL,
                    pass_index INTEGER NOT NULL,
                    queue_order INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    annotation_id TEXT NOT NULL DEFAULT '',
                    completed_by TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
```

- [ ] **Step 3: Replace per-annotator assignment with global pending-queue selection**

Replace `assign_next_segment()` with logic that selects the earliest pending queue row:

```python
    def assign_next_segment(self, annotator_id: str) -> Dict[str, Any]:
        queue_item = self._next_pending_queue_item()
        if queue_item is None:
            raise ValueError("no stage-1 segments remaining")
        segment = self.segment_lookup.get(queue_item.segment_id)
        if segment is None:
            raise ValueError("segment not found")
        payload = self._segment_payload(segment)
        payload["queue"] = {
            "queue_id": queue_item.queue_id,
            "pass_index": queue_item.pass_index,
            "queue_order": queue_item.queue_order,
            "status": queue_item.status,
        }
        self._append_assignment_log(annotator_id, payload["segment"]["segment_id"])
        return payload
```

Implement `_next_pending_queue_item()` to query:

```python
SELECT queue_id, segment_id, pass_index, queue_order, status, annotation_id, completed_by, completed_at
FROM stage1_assignment_queue
WHERE status='pending'
ORDER BY queue_order ASC
LIMIT 1
```

- [ ] **Step 4: Make submit require `queue_id` and complete queue rows once**

In `submit_segment()`:

1. read `queue_id` from payload
2. validate that the queue row exists and matches `segment_id`
3. insert into `coarse_labels` as before
4. attempt an update like:

```python
            cursor = conn.execute(
                """
                UPDATE stage1_assignment_queue
                SET status='completed', annotation_id=?, completed_by=?, completed_at=?
                WHERE queue_id=? AND status='pending'
                """,
                (record["annotation_id"], annotator_id, record["submitted_at"], queue_id),
            )
```

Return:

```python
        return {
            "annotation_id": record["annotation_id"],
            "segment_id": segment.segment_id,
            "frame_index": segment.representative_frame,
            "submitted_slot_count": len(slot_decisions),
            "queue_id": queue_id,
            "queue_completed": cursor.rowcount > 0,
        }
```

- [ ] **Step 5: Refresh payload helpers and keep editing backward-compatible**

Update `_segment_payload()` to accept an optional queue item:

```python
    def _segment_payload(self, segment: SegmentRecord, queue_item: QueueRecord | None = None) -> Dict[str, Any]:
```

and include queue metadata only when provided:

```python
        if queue_item is not None:
            payload["queue"] = {
                "queue_id": queue_item.queue_id,
                "pass_index": queue_item.pass_index,
                "queue_order": queue_item.queue_order,
                "status": queue_item.status,
            }
```

Leave `annotation_detail()` and `update_annotation()` queue-neutral so existing edit flows continue working.

- [ ] **Step 6: Run the backend test module to verify it passes**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server -v
```

Expected: PASS.

- [ ] **Step 7: Commit the backend implementation**

```bash
git add codes/application/step3_human_stage_1/ui_human_stage_1_server.py \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_server.py
git commit -m "feat: add stage 1 global double-pass queue"
```

### Task 3: Add frontend payload support for `queue_id`

**Files:**
- Modify: `codes/application/step3_human_stage_1/web/app.js`
- Modify: `codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py`

- [ ] **Step 1: Add a failing static test for `queue_id` payload wiring**

Append these assertions to `test_human_stage_1_ui_exposes_only_three_coarse_actions`:

```python
        self.assertIn('payload["queue"]["queue_id"]', js)
        self.assertIn("queue_id: state.task.queue.queue_id", js)
        self.assertIn('if (!state.task?.queue?.queue_id)', js)
```

- [ ] **Step 2: Run the static test to verify it fails**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
```

Expected: FAIL because the current browser payload does not include queue metadata.

- [ ] **Step 3: Wire `queue_id` into new submissions**

In `buildSubmitPayload()` inside `codes/application/step3_human_stage_1/web/app.js`, add:

```javascript
  if (!state.editing && !state.task?.queue?.queue_id) {
    throw new Error("当前任务缺少 queue_id");
  }
```

and include queue id only for fresh submits:

```javascript
  const payload = {
    annotator_id: annotatorId(),
    segment_id: state.task.segment.segment_id,
    video_stem: state.task.segment.video_stem,
    frame_index: state.task.frame.frame_index,
    slot_decisions: slot_decisions.filter((item) => ALLOWED_DECISIONS.includes(item.decision_type)),
  };
  if (!state.editing && state.task?.queue?.queue_id) {
    payload.queue_id = state.task.queue.queue_id;
  }
  return payload;
```

- [ ] **Step 4: Run syntax and static tests**

Run:

```bash
node --check codes/application/step3_human_stage_1/web/app.js
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
```

Expected:
- JS syntax check exits cleanly
- static test module reports PASS

- [ ] **Step 5: Commit the frontend wiring**

```bash
git add codes/application/step3_human_stage_1/web/app.js \
  codes/test/step3_human_stage_1/test_ui_human_stage_1_web_static.py
git commit -m "feat: send queue id with stage 1 submits"
```

### Task 4: Refresh active docs and run final verification

**Files:**
- Modify: `docs/README.md`

- [ ] **Step 1: Update the active README wording**

In the `human_stage_1 UI 该怎么理解` section of `docs/README.md`, append one short line after the slot description:

```markdown
- 派单使用全局共享队列：所有 segment 先完整排一遍，再完整排第二遍，只有提交成功才会推进队列
```

- [ ] **Step 2: Run the final verification bundle**

Run:

```bash
PYTHONPATH=codes /home/hrli/data_annotation/.venv/bin/python -m unittest \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_server \
  codes.test.step3_human_stage_1.test_ui_human_stage_1_web_static -v
node --check codes/application/step3_human_stage_1/web/app.js
```

Expected:
- all listed Python tests report PASS
- `node --check` exits cleanly

- [ ] **Step 3: Commit docs and final verification state**

```bash
git add docs/README.md
git commit -m "docs: describe stage 1 global double-pass queue"
```

