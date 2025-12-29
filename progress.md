# Progress Log: Agentic Eval Curator

## Approach

Building a universal benchmark curation system that converts arbitrary input documents (3GPP RAN, ORAN specs, etc.) into an MCQ evaluation dataset. The dataset is designed to:

1. **Compare agentic RAG vs pure RAG** — Measure the value of agentic orchestration
2. **Evaluate architecture changes** — Track regression/improvement on agent performance
3. **Isolate reasoning from retrieval** — Via Frozen Retrieval mode (identical chunks for all systems)

**Key architectural decisions:**
- CLI-based batch pipeline (no web UI)
- Gemini API (`gemini-2.5-flash`) for MCQ generation
- Two evaluation modes: End-to-End and Frozen Retrieval
- 10 context distractor chunks per frozen context
- Custom eval dataset (no integration with RAGAS/LangChain Evaluators)
- Python 3.11+, Pydantic models, JSONL interchange format

**GitHub Repository:** https://github.com/chijunzheng/agentic-eval-curator

---

## Steps Completed

### 1. Repository Setup (Planning Phase)
- [x] Created initial `CLAUDE.md` with project conventions and ADR constraints
- [x] Explored existing skills: `create-prd`, `generate-tasks`
- [x] Read ADR-0001 summary (MCQ format, slices, eval modes)

### 2. PRD Creation (`/create-prd` workflow)
- [x] Asked 5 clarifying questions with A/B/C/D options
- [x] User selections:
  - 1D: All document types (PDF, text, CSV, JSON, HTML)
  - 2A: Fully automated LLM generation with human review
  - 3A: CLI tool (batch processing)
  - 4B: Medium scale (≤1,000 docs, ≤5,000 MCQ items)
  - 5A: Dataset export only (JSONL), no built-in eval runner
- [x] Added incremental ingestion support (per user request)
- [x] Clarified terminology: MCQ distractors vs context distractors, frozen context
- [x] Finalized LLM choice: `gemini-2.5-flash`
- [x] Saved PRD to `tasks/prd-rag-benchmark-curation.md`

### 3. Skill Created: `mcq-prompt-generator`
- [x] Created `.claude/skills/mcq-prompt-generator/SKILL.md`
- [x] Created `.claude/skills/mcq-prompt-generator/reference.md` with:
  - YAML prompt template structure
  - Slice-specific strategies (A: 1-hop, B: 2-hop, C: hard agentic)
  - 3GPP RAN and ORAN terminology tables
  - Reasoning type and failure mode labels
  - Distractor quality guidelines
  - Evidence span extraction rules

### 4. Implementation Task List Generated
- [x] Created `tasks/tasks-rag-benchmark-curation.md` with 6 parent tasks, 43 sub-tasks
- [x] Task breakdown: project setup, ingestion, generation, validation, frozen context, export/CLI

### 5. Git + GitHub Setup (Task 0.0)
- [x] Initialized git repository
- [x] Created `.gitignore` for Python project
- [x] Initial commit with PRD, task list, skills, and config files
- [x] Created feature branch: `feature/rag-benchmark-curation`
- [x] Connected to remote: `git@github.com:chijunzheng/agentic-eval-curator.git`
- [x] Pushed `main` and `feature/rag-benchmark-curation` branches

### 6. Project Structure + Dependencies (Task 1.0)
- [x] Created directory structure:
  ```
  src/ingest/, src/generate/, src/validate/, src/frozen/, src/export/
  tests/, configs/, data/
  ```
- [x] Created `pyproject.toml` with pinned dependencies:
  - click, google-generativeai, pydantic, pdfplumber, beautifulsoup4, pyyaml, python-dotenv
  - Dev: pytest, pytest-cov, ruff
- [x] Skipped separate `requirements.txt` (using pyproject.toml with pinned versions)
- [x] Created `.env.example` with `GEMINI_API_KEY`
- [x] Created all `__init__.py` module files
- [x] Created `src/models.py` with Pydantic models:
  - `CDRChunk`, `GoldEvidence`, `MCQItem`, `FrozenContext`
  - `ValidationResult`, `CorpusManifestEntry`
  - Enums: `SourceType`, `Slice`, `ReasoningType`, `FailureMode`
- [x] Created `src/config.py` with YAML config loading and validation
- [x] Created `configs/default.yaml` with pipeline defaults
- [x] Created `tests/conftest.py` with shared pytest fixtures
- [x] Verified setup: `pip install -e ".[dev]"` and imports working

---

## Current Status

**No failures.** Task 1.0 complete. Ready to start Task 2.0.

---

## Current Files

```
agentic-eval-curator/
├── .env.example
├── .gitignore
├── .venv/                          # Virtual environment (not committed)
├── CLAUDE.md                       # Project conventions
├── progress.md                     # This file
├── pyproject.toml                  # Package config + pinned deps
│
├── .claude/
│   ├── rules/
│   │   └── adr-0001-summary.md
│   └── skills/
│       ├── create-prd/
│       ├── generate-tasks/
│       └── mcq-prompt-generator/
│
├── configs/
│   └── default.yaml                # Pipeline defaults
│
├── data/                           # Runtime data (gitignored subdirs)
│
├── src/
│   ├── __init__.py
│   ├── config.py                   # Config loading
│   ├── models.py                   # Pydantic models
│   ├── ingest/                     # (empty, Task 2.0)
│   ├── generate/                   # (empty, Task 3.0)
│   ├── validate/                   # (empty, Task 4.0)
│   ├── frozen/                     # (empty, Task 5.0)
│   └── export/                     # (empty, Task 6.0)
│
├── tasks/
│   ├── prd-rag-benchmark-curation.md
│   └── tasks-rag-benchmark-curation.md
│
└── tests/
    ├── __init__.py
    └── conftest.py                 # Shared fixtures
```

---

## Next Steps

1. **Task 2.0: Implement document ingestion pipeline**
   - 2.1 `src/ingest/cdr.py` — CDRConverter class
   - 2.2 `src/ingest/parsers.py` — PDF, TXT, MD, CSV, JSON, HTML parsers
   - 2.3 `src/ingest/chunker.py` — Fixed window, semantic, table-aware chunking
   - 2.4 `src/ingest/manifest.py` — Corpus manifest for incremental ingestion
   - 2.5 `src/ingest/pipeline.py` — Orchestration
   - 2.6-2.9 Unit tests

2. **Task 3.0: Implement MCQ generation**
3. **Task 4.0: Implement validation**
4. **Task 5.0: Implement frozen context builder**
5. **Task 6.0: Implement export + CLI**

---

## Commands

```bash
# Setup
cd /path/to/agentic-eval-curator
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/

# Lint
ruff check src/ tests/
```
