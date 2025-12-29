---
name: create-prd
description: Create a PRD markdown file from a feature idea. Ask 3–5 essential clarifying questions with A/B/C options, then write /tasks/prd-[feature-name].md. Do not implement code.
---

# Create PRD

## When to use
Use this Skill when the user asks for a PRD, product spec, or wants to clarify scope/requirements before implementation.

## Instructions
1) Read ADR summary rules (especially ADR-0001). Ensure the PRD aligns.
2) Ask 3–5 clarifying questions max.
   - Number questions (1,2,3…)
   - Provide options A/B/C/D for each
   - Optimize for “what/why/scope/success”, not implementation details
3) After user answers, generate a PRD in Markdown using the PRD structure in [reference.md](reference.md).
4) Save as: `/tasks/prd-[feature-name].md`
5) Do not start implementation.

## Output contract
- The PRD is suitable for a junior developer.
- Requirements are numbered, explicit, and testable.
- Include non-goals and success metrics.

## Reference
- Full PRD rulebook: [reference.md](reference.md)
