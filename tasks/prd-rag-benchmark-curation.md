# PRD: Universal RAG Benchmark Curation System (MCQ Eval Set)

## 1. Introduction / Overview

This system converts arbitrary input documents into a high-quality evaluation dataset of multiple-choice questions (MCQ) for benchmarking Retrieval-Augmented Generation (RAG) systems.

**Primary use cases:**
1. Compare production-grade agentic RAG vs pure RAG systems
2. Evaluate the impact of architecture changes on agent performance
3. Isolate reasoning/orchestration quality from retrieval quality via Frozen Retrieval mode

**Problem:** Existing RAG benchmarks conflate retrieval quality with reasoning quality, making it hard to isolate where agentic orchestration adds value. Teams also lack tooling to quickly generate domain-specific eval sets from their own corpora.

**Solution:** A CLI-based curation pipeline that ingests documents, chunks them into a canonical format, uses an LLM to generate MCQ items with gold evidence spans, validates item quality, and exports JSONL datasets for custom evaluation.

## 2. Goals

1. Enable creation of MCQ eval datasets from any document corpus in under a day of human effort (for medium-scale corpora).
2. Produce items that are unambiguous, have exactly one correct answer, and include traceable gold evidence.
3. Support difficulty/complexity segmentation via slices (A/B/C) and hop counts (1/2/3).
4. Output datasets compatible with both evaluation modes:
   - **End-to-End:** System retrieves its own chunks, then answers.
   - **Frozen Retrieval:** System receives pre-determined chunks (same for all systems), isolating reasoning from retrieval.
5. Maintain deterministic, reproducible runs (seeded generation).

## 3. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-1 | Benchmark creator | Ingest PDFs, text files, CSVs, and HTML pages into a unified chunk format | I can work with heterogeneous corpora |
| US-2 | Benchmark creator | Run LLM-based MCQ generation on my chunks | I get candidate questions without manual authoring |
| US-3 | Benchmark creator | Review and filter generated items via CLI reports | I can remove ambiguous or low-quality items |
| US-4 | Benchmark creator | Label items by slice (A/B/C) and hop count | I can report fine-grained performance breakdowns |
| US-5 | Benchmark creator | Export a validated JSONL dataset | I can run End-to-End evals in my own harness |
| US-6 | Benchmark creator | Build frozen contexts with gold + distractor chunks | I can run Frozen Retrieval evals to isolate reasoning |
| US-7 | Benchmark creator | Add new documents to an existing corpus incrementally | I don't have to re-ingest the entire corpus when adding content |
| US-8 | Eval engineer | Compare my production agent vs pure RAG on the same dataset | I can measure the value of agentic orchestration |
| US-9 | Eval engineer | Re-run evals after architecture changes | I can measure regression or improvement |

## 4. Functional Requirements

### 4.1 Document Ingestion

| ID | Requirement |
|----|-------------|
| FR-1 | The system must accept input documents in: `.txt`, `.md`, `.pdf`, `.csv`, `.json`, `.html` formats. |
| FR-2 | The system must convert each document into the Canonical Document Representation (CDR): `doc_id`, `source_type`, `chunk_id`, `text`, and optional `page_ref`, `section_path`, `table_json`. |
| FR-3 | The system must support configurable chunking strategies (fixed token window, semantic paragraph, table-aware). |
| FR-4 | The system must output chunks as JSONL to `data/chunks/`. |
| FR-5 | The system must support incremental ingestion: detect new/modified documents and only process changes. |
| FR-6 | The system must maintain a corpus manifest tracking ingested doc_ids, checksums, and timestamps. |

### 4.2 MCQ Generation

| ID | Requirement |
|----|-------------|
| FR-7 | The system must generate MCQ items using Gemini API (`gemini-2.5-flash`), with each item containing: question text, four options (A–D), correct answer key, and gold evidence spans. |
| FR-8 | Gold evidence spans must reference `doc_id`, `chunk_id`, and character offsets or page refs. |
| FR-9 | Each generated item must include: `required_hops` (1, 2, or 3), `slice` (A, B, or C), `reasoning_type`, and at least one `failure_mode` label. |
| FR-10 | The system must use a stable QID format: `{doc_id}_{index}`. |
| FR-11 | The system must support seeded/deterministic generation for reproducibility. |
| FR-12 | The system must output generated items as JSONL to `data/generated/`. |

### 4.3 Validation

| ID | Requirement |
|----|-------------|
| FR-13 | The system must validate that each item has exactly one correct answer. |
| FR-14 | The system must flag items where MCQ distractors (wrong answer options) are too similar to the correct answer (ambiguity check). |
| FR-15 | The system must verify that gold evidence spans exist in the referenced chunks. |
| FR-16 | The system must produce a validation report with pass/fail counts and flagged item IDs. |
| FR-17 | The system must output validated items to `data/validated/` and rejected items to `data/rejected/`. |

### 4.4 Frozen Context Builder

| ID | Requirement |
|----|-------------|
| FR-18 | The system must generate frozen retrieval contexts for each MCQ item. |
| FR-19 | Frozen contexts must include the gold evidence chunks plus 10 context distractor chunks (irrelevant chunks that test filtering ability). |
| FR-20 | The system must support configuring distractor selection strategy (random, semantic similarity, same-doc). |
| FR-21 | The system must output frozen contexts as JSONL to `data/frozen_contexts/`. |

### 4.5 Export

| ID | Requirement |
|----|-------------|
| FR-22 | The system must export a core dataset JSONL (`dataset.jsonl`) with: QID, question, options, answer_key, gold_evidence, slice, required_hops, reasoning_type, failure_modes. |
| FR-23 | The system must export a frozen retrieval dataset JSONL (`dataset_frozen.jsonl`) that adds `frozen_context` (list of chunk_ids and their text) to each item. |
| FR-24 | The system must include a manifest file with corpus metadata, generation config, and item counts per slice. |

### 4.6 CLI Interface

| ID | Requirement |
|----|-------------|
| FR-25 | The system must provide CLI commands: `ingest`, `generate`, `validate`, `build-frozen`, `export`. |
| FR-26 | Each command must support `--config` for YAML/JSON configuration files. |
| FR-27 | Each command must support `--seed` for reproducibility. |
| FR-28 | The system must provide `--dry-run` mode for previewing operations. |
| FR-29 | The `ingest` command must support `--incremental` flag (default: true) to only process new/changed documents. |

## 5. Non-Goals (Out of Scope)

| ID | Exclusion |
|----|-----------|
| NG-1 | Built-in eval runner — users will run evals in their own harness. |
| NG-2 | Web UI or interactive annotation interface. |
| NG-3 | Real-time or streaming ingestion (batch only). |
| NG-4 | Multi-language support (English-only for v1). |
| NG-5 | Automatic corpus discovery or web crawling. |
| NG-6 | LLM-as-judge scoring (may be added later but not in v1). |
| NG-7 | Integration with existing eval harnesses (RAGAS, LangChain Evaluators, etc.) — this is a custom eval dataset. |

## 6. Technical Considerations

- **Language:** Python 3.11+
- **LLM Integration:** Gemini API (`gemini-2.5-flash`) via `google-generativeai` SDK.
- **Chunking:** Use `langchain` or `unstructured` for document parsing; custom chunker for tables.
- **Storage:** Local filesystem with JSONL; no database required for v1.
- **Config:** YAML config files in `configs/`.
- **Logging:** Structured JSON logs for pipeline runs.
- **Incremental Ingestion:** Use file checksums (SHA-256) to detect changes; store manifest in `data/corpus_manifest.json`.
- **Context Distractors:** Default 10 distractor chunks per frozen context.

## 7. Terminology

| Term | Definition |
|------|------------|
| MCQ distractor | A wrong answer option (A/B/C/D) that is plausible but incorrect. Tests comprehension vs. guessing. |
| Context distractor | An irrelevant chunk included in frozen context alongside gold evidence. Tests ability to find relevant info among noise. |
| Gold evidence | The chunk(s) containing the information needed to answer the question correctly. |
| Frozen context | A pre-determined set of chunks (gold + 10 distractors) provided to all systems in Frozen Retrieval mode. |
| Slice | Difficulty category: A (1-hop lookup), B (2-hop compositional), C (hard agentic). |

## 8. Success Metrics

| Metric | Target |
|--------|--------|
| Ingestion coverage | 95%+ of input docs successfully chunked (no parse failures) |
| Generation yield | ≥3 valid MCQ items per 10 chunks on average |
| Validation pass rate | ≥80% of generated items pass validation |
| Ambiguity rate | <5% of validated items flagged as ambiguous on human review |
| Reproducibility | Identical outputs for identical inputs + seed |
| Incremental efficiency | Re-ingestion of unchanged corpus completes in <10% of full ingestion time |
