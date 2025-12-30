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

## Commands

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Development
```bash
# Lint
ruff check src/ tests/

# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Pipeline Commands (CLI)
```bash
# Ingest documents into CDR chunks
rag-bench ingest --input-dir data/raw/ [--incremental] [--dry-run]

# Generate MCQ items from chunks (requires GEMINI_API_KEY)
rag-bench generate [--slice A|B|C|all] [--seed 42] [--dry-run]

# Validate generated items
rag-bench validate [--dry-run]

# Build frozen retrieval contexts
rag-bench build-frozen [--distractor-strategy random|same_doc|semantic] [-n 10] [--seed 42] [--dry-run]

# Export final dataset
rag-bench export [--output-dir data/export/] [--include-frozen|--no-frozen]

# Check pipeline status
rag-bench status
```

### CLI Options
All commands support:
- `--config FILE` or `-c FILE`: Path to YAML config file (default: configs/default.yaml)
- `--help`: Show command help

### Environment Variables
- `GEMINI_API_KEY`: Required for the `generate` command

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
