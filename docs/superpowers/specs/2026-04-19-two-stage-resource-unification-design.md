# Two-Stage Resource Unification Design

## Goal

Unify the entire repository around a two-stage annotation workflow only.

After this change:

- active repository resources must describe and expose only the two-stage workflow
- all historical one-shot annotation code paths must be archived and taken offline
- the archive must preserve enough structure and schema context to restore old paths later if needed

## Scope

This change covers all repository resources, including:

- `docs/`
- `codes/` README files and code-adjacent explanations
- active application/process/test code paths that still expose one-shot annotation behavior
- archive indexing and restoration guidance

This change does not aim to delete history. It must preserve recoverability.

## Definitions

### Active Two-Stage Workflow

The active workflow is:

1. first-stage coarse labeling via `human_stage_1`
2. second-stage review / downstream refinement on top of segmented units

### One-Shot Annotation

For this cleanup, one-shot annotation means any historical path that bypasses the intended two-stage flow and performs direct single-stage frame-level annotation or its dedicated downstream/result stack.

## Design Principles

1. Active entry points must not advertise one-shot annotation
2. Historical code should move under `archive/`, not be deleted
3. Archived materials should keep enough original structure to be restorable
4. Active docs must clearly point to current sources of truth
5. Archive docs must explain what was moved, why, and how to restore it

## Archive Strategy

### Active Surface

Keep active only the two-stage resources and their supporting docs/tests.

### Archived Surface

Move one-shot resources into archive areas with preserved grouping:

- archived application code
- archived process/downstream code
- archived tests
- archived docs
- archived schema/context notes

### Restoration Metadata

Add archive README files that record:

- what the archived resource used to do
- which active path replaced it
- which data/schema it depended on
- how someone could recover it later

## Expected Active State

After cleanup:

- active docs no longer recommend one-shot annotation
- active application code no longer exposes one-shot annotation API paths
- active tests no longer validate one-shot behavior
- old one-shot code remains restorable under archive

## Verification

Verification should confirm:

1. active docs no longer mention one-shot annotation as supported workflow
2. active code paths no longer expose one-shot endpoints
3. archived files exist with restoration notes
4. active test suite still passes
