# Detailed plan

## Phase 0: Discovery and scope lock

- Confirm supported OSes and UI frameworks (Windows/macOS/Linux).
- Identify target languages and build systems for code autonomy.
- Define "sensitive change" taxonomy and approval workflow.
- Set performance targets for GUI reaction time.

## Phase 1: Core agent skeleton

- Implement Orchestrator and Planner interfaces.
- Define task graph schema and execution contracts.
- Create Executor APIs for code, CLI, and GUI.
- Add logging and artifact storage model.

## Phase 2: Code intelligence

- Implement repository scanning and indexing.
- Add dependency graph extraction.
- Provide structured code edit operations (patch/diff generation).
- Add formatting and linting integration hooks.

## Phase 3: GUI perception and action

- Add screen capture and OCR pipeline.
- Build UI element detection (template + ML fallback).
- Implement high-level action primitives (click, type, select).
- Add a rapid response loop for real-time UI events.

## Phase 4: Safety & approvals

- Implement sensitive-change classification.
- Create draft/diff generation and approval checkpoints.
- Add command allowlist/denylist enforcement.

## Phase 5: Reliability and resilience

- Add retry strategies for flaky UI.
- Introduce timeout management and recovery paths.
- Improve heuristics for UI element detection.

## Phase 6: Observability and audit

- Add structured logs for all actions.
- Record pre/post snapshots for code edits.
- Provide exportable audit reports.

## Phase 7: Hardening and release

- Add integration tests for representative repos and apps.
- Add performance benchmarks for reaction time.
- Deliver stable CLI and GUI tooling packages.
