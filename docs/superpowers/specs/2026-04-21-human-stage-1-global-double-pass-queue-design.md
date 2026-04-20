# Human Stage 1 Global Double-Pass Queue Design

## Goal

Replace the current per-annotator `human_stage_1` assignment behavior with one shared global task queue.

The new queue must:

1. use the existing `segment_pool` order as the canonical ordering
2. traverse the full ordered segment list once
3. then traverse the same ordered segment list a second time
4. treat each queue position as complete only after a successful submit

In short:

```text
global queue = [all segments in order] + [all segments in the same order]
```

The design explicitly allows accidental over-labeling caused by concurrent requests. If two or more annotators receive the same queue item before any of them submits, and they all submit, those extra submissions are accepted.

## Problem

The current implementation assigns work independently per annotator. Every annotator effectively walks the entire segment list from start to finish because `next_segment` only skips segments already completed by that same annotator.

This creates the exact failure mode the user wants to avoid:

- multiple annotators pile up on the earliest segments
- global progress does not move smoothly through the batch
- the system behaves like “one private queue per annotator” instead of one shared task stream

## Scope

This design covers only the active `human_stage_1` stack:

- task assignment behavior in `codes/application/step3_human_stage_1/ui_human_stage_1_server.py`
- persistence needed to support a global double-pass queue
- migration from the existing `coarse_labels` history to the new queue state
- regression tests for the new semantics

This design does not change:

- stage-1 coarse decision schema itself
- slot validation rules
- history recommendation logic except for reading the existing `coarse_labels`
- review-stage services
- admin-stage semantics beyond whatever passive visibility the current DB already provides

## Hard Constraints

The user requirements for this design are:

1. one shared global queue, not one queue per annotator
2. no claim / lease / lock complexity
3. only successful submit advances queue completion
4. queue order must be “all segments once, then all segments once again”
5. the same annotator may receive the same segment again on the second pass
6. accidental third or later annotations are acceptable and should not be rejected just because the nominal queue target is two passes

## Recommendation

Use a small materialized queue table in the existing stage-1 SQLite database.

This is preferable to recomputing queue position on every request because:

- it keeps the assignment order explicit and inspectable
- it preserves the “first full pass, then second full pass” requirement exactly
- it makes startup migration from existing annotations straightforward
- it avoids adding locking logic while still keeping one global notion of progress

## Queue Model

Add a new table:

```text
stage1_assignment_queue
```

Each segment produces exactly two nominal queue items:

- pass 1
- pass 2

The table should include at least:

- `queue_id`
- `segment_id`
- `video_stem`
- `pass_index`
- `queue_order`
- `status`
- `annotation_id`
- `completed_by`
- `completed_at`

### Status Semantics

The queue needs only two stable statuses:

- `pending`
- `completed`

No `claimed`, `leased`, `reserved`, or timeout states are needed.

### Ordering

Use the existing `segment_pool` order, which is already sorted by:

- `video_stem`
- `start_frame`
- `end_frame`
- `segment_id`

If the ordered segment list is:

```text
S1, S2, S3, ..., SN
```

then the queue order must be:

```text
S1(pass1), S2(pass1), ..., SN(pass1), S1(pass2), S2(pass2), ..., SN(pass2)
```

## Assignment Semantics

`next_segment` should no longer ask “what has this annotator completed?”

Instead it should:

1. read the earliest queue row whose `status = pending`
2. return that queue row’s segment payload
3. include queue metadata in the response

That means:

- every annotator sees the same current global frontier
- if two annotators ask at the same time, they may receive the same queue item
- this is acceptable by design

The response should include:

- `queue_id`
- `pass_index`

alongside the existing segment and frame payload.

## Submit Semantics

`submit_segment` must require `queue_id`.

On submit:

1. validate that the submitted `segment_id` still matches the queue item’s `segment_id`
2. write the coarse-label record to `coarse_labels` exactly as before
3. attempt to mark the queue item completed

If the queue item is still `pending`, the submit:

- marks it `completed`
- writes `annotation_id`
- writes `completed_by`
- writes `completed_at`

If the queue item is already `completed`, the submit is still accepted:

- the annotation is still inserted into `coarse_labels`
- the queue row remains unchanged
- the queue does not advance again

This preserves the desired behavior:

- two nominal passes in the queue
- but accidental third or later labels are allowed

## Annotation Editing Semantics

`update_annotation` should continue to update the stored annotation record only.

It should not reopen or rewrite queue state because:

- queue progress is defined by first successful completion of a queue item
- editing an existing completed annotation is an audit/content operation, not a reassignment event

## Migration From Existing Data

The current batch may already contain stage-1 annotations in `coarse_labels`.

When the server starts:

1. if `stage1_assignment_queue` does not exist, create it
2. populate the full double-pass queue from the current ordered `segment_pool`
3. replay existing annotations into queue completion state

Replay rule:

- load existing `coarse_labels`
- order them by `submitted_at ASC, annotation_id ASC`
- for each annotation, find the earliest queue row for the same `segment_id` whose status is still `pending`
- mark that queue row `completed`

Consequences:

- the first historical annotation for a segment fills pass 1
- the second historical annotation fills pass 2
- third and later historical annotations remain valid rows in `coarse_labels` but do not create extra queue progress

This lets the new queue inherit real existing batch progress without resetting the batch.

## Recommendation Logic

Recommendation logic may continue to read all rows from `coarse_labels` in chronological order.

No queue-specific restriction is needed there because the user did not request any change to recommendation semantics.

This means duplicate or extra annotations can still contribute to the historical majority logic, which matches current behavior.

## Error Handling

The server should reject:

- missing `queue_id`
- unknown `queue_id`
- `segment_id` mismatch between request and queue row

The server should not reject:

- submit to a queue item that was already completed by someone else

That later case is allowed and should simply become an additional annotation row without changing queue state.

## Testing

Regression coverage should verify:

1. queue initialization creates exactly two queue rows per segment in the correct order
2. `next_segment` returns the earliest global pending queue item, not an annotator-specific next item
3. two different annotators can receive the same pending queue item before any submit
4. first successful submit completes the queue item and advances the next global assignment
5. second submit to the same queue item is still accepted but does not advance queue state again
6. startup migration from pre-existing `coarse_labels` correctly marks earlier queue rows completed
7. the same annotator may receive the same `segment_id` again on pass 2

## Success Criteria

This work is complete when:

1. `human_stage_1` uses one shared global queue
2. queue order is exactly “all segments once, then all segments once again”
3. successful submit, not request time, is what advances queue completion
4. concurrent requests may still produce duplicate assignment of the same queue item
5. accidental third or later annotations are accepted without breaking queue progress
6. existing stage-1 history is migrated into the new queue so the batch does not restart from zero
