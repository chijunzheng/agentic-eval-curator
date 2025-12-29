# Tasks: RAG Benchmark Curation System

## Relevant Files

### Core Source Files
- `src/__init__.py` - Package initialization
- `src/cli.py` - Main CLI entry point with Click commands
- `src/ingest/__init__.py` - Ingestion module initialization
- `src/ingest/parsers.py` - Document parsers for PDF, TXT, MD, CSV, JSON, HTML
- `src/ingest/chunker.py` - Chunking strategies (fixed window, semantic, table-aware)
- `src/ingest/cdr.py` - Canonical Document Representation dataclass and utilities
- `src/ingest/manifest.py` - Corpus manifest management for incremental ingestion
- `src/generate/__init__.py` - Generation module initialization
- `src/generate/mcq_generator.py` - MCQ generation logic using Gemini API
- `src/generate/prompts.py` - Prompt templates for each slice (A/B/C)
- `src/generate/evidence.py` - Gold evidence span extraction utilities
- `src/validate/__init__.py` - Validation module initialization
- `src/validate/validator.py` - MCQ item validation logic
- `src/validate/rules.py` - Validation rules (single answer, ambiguity, evidence exists)
- `src/frozen/__init__.py` - Frozen context module initialization
- `src/frozen/builder.py` - Frozen context builder with distractor selection
- `src/frozen/distractors.py` - Distractor selection strategies
- `src/export/__init__.py` - Export module initialization
- `src/export/exporter.py` - JSONL export logic for datasets
- `src/models.py` - Pydantic models for MCQItem, CDRChunk, FrozenContext, etc.
- `src/config.py` - Configuration loading and validation

### Test Files
- `tests/__init__.py` - Test package initialization
- `tests/conftest.py` - Pytest fixtures and shared test utilities
- `tests/test_parsers.py` - Unit tests for document parsers
- `tests/test_chunker.py` - Unit tests for chunking strategies
- `tests/test_cdr.py` - Unit tests for CDR conversion
- `tests/test_manifest.py` - Unit tests for corpus manifest
- `tests/test_mcq_generator.py` - Unit tests for MCQ generation (mocked API)
- `tests/test_validator.py` - Unit tests for validation rules
- `tests/test_frozen_builder.py` - Unit tests for frozen context builder
- `tests/test_exporter.py` - Unit tests for export functionality
- `tests/test_cli.py` - Integration tests for CLI commands

### Configuration Files
- `configs/default.yaml` - Default pipeline configuration
- `configs/chunking.yaml` - Chunking strategy configurations
- `configs/generation.yaml` - MCQ generation parameters

### Data Directories (created at runtime)
- `data/raw/` - Input documents
- `data/chunks/` - CDR chunks (JSONL)
- `data/generated/` - Generated MCQ items (JSONL)
- `data/validated/` - Validated items (JSONL)
- `data/rejected/` - Rejected items (JSONL)
- `data/frozen_contexts/` - Frozen retrieval contexts (JSONL)
- `data/corpus_manifest.json` - Incremental ingestion manifest

### Project Files
- `pyproject.toml` - Project metadata and dependencies
- `requirements.txt` - Pinned dependencies
- `.env.example` - Environment variable template (API keys)

### Notes

- Unit tests should be placed in the `tests/` directory mirroring the `src/` structure.
- Run tests with `pytest tests/` or `pytest tests/test_specific.py`.
- Use `python -m src.cli <command>` to run CLI commands during development.

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch: `git checkout -b feature/rag-benchmark-curation`

- [x] 1.0 Set up project structure and dependencies
  - [x] 1.1 Create directory structure: `src/`, `src/ingest/`, `src/generate/`, `src/validate/`, `src/frozen/`, `src/export/`, `tests/`, `configs/`, `data/`
  - [x] 1.2 Create `pyproject.toml` with project metadata, Python 3.11+ requirement, and pinned dependencies (click, google-generativeai, pydantic, pdfplumber, beautifulsoup4, pyyaml, python-dotenv, pytest, ruff)
  - [x] 1.3 ~~Create `requirements.txt`~~ (skipped: using pyproject.toml with pinned versions)
  - [x] 1.4 Create `.env.example` with `GEMINI_API_KEY=your_key_here`
  - [x] 1.5 Create `src/__init__.py` and all module `__init__.py` files
  - [x] 1.6 Create `src/models.py` with Pydantic models:
    - `CDRChunk` (doc_id, source_type, chunk_id, text, page_ref, section_path, table_json)
    - `GoldEvidence` (doc_id, chunk_id, char_start, char_end, page_ref)
    - `MCQItem` (qid, question, options, answer_key, gold_evidence, slice, required_hops, reasoning_type, failure_modes)
    - `FrozenContext` (qid, chunks: list of chunk_id + text)
  - [x] 1.7 Create `src/config.py` with config loading from YAML and CLI overrides
  - [x] 1.8 Create `configs/default.yaml` with sensible defaults for all pipeline stages
  - [x] 1.9 Create `tests/conftest.py` with shared fixtures (sample chunks, sample items, temp directories)
  - [x] 1.10 Verify setup: run `pip install -e .` and `pytest tests/` (should pass with no tests yet)

- [x] 2.0 Implement document ingestion pipeline
  - [x] 2.1 Create `src/ingest/cdr.py`:
    - `CDRConverter` class with `to_cdr()` method
    - Generate stable `doc_id` from file path hash
    - Generate stable `chunk_id` as `{doc_id}_{index}`
  - [x] 2.2 Create `src/ingest/parsers.py`:
    - `BaseParser` abstract class with `parse(file_path) -> str` method
    - `TextParser` for `.txt` and `.md` files
    - `PDFParser` for `.pdf` files (extract text, preserve page refs)
    - `CSVParser` for `.csv` files (convert rows to text, preserve table structure)
    - `JSONParser` for `.json` files (flatten or stringify)
    - `HTMLParser` for `.html` files (strip tags, extract text)
    - `get_parser(file_path)` factory function
  - [x] 2.3 Create `src/ingest/chunker.py`:
    - `BaseChunker` abstract class with `chunk(text, metadata) -> list[CDRChunk]`
    - `FixedWindowChunker` (configurable token/char window with overlap)
    - `SemanticChunker` (paragraph-based splitting)
    - `TableAwareChunker` (preserve table boundaries, store `table_json`)
    - `get_chunker(strategy_name)` factory function
  - [x] 2.4 Create `src/ingest/manifest.py`:
    - `CorpusManifest` class to track ingested files
    - Store: `{doc_id: {path, checksum (SHA-256), timestamp, chunk_count}}`
    - Methods: `load()`, `save()`, `is_modified(file_path)`, `update(doc_id, metadata)`
    - Default path: `data/corpus_manifest.json`
  - [x] 2.5 Create `src/ingest/pipeline.py`:
    - `IngestPipeline` class orchestrating parse → chunk → save
    - Support `--incremental` flag (skip unchanged files via manifest)
    - Output chunks to `data/chunks/{doc_id}.jsonl`
    - Update manifest after successful ingestion
  - [x] 2.6 Write `tests/test_parsers.py`:
    - Test each parser with sample files
    - Test `get_parser()` factory
    - Test error handling for unsupported formats
  - [x] 2.7 Write `tests/test_chunker.py`:
    - Test each chunking strategy
    - Test chunk_id stability
    - Test overlap handling
  - [x] 2.8 Write `tests/test_manifest.py`:
    - Test manifest load/save
    - Test `is_modified()` with changed/unchanged files
  - [x] 2.9 Write `tests/test_cdr.py`:
    - Test CDR conversion
    - Test doc_id and chunk_id generation stability

- [x] 3.0 Implement MCQ generation with Gemini API
  - [x] 3.1 Create `src/generate/prompts.py`:
    - `SLICE_A_PROMPT` (1-hop factual lookup)
    - `SLICE_B_PROMPT` (2-hop compositional reasoning)
    - `SLICE_C_PROMPT` (hard agentic: exceptions, precedence, contradictions, table+prose joins)
    - `format_prompt(slice, chunks, config)` function
    - Include reasoning_type and failure_mode label requirements in prompts
  - [x] 3.2 Create `src/generate/evidence.py`:
    - `extract_evidence_spans(question, answer, chunks) -> list[GoldEvidence]`
    - Find exact text matches for answer content in source chunks
    - Calculate character offsets
  - [x] 3.3 Create `src/generate/mcq_generator.py`:
    - `MCQGenerator` class with Gemini API client
    - `generate(chunks, slice, config) -> list[MCQItem]`
    - Parse structured output from Gemini (JSON mode)
    - Assign stable QIDs: `{doc_id}_{index}`
    - Set `required_hops` based on slice (A=1, B=2, C=2-3)
    - Support seeded generation via config
  - [x] 3.4 Create `src/generate/pipeline.py`:
    - `GenerationPipeline` class orchestrating chunk loading → generation → save
    - Load chunks from `data/chunks/`
    - Group chunks by doc_id or sliding window for context
    - Output items to `data/generated/{batch_id}.jsonl`
    - Log generation stats (items per slice, failures)
  - [x] 3.5 Write `tests/test_mcq_generator.py`:
    - Mock Gemini API responses
    - Test QID generation stability
    - Test slice assignment
    - Test error handling for API failures
  - [x] 3.6 Write `tests/test_evidence.py`:
    - Test evidence span extraction
    - Test offset calculation accuracy

- [x] 4.0 Implement validation pipeline
  - [x] 4.1 Create `src/validate/rules.py`:
    - `Rule` base class with `validate(item, chunks) -> (bool, str)`
    - `SingleAnswerRule` - verify exactly one answer marked correct
    - `EvidenceExistsRule` - verify gold evidence spans exist in referenced chunks
    - `AmbiguityRule` - flag items where distractors are too similar to correct answer (basic string similarity)
    - `OptionsCompleteRule` - verify all 4 options (A-D) are present and non-empty
    - `HopCountRule` - verify required_hops is consistent with slice assignment
    - `EvidenceCountRule` - verify evidence count matches required hops
  - [x] 4.2 Create `src/validate/validator.py`:
    - `Validator` class with configurable rule list
    - `validate(item, chunks) -> ValidationResult` (passed, failed_rules, warnings)
    - `validate_batch(items, chunks) -> ValidationReport`
  - [x] 4.3 Create `src/validate/pipeline.py`:
    - `ValidationPipeline` class orchestrating load → validate → partition
    - Load items from `data/generated/`
    - Load chunks for evidence verification
    - Output passed items to `data/validated/`
    - Output failed items to `data/rejected/` with failure reasons
    - Generate validation report (pass/fail counts, flagged item IDs)
  - [x] 4.4 Write `tests/test_validator.py`:
    - Test each validation rule
    - Test with valid and invalid items
    - Test report generation

- [x] 5.0 Implement frozen context builder
  - [x] 5.1 Create `src/frozen/distractors.py`:
    - `DistractorSelector` base class with `select(item, all_chunks, n) -> list[CDRChunk]`
    - `RandomSelector` - randomly sample n chunks excluding gold
    - `SameDocSelector` - prefer chunks from same doc as gold (tests intra-doc filtering)
    - `SemanticSelector` - select chunks with high embedding similarity but different content (optional, can be stub for v1)
    - `get_selector(strategy_name)` factory function
  - [x] 5.2 Create `src/frozen/builder.py`:
    - `FrozenContextBuilder` class
    - `build(item, all_chunks, config) -> FrozenContext`
    - Include gold evidence chunks + n distractor chunks (default n=10)
    - Shuffle order to avoid position bias
    - Store chunk_id and full text for each chunk
  - [x] 5.3 Create `src/frozen/pipeline.py`:
    - `FrozenPipeline` class orchestrating load → build → save
    - Load validated items from `data/validated/`
    - Load all chunks from `data/chunks/`
    - Output frozen contexts to `data/frozen_contexts/`
  - [x] 5.4 Write `tests/test_frozen_builder.py`:
    - Test distractor selection strategies
    - Test frozen context includes gold chunks
    - Test distractor count is correct
    - Test shuffling

- [ ] 6.0 Implement export and CLI commands
  - [ ] 6.1 Create `src/export/exporter.py`:
    - `DatasetExporter` class
    - `export_core(items, output_path)` - export `dataset.jsonl` with core fields
    - `export_frozen(items, frozen_contexts, output_path)` - export `dataset_frozen.jsonl` with frozen context attached
    - `export_manifest(items, config, output_path)` - export manifest with corpus metadata, generation config, item counts per slice
  - [ ] 6.2 Create `src/cli.py`:
    - Use Click framework
    - `@click.group()` main entry point
    - `ingest` command: `--input-dir`, `--config`, `--incremental`, `--dry-run`, `--seed`
    - `generate` command: `--config`, `--slice` (A/B/C/all), `--dry-run`, `--seed`
    - `validate` command: `--config`, `--dry-run`
    - `build-frozen` command: `--config`, `--distractor-strategy`, `--distractor-count`, `--dry-run`, `--seed`
    - `export` command: `--output-dir`, `--include-frozen`, `--config`
    - All commands support `--config` for YAML config file
  - [ ] 6.3 Update `pyproject.toml` with CLI entry point:
    - `[project.scripts]` section: `rag-bench = "src.cli:main"`
  - [ ] 6.4 Write `tests/test_exporter.py`:
    - Test JSONL export format
    - Test manifest generation
    - Test frozen dataset structure
  - [ ] 6.5 Write `tests/test_cli.py`:
    - Integration tests for each CLI command
    - Test `--dry-run` mode
    - Test `--config` loading
    - Test error handling for missing inputs
  - [ ] 6.6 Create sample config files:
    - `configs/chunking.yaml` - chunking strategy options
    - `configs/generation.yaml` - Gemini API parameters, slice prompts
  - [ ] 6.7 End-to-end test: run full pipeline on sample documents
    - Create `tests/fixtures/` with sample PDF, TXT, CSV
    - Run ingest → generate → validate → build-frozen → export
    - Verify output files exist and are valid JSONL
  - [ ] 6.8 Update `CLAUDE.md` Commands section with actual CLI commands
  - [ ] 6.9 Update `progress.md` with implementation status
