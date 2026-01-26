# Architecture

## Overview

ShadowPCAgent is designed as a multi-process system with clear boundaries between planning, execution, perception, and safety. The architecture favors **modularity**, **auditability**, and **fast UI reaction** while preserving a **draft/diff approval gate** for sensitive changes.

## Core components

1. **Orchestrator**
   - Entry point for user requests.
   - Performs task decomposition, risk evaluation, and capability routing.
   - Owns the global task graph and coordination state.

2. **Planner**
   - Generates a step-by-step execution plan.
   - Keeps track of dependencies between subtasks.
   - Exposes a structured plan format for review and audit.

3. **Executors**
   - Specialized workers for:
     - **Code editing** (file modifications, patching, formatting).
     - **CLI operations** (build, test, package, deploy).
     - **GUI actions** (high-level UI interactions).

4. **Perception Engine**
   - Captures screen frames.
   - Extracts text via OCR.
   - Detects UI elements via template matching or ML detectors.
   - Produces a scene graph used by GUI executors.

5. **Safety & Policy Engine**
   - Classifies changes as sensitive/non-sensitive.
   - Enforces draft/diff approval for sensitive actions.
   - Maintains allow/deny command policies.

6. **Memory & Context Manager**
   - Stores repository map, user preferences, and system constraints.
   - Tracks prior actions and test outcomes for faster iteration.

## Data flow

1. User request → Orchestrator → Planner.
2. Planner builds task graph → Orchestrator dispatches tasks.
3. Executors perform tasks and report state.
4. Safety Engine validates actions and gates sensitive changes.
5. Memory Manager stores outcomes and artifacts.

## Key design decisions

- **Separation of concerns**: GUI operations are isolated from code editing.
- **Draft/diff gate**: sensitive changes always require user approval.
- **Fast reaction loop**: UI perception and action are event-driven where possible.
- **Auditing**: every action is logged for postmortem analysis.
