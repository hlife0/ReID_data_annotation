# Human Stage 1 Eight-Slot Display Design

## Goal

Update the active `human_stage_1` UI stack from 7 identity slots to 8 identity slots, and show each slot label in the browser as `P<n>(Name)` using ASCII parentheses.

The requested mapping is:

- `p1` -> `P1(赵宇轩)`
- `p2` -> `P2(张络屹)`
- `p3` -> `P3(Alison)`
- `p4` -> `P4(刘浩贤)`
- `p5` -> `P5(何炳毅)`
- `p6` -> `P6(李泓睿)`
- `p7` -> `P7(梁芳舟)`
- `p8` -> `P8(谢灵韵)`

## Scope

This design covers only the active `human_stage_1` stack:

- backend slot list and slot metadata in `codes/application/step3_human_stage_1/`
- frontend slot-tab and slot-summary labels in `codes/application/step3_human_stage_1/web/`
- active regression tests for the same stack
- active docs that still describe the current slot count or slot labels

This design does not change:

- stored slot IDs in annotation payloads or databases
- review-stage behavior in `step5_stage2_review`
- historical archive docs

## Design

Keep the canonical slot identifiers as lowercase machine IDs:

- `p1`
- `p2`
- `p3`
- `p4`
- `p5`
- `p6`
- `p7`
- `p8`

Add a display-label mapping layer for the UI-facing text so the browser renders the human-readable labels while the API and persisted data continue to use stable slot IDs.

This avoids a storage migration and keeps existing JSON payloads, recommendation logic, validation, and history summaries keyed by the same slot names.

## Backend Changes

Update the active `human_stage_1` server so that:

1. `SLOT_NAMES` expands from 7 entries to 8 entries.
2. API payloads expose both:
   - slot IDs for machine logic
   - slot display labels for the browser
3. any server-rendered summaries that currently show `P1`, `P2`, etc. use the new `P<n>(Name)` format where appropriate.

The backend remains authoritative for slot configuration so the browser does not need to hardcode the human names separately.

## Frontend Changes

Update the active `human_stage_1` frontend so that:

1. the slot tab row shows 8 slots instead of 7
2. the visible label for each slot uses `P<n>(Name)` with ASCII parentheses
3. any active-slot title, recommendation text, decision summary, or history panel text that currently uses bare `P<n>` or lowercase `p<n>` is switched to the mapped display label where that text is user-facing
4. request payloads sent back to the server still use `p1` to `p8`

If a UI surface is internal-only state and not visible to annotators, it may remain keyed by raw slot ID.

## Data Flow

The slot flow after this change is:

1. backend defines ordered slot IDs and display labels
2. frontend renders slot tabs and labels from that server-provided configuration
3. annotator actions still read and submit raw slot IDs
4. backend persists raw slot IDs exactly as before
5. user-facing summaries format slot IDs back into `P<n>(Name)` text

## Testing

Add or update regression coverage so the active stack verifies:

1. assignment/detail payloads now include 8 slot names
2. user-facing slot label metadata matches the requested mapping
3. persisted submissions still accept and store `p1` through `p8`
4. static web assets contain the 8-slot label behavior

Verification should focus on active `step3_human_stage_1` tests and lightweight static checks, without modifying unrelated review-stage tests.

## Success Criteria

This work is complete when:

1. the `human_stage_1` UI exposes 8 slot tabs
2. annotators see labels in the exact format `P1(赵宇轩)` through `P8(谢灵韵)`
3. submitted data still uses raw slot IDs `p1` through `p8`
4. active tests for `human_stage_1` pass with the new slot count and label mapping
