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

### 7. Document Ingestion Pipeline (Task 2.0)
- [x] Created `src/ingest/cdr.py`:
  - `CDRConverter` class with `to_cdr()` method
  - `generate_doc_id()` using SHA-256 hash of absolute path (12 hex chars)
  - `generate_chunk_id()` as `{doc_id}_{index}`
  - `get_source_type()` for file extension mapping
- [x] Created `src/ingest/parsers.py`:
  - `BaseParser` abstract class with `parse() -> ParseResult`
  - `TextParser` for `.txt` and `.md` (UTF-8 text extraction)
  - `PDFParser` for `.pdf` (pdfplumber, page refs, table extraction)
  - `CSVParser` for `.csv` (pipe-delimited text, table structure)
  - `JSONParser` for `.json` (recursive flattening to key: value format)
  - `HTMLParser` for `.html` (BeautifulSoup, script/style stripping, table extraction)
  - `get_parser()` factory function
- [x] Created `src/ingest/chunker.py`:
  - `BaseChunker` abstract class with `chunk(ParseResult) -> list[ChunkMetadata]`
  - `FixedWindowChunker` (configurable size/overlap, page ref tracking)
  - `SemanticChunker` (paragraph-based, merges small paragraphs)
  - `TableAwareChunker` (preserves tables as separate chunks with table_json)
  - `get_chunker()` factory function
- [x] Created `src/ingest/manifest.py`:
  - `CorpusManifest` class for incremental ingestion tracking
  - SHA-256 file checksums for change detection
  - Methods: `load()`, `save()`, `is_modified()`, `update()`, `remove()`
- [x] Created `src/ingest/pipeline.py`:
  - `IngestPipeline` class orchestrating parse → chunk → CDR → save
  - Incremental mode (skip unchanged files via manifest)
  - Dry-run mode support
  - JSONL output to `data/chunks/{doc_id}.jsonl`
  - `IngestStats` dataclass for run statistics
- [x] Updated `src/ingest/__init__.py` with exports
- [x] Created unit tests (71 tests total, all passing):
  - `tests/test_parsers.py` - Parser tests (11 tests)
  - `tests/test_chunker.py` - Chunker tests (16 tests)
  - `tests/test_manifest.py` - Manifest tests (16 tests)
  - `tests/test_cdr.py` - CDR conversion tests (22 tests)

### 8. MCQ Generation Pipeline (Task 3.0)
- [x] Created `src/generate/prompts.py`:
  - Slice-specific prompts: `SLICE_A_PROMPT` (1-hop), `SLICE_B_PROMPT` (2-hop), `SLICE_C_PROMPT` (hard agentic)
  - `format_prompt()` function combining chunks with slice prompts
  - `format_chunk_data()` for chunk formatting with metadata
  - JSON output schema for Gemini structured output mode
  - `get_required_hops()` mapping slice to hop count
- [x] Created `src/generate/evidence.py`:
  - `find_span_in_chunk()` - exact/normalized/case-insensitive text matching
  - `extract_evidence_spans()` - converts LLM text spans to `GoldEvidence` objects
  - `validate_evidence_spans()` - verifies references exist in chunks
  - `get_evidence_text()` - retrieves actual evidence text
- [x] Created `src/generate/mcq_generator.py`:
  - `MCQGenerator` class wrapping Gemini API with JSON mode
  - `generate(chunks, slice_type)` returns `GenerationResult` with items/errors
  - Mapping dicts for `ReasoningType` and `FailureMode` enums
  - Stable QID generation: `{doc_id}_q{counter}`
  - Error handling for API failures and invalid JSON
- [x] Created `src/generate/pipeline.py`:
  - `GenerationPipeline` class orchestrating full workflow
  - Loads chunks from `data/chunks/`, groups by doc_id
  - Creates overlapping chunk windows for context
  - Outputs to `data/generated/{batch_id}.jsonl`
  - `GenerationStats` dataclass for tracking
- [x] Updated `src/generate/__init__.py` with exports
- [x] Created unit tests (44 new tests, 115 total):
  - `tests/test_evidence.py` - Evidence extraction tests (22 tests)
  - `tests/test_mcq_generator.py` - Generator tests with mocked API (22 tests)

### 9. Validation Pipeline (Task 4.0)
- [x] Created `src/validate/rules.py`:
  - `Rule` abstract base class with `validate(item, chunks) -> (bool, str)`
  - `SingleAnswerRule` - verify answer_key is A/B/C/D
  - `OptionsCompleteRule` - verify all 4 options present and non-empty
  - `EvidenceExistsRule` - verify gold evidence spans exist in referenced chunks
  - `AmbiguityRule` - flag items where distractors too similar to correct answer (SequenceMatcher)
  - `HopCountRule` - verify required_hops consistent with slice assignment
  - `EvidenceCountRule` - verify evidence count >= required_hops
  - `get_default_rules()` and `get_rule()` factory functions
  - `AVAILABLE_RULES` registry for all rules
- [x] Created `src/validate/validator.py`:
  - `Validator` class with configurable rule list
  - `validate(item, chunks) -> ValidationResult`
  - `validate_batch(items, chunks) -> ValidationReport`
  - `ValidationReport` dataclass with pass_rate, failure_counts, to_dict()
  - Methods: `add_rule()`, `remove_rule()`, `get_rule_names()`
- [x] Created `src/validate/pipeline.py`:
  - `ValidationPipeline` class orchestrating load → validate → partition
  - Loads items from `data/generated/` and chunks from `data/chunks/`
  - Partitions into `data/validated/` (passed) and `data/rejected/` (failed)
  - Saves validation report as JSON
  - `ValidationStats` dataclass for run statistics
  - `validate_single()` convenience method
- [x] Updated `src/validate/__init__.py` with exports
- [x] Created unit tests (59 new tests, 174 total):
  - `tests/test_validator.py` - All validation tests (59 tests)

### 10. Frozen Context Builder (Task 5.0)
- [x] Created `src/frozen/distractors.py`:
  - `DistractorSelector` abstract base class with `select(item, all_chunks, n, seed)`
  - `RandomSelector` - randomly sample n chunks excluding gold evidence
  - `SameDocSelector` - prefer chunks from same document as gold (tests intra-doc filtering)
  - `SemanticSelector` - stub implementation (falls back to random for v1)
  - `get_selector()` factory function
  - `AVAILABLE_SELECTORS` registry
- [x] Created `src/frozen/builder.py`:
  - `FrozenContextBuilder` class with configurable strategy and distractor count
  - `build(item, all_chunks, seed) -> BuildResult`
  - `build_batch()` for multiple items
  - Includes gold evidence chunks + n distractor chunks (default n=10)
  - Shuffles order to avoid position bias
  - `BuildResult` dataclass with context, counts, and missing gold info
- [x] Created `src/frozen/pipeline.py`:
  - `FrozenPipeline` class orchestrating load → build → save
  - Loads validated items from `data/validated/`
  - Loads all chunks from `data/chunks/`
  - Outputs frozen contexts to `data/frozen_contexts/`
  - `FrozenStats` dataclass with duration, averages, and to_dict()
  - `build_single()` convenience method
- [x] Updated `src/frozen/__init__.py` with exports
- [x] Created unit tests (46 new tests, 220 total):
  - `tests/test_frozen_builder.py` - All frozen context tests (46 tests)

### 11. Export + CLI (Task 6.0)
- [x] Created `src/export/exporter.py`:
  - `DatasetExporter` class with export_core(), export_frozen(), export_manifest()
  - `ExportManifest` dataclass for dataset metadata
  - `ExportPipeline` class orchestrating validated items + frozen contexts → export
  - Core dataset (dataset.jsonl), frozen dataset (dataset_frozen.jsonl), manifest (manifest.json)
- [x] Created `src/cli.py`:
  - Click-based CLI with `rag-bench` entry point
  - `ingest` command: document ingestion with incremental support
  - `generate` command: MCQ generation with slice selection
  - `validate` command: validation pipeline with rule-based checking
  - `build-frozen` command: frozen context building with distractor strategies
  - `export` command: dataset export with optional frozen contexts
  - `status` command: pipeline status and data directory inspection
  - All commands support --config, --dry-run, and relevant options
- [x] Updated `src/export/__init__.py` with exports
- [x] Created `configs/chunking.yaml` with documented chunking options
- [x] Created `configs/generation.yaml` with Gemini API and frozen config options
- [x] Created unit tests (57 new tests, 277 total):
  - `tests/test_exporter.py` - Exporter tests (29 tests)
  - `tests/test_cli.py` - CLI integration tests (28 tests)
- [x] Updated `CLAUDE.md` with actual CLI commands

### 12. Additional File Format Support (ORAN Docs)
- [x] Added `DOCX`, `XLSX`, `YANG` to `SourceType` enum in `src/models.py`
- [x] Added dependencies to `pyproject.toml`:
  - `python-docx==1.1.2` for Microsoft Word documents
  - `openpyxl==3.1.5` for Microsoft Excel spreadsheets
- [x] Created `DocxParser` class in `src/ingest/parsers.py`:
  - Extracts paragraphs and tables from Word documents
  - Preserves table structure with headers
  - Appends table text representation for searchability
- [x] Created `XlsxParser` class in `src/ingest/parsers.py`:
  - Multi-sheet support with sheet name headers
  - Extracts data as pipe-delimited text
  - Stores table structure per sheet
  - Skips empty rows automatically
- [x] Created `YangParser` class in `src/ingest/parsers.py`:
  - Parses YANG data model files (RFC 6020, RFC 7950)
  - Extracts metadata: module name, namespace, prefix, organization, description
  - Prepends structured header to raw YANG content
- [x] Registered new parsers in `_PARSERS` registry
- [x] Added unit tests (16 new tests, 293 total):
  - `TestDocxParser` - 3 tests (paragraphs, tables, empty docs)
  - `TestXlsxParser` - 3 tests (single sheet, multiple sheets, empty rows)
  - `TestYangParser` - 3 tests (module, submodule, minimal content)
  - `TestGetParser` - 3 tests (docx, xlsx, yang factory functions)
- [x] Pushed to remote: `origin/feature/rag-benchmark-curation`

### 13. Fixed SemanticChunker Mid-Word Cuts
- [x] **Issue**: Chunks were being cut mid-word/mid-sentence even with semantic chunking
- [x] **Root cause**: `SemanticChunker` didn't handle paragraphs exceeding `max_chunk_size`
- [x] **Fix**: Added `_split_long_paragraph()` method with fallback hierarchy:
  1. Split at sentence boundaries (`.!?` followed by space)
  2. Split at newline boundaries (for TOC-like content)
  3. Split at word boundaries (last resort)
- [x] Added `_merge_segments()` to recombine segments up to max size
- [x] Added `_split_by_words()` for word-boundary splitting
- [x] Added 3 new unit tests for long-paragraph splitting (296 total)

---

## Current Status

**All tasks complete.** 296 tests passing. Pipeline is fully functional:
- Document ingestion (PDF, TXT, MD, CSV, JSON, HTML, DOCX, XLSX, YANG)
- MCQ generation with Gemini API
- Validation with 6 quality rules
- Frozen context building with 3 distractor strategies
- Dataset export with manifest

**No current failures.** Ready for end-to-end testing with ORAN source documents.

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
│   ├── default.yaml                # Pipeline defaults
│   ├── chunking.yaml               # Chunking strategy options
│   └── generation.yaml             # Gemini API parameters
│
├── data/                           # Runtime data (gitignored subdirs)
│
├── src/
│   ├── __init__.py
│   ├── cli.py                      # Click CLI (rag-bench command)
│   ├── config.py                   # Config loading
│   ├── models.py                   # Pydantic models
│   ├── ingest/
│   │   ├── __init__.py             # Module exports
│   │   ├── cdr.py                  # CDR conversion utilities
│   │   ├── chunker.py              # Chunking strategies
│   │   ├── manifest.py             # Corpus manifest for incremental ingestion
│   │   ├── parsers.py              # Document parsers (PDF, TXT, CSV, JSON, HTML, DOCX, XLSX, YANG)
│   │   └── pipeline.py             # Ingestion pipeline orchestration
│   ├── generate/
│   │   ├── __init__.py             # Module exports
│   │   ├── evidence.py             # Gold evidence span extraction
│   │   ├── mcq_generator.py        # Gemini API MCQ generation
│   │   ├── pipeline.py             # Generation pipeline orchestration
│   │   └── prompts.py              # Slice-specific prompt templates
│   ├── validate/
│   │   ├── __init__.py             # Module exports
│   │   ├── rules.py                # Validation rules (6 rules)
│   │   ├── validator.py            # Validator class with batch support
│   │   └── pipeline.py             # Validation pipeline orchestration
│   ├── frozen/
│   │   ├── __init__.py             # Module exports
│   │   ├── distractors.py          # Distractor selection strategies (3 strategies)
│   │   ├── builder.py              # FrozenContextBuilder class
│   │   └── pipeline.py             # Frozen context pipeline orchestration
│   └── export/
│       ├── __init__.py             # Module exports
│       └── exporter.py             # DatasetExporter and ExportPipeline
│
├── tasks/
│   ├── prd-rag-benchmark-curation.md
│   └── tasks-rag-benchmark-curation.md
│
└── tests/
    ├── __init__.py
    ├── conftest.py                 # Shared fixtures
    ├── test_cdr.py                 # CDR conversion tests (22 tests)
    ├── test_chunker.py             # Chunker tests (23 tests)
    ├── test_cli.py                 # CLI integration tests (28 tests)
    ├── test_evidence.py            # Evidence extraction tests (22 tests)
    ├── test_exporter.py            # Exporter tests (29 tests)
    ├── test_frozen_builder.py      # Frozen context tests (46 tests)
    ├── test_manifest.py            # Manifest tests (16 tests)
    ├── test_mcq_generator.py       # MCQ generator tests (22 tests)
    ├── test_parsers.py             # Parser tests (29 tests)
    └── test_validator.py           # Validation tests (59 tests)
```

---

## Next Steps

All implementation tasks (1.0 - 6.0) are complete. Ready for end-to-end testing:

1. **Run pipeline on ORAN source documents**:
   ```bash
   rag-bench ingest --input-dir /path/to/oran_specs/
   rag-bench generate
   rag-bench validate
   rag-bench build-frozen
   rag-bench export
   ```

2. **Potential enhancements** (if needed):
   - Add semantic distractor selection using embeddings
   - Add evaluation runner for frozen retrieval mode
   - Add reporting with per-slice and per-hop breakdowns

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

# Pipeline (end-to-end)
rag-bench ingest --input-dir /path/to/docs/   # Supports: PDF, TXT, MD, CSV, JSON, HTML, DOCX, XLSX, YANG
rag-bench generate --slice all                 # Requires GEMINI_API_KEY
rag-bench validate
rag-bench build-frozen
rag-bench export --output-dir data/export/
rag-bench status                               # Check pipeline state
```
