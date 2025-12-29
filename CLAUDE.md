# RAG Benchmark Curator (MCQ + Evidence)

## Project intent
Build a universal benchmark curation system that converts arbitrary input documents into an evaluation dataset of multiple-choice questions (A–D) with answer keys and gold evidence spans. Primary use: compare Naive RAG vs Agentic RAG while holding retrieval constant (Frozen Retrieval mode) to measure reasoning/orchestration lift.

## Non-negotiables (ADR-0001)
- Dataset item format: MCQ with 4 options (A–D), single correct answer key, and gold evidence spans (doc_id + chunk_id + offsets/page refs).
- Every item must include:
  - required_hops (1/2/3) and slice (A/B/C)
  - reasoning_type and at least one failure_mode label
- Two evaluation modes:
  1) Frozen Retrieval (reasoning-only): Naive and Agentic receive identical retrieved chunks in the same order; agentic must not re-retrieve.
  2) End-to-End: systems retrieve normally (separate reported metric).
- Headline metric: deterministic MCQ accuracy (exact match A/B/C/D).
- LLM-as-judge is optional and must not change the headline score (use only for dataset QA or diagnostics).

## Repo conventions
- Canonical Document Representation (CDR) is the internal interface:
  - doc_id, source_type, chunk_id, text, and (optional) page_ref/section_path/table_json.
- QIDs must be stable and unique (e.g., {doc_id}_{index}).
- JSONL is the default interchange format for chunks and MCQ items.
- Always log error taxonomy during eval:
  - retrieval_miss, reasoning_miss, benchmark_ambiguity.

## Recommended layout
- `ADR/` (decision records)
- `tasks/` (PRDs, task lists)
- `data/` (corpora, chunks, generated datasets, frozen contexts)
- `src/` (ingest, generate, validate, eval, report)
- `.claude/skills/` (workflows)

## Commands (fill in as the repo stabilizes)
- Setup: `<cmd>`
- Format: `<cmd>`
- Lint: `<cmd>`
- Tests: `<cmd>`
- Ingest → chunks: `<cmd>`
- Generate MCQ dataset: `<cmd>`
- Validate dataset: `<cmd>`
- Build frozen contexts: `<cmd>`
- Evaluate (Frozen Retrieval): `<cmd>`
- Evaluate (End-to-End): `<cmd>`
- Report: `<cmd>`

## Definition of Done (for any feature/PR)
- Adds/updates unit tests for new logic.
- Deterministic runs where applicable (seeded).
- Validator gates pass (no ambiguous items).
- Eval output includes per-slice and hop-count breakdown.
- Frozen Retrieval mode remains supported and documented.

## How to work with Claude Code
- Use Skills for long workflows:
  - create-prd, generate-tasks, mcq-item-generator, mcq-item-validator, frozen-retrieval-eval, reporting
- Keep ADR constraints above in mind for every implementation.
