---
name: generate-tasks
description: Generate a two-phase implementation task list from a PRD/requirements. Phase 1 outputs parent tasks and pauses for 'Go'. Phase 2 outputs sub-tasks and relevant files, saved to /tasks/tasks-[feature-name].md.
---

# Generate Tasks

## When to use
Use this Skill when the user wants an implementation plan, task checklist, or engineering breakdown from a PRD/ADR.

## Instructions
1) Read the provided PRD (or requirements) and ADR summary rules.
2) Generate Phase 1 only: high-level parent tasks.
   - Must include 0.0 "Create feature branch" unless user says not to.
   - Keep it around ~5 parent tasks total.
3) Pause and ask the user to respond with "Go" to generate sub-tasks.
4) After "Go", generate Phase 2: detailed sub-tasks, relevant files, notes, and checklist formatting as specified in [reference.md](reference.md).
5) Save as: `/tasks/tasks-[feature-name].md`

## Output contract
- Tasks are ordered logically.
- Subtasks are concrete and checkable.
- Include test files where applicable.

## Reference
- Full task-list rulebook: [reference.md](reference.md)
