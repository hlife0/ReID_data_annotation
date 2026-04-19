# Step-Scheme Repository Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize active process/application/test resources under step-specific directories while preserving the agreed Step 0-5 workflow boundaries.

**Architecture:** Move active files into step-scoped subdirectories, add an explicit placeholder for Step 4, and separate support/devtool code from workflow steps. Then rewrite imports, tests, and docs so the active surface accurately reflects the new layout.

**Tech Stack:** Python, Markdown, file moves, `unittest`

---

### Task 1: Add Guardrail Tests For Step-Scoped Layout

**Files:**
- Modify: `codes/test/test_repo_layout.py`
- Create: `codes/test/support/`

- [ ] **Step 1: Write failing assertions for the new step directory layout**
- [ ] **Step 2: Verify those assertions fail before moving files**

### Task 2: Reorganize Active Process Code

**Files:**
- Move active process files into step/shared/devtools directories

- [ ] **Step 1: Move Step 0 files**
- [ ] **Step 2: Move Step 1 files**
- [ ] **Step 3: Move Step 2 files**
- [ ] **Step 4: Create Step 4 placeholder directory and README**
- [ ] **Step 5: Move Step 5 files**
- [ ] **Step 6: Move shared and devtool files**

### Task 3: Reorganize Active Application Code

**Files:**
- Move active application server/web files into step/support directories

- [ ] **Step 1: Move Step 3 application files**
- [ ] **Step 2: Move Step 5 application files**
- [ ] **Step 3: Move support/admin files**

### Task 4: Reorganize Tests

**Files:**
- Move active tests into step/support/devtools directories

- [ ] **Step 1: Move tests to step-scoped locations**
- [ ] **Step 2: Update imports and module paths**

### Task 5: Rewrite Imports And Active Docs

**Files:**
- Modify active Python imports
- Modify active docs and README references

- [ ] **Step 1: Update Python imports**
- [ ] **Step 2: Update docs to new file paths**
- [ ] **Step 3: Update active workflow explanations**

### Task 6: Verify And Stabilize

**Files:**
- Run active tests and path scans

- [ ] **Step 1: Run targeted layout tests**
- [ ] **Step 2: Run full active test suite**
- [ ] **Step 3: Re-scan active docs and code for stale flat-path references**
