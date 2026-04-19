# Two-Stage Resource Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove one-shot annotation from the active repository surface, archive its code/docs/tests with restoration context, and leave only the two-stage workflow as the supported path.

**Architecture:** First inventory and classify one-shot resources, then archive complete file-level one-shot stacks and trim mixed active files so their public interfaces only expose two-stage behavior. Finally, rewrite active documentation and add archive restoration/index documents so old structures remain recoverable.

**Tech Stack:** Python, repository file moves, Markdown docs, `unittest`

---

### Task 1: Add Guardrail Tests For Active Surface

**Files:**
- Modify: `codes/test/test_repo_layout.py`
- Create: `codes/test/test_two_stage_repo_surface.py`

- [ ] **Step 1: Write failing tests that define the new active surface**
- [ ] **Step 2: Verify those tests fail against the current repository**
- [ ] **Step 3: Cover active-doc references, active one-shot endpoints, and archived-path expectations**

### Task 2: Archive File-Level One-Shot Stacks

**Files:**
- Move: one-shot application/process/test/doc files into archive locations
- Create: archive README and restoration notes

- [ ] **Step 1: Move full one-shot downstream/result stacks into archive**
- [ ] **Step 2: Preserve readable structure under archive**
- [ ] **Step 3: Add restoration context including schema/data dependencies**

### Task 3: Remove Mixed One-Shot Paths From Active Files

**Files:**
- Modify: active application/server/web/test files that still expose frame-mode one-shot paths

- [ ] **Step 1: Remove one-shot API handlers from active review server surface**
- [ ] **Step 2: Remove or archive tests that validate one-shot behavior**
- [ ] **Step 3: Keep only two-stage behavior in active interfaces**

### Task 4: Rewrite Active Resource Documentation

**Files:**
- Modify: active docs and code-adjacent README files

- [ ] **Step 1: Rewrite root docs to say only two-stage is supported**
- [ ] **Step 2: Remove active references to archived one-shot materials**
- [ ] **Step 3: Point recovery-oriented readers at archive indexes instead**

### Task 5: Verify And Report

**Files:**
- Test: active test suite
- Inspect: archive and active doc sets

- [ ] **Step 1: Run active tests**
- [ ] **Step 2: Re-scan repository for one-shot references in active paths**
- [ ] **Step 3: Summarize what stayed active versus what moved to archive**
