# Human Stage 1 Progress Bar And Submit-Only Design

## Goal

Make two small active-UI changes to `human_stage_1`:

1. remove the top-level `下一段` button so annotators do not manually advance without submitting
2. add a per-annotator progress bar between the annotator input and the submit button

The progress bar must display each annotator's completed workload as:

```text
completed_frames / 2600
```

where:

- `completed_frames` = the sum of `frame_count` across all annotations already submitted by that annotator
- `2600` = the fixed per-annotator target workload

## Scope

This design covers only the active `human_stage_1` stack:

- `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
- `codes/application/step3_human_stage_1/web/index.html`
- `codes/application/step3_human_stage_1/web/app.js`
- `codes/application/step3_human_stage_1/web/styles.css`
- active `step3_human_stage_1` tests
- active docs only if they describe the top action layout

This design does not change:

- queue semantics
- slot decision semantics
- history editing semantics
- review-stage services

## Hard Constraints

The user-defined requirements are:

1. there should no longer be a visible `下一段` button for stage-1 assignment
2. the progress bar must sit to the right of the annotator field and to the left of the submit button
3. progress is personal to the current annotator, not global
4. progress should count submitted work only
5. the per-annotator total target is fixed at `2600` frames

## Recommendation

Keep the change minimal:

- compute progress on the server from existing annotation history
- return that progress alongside the existing assignment/history payloads
- let the browser render a compact bar and numeric text in the header action row

This avoids client-side estimation and keeps the progress definition consistent with stored annotation data.

## Progress Semantics

Progress is defined as:

```text
annotator_completed_frames = sum(segment.frame_count for each submitted annotation by that annotator)
```

Important consequences:

- each successful new annotation row counts once toward that annotator's personal progress
- `update_annotation` must not increase progress, because it edits an existing annotation instead of creating a new one
- if a submit is accepted for an already completed queue item, it still counts toward the submitting annotator's personal progress because the user explicitly wants personal effort counted even when queue advancement does not occur

The progress bar should cap visually at 100%, but the numeric text may still show values above `2600` if the annotator exceeds the nominal target.

## Backend Changes

Add one server-side helper that calculates progress for a single annotator by joining:

- `coarse_labels`
- `stage1_assignment_queue` and/or `segment_lookup`

The simplest robust version is:

1. read all annotation rows for the annotator
2. map each row's `segment_id` to the current segment metadata
3. sum `frame_count`

Expose a payload shaped like:

```json
{
  "completed_frames": 1234,
  "target_frames": 2600,
  "ratio": 0.4746
}
```

Return this progress block in:

- `next_segment`
- `my_annotations`
- optionally `annotation_detail`

The browser only needs one reliable source during:

- initial page load
- annotator switch
- submit success
- history refresh

## Frontend Changes

### Header Layout

Change the header actions from:

```text
Annotator | 下一段 | 提交
```

to:

```text
Annotator | Progress Bar | 提交
```

### Progress Display

Use a compact horizontal progress component that includes:

- a short label such as `进度`
- a fill bar
- numeric text such as `1234 / 2600 帧`

The bar must update when:

1. the page initializes
2. the annotator field changes
3. a submit succeeds
4. history is refreshed if that response includes progress

### Next Task Loading

Once the `下一段` button is removed, task loading must still remain smooth:

- the page should load a task automatically on first render
- after a successful submit, it should still advance automatically to the next task
- when the annotator changes, the page should refresh both progress and the current assigned task automatically

This preserves the workflow without a manual “advance without submit” control.

## Testing

Regression coverage should verify:

1. the static HTML no longer contains the `nextBtn` control
2. the static UI contains the progress bar container and progress text elements
3. the server returns annotator progress metadata
4. progress sums `frame_count` across submitted annotations for that annotator
5. editing an annotation does not increase progress

## Success Criteria

This work is complete when:

1. `human_stage_1` no longer shows a `下一段` button
2. the header shows a per-annotator progress bar between the annotator field and submit button
3. the numeric progress uses `completed_frames / 2600`
4. progress updates correctly after submit and annotator changes
