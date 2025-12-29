# Progress Log: RAG Benchmark Curation System

## Approach

Building a universal benchmark curation system that converts arbitrary input documents (3GPP RAN, ORAN specs) into an MCQ evaluation dataset. The dataset will be used to:
1. Compare production-grade agentic RAG vs pure RAG systems
2. Evaluate impact of architecture changes on agent performance
3. Isolate reasoning quality from retrieval quality via Frozen Retrieval mode

**Key architectural decisions:**
- CLI-based batch pipeline (no web UI)
- Gemini API (`gemini-2.5-flash`) for MCQ generation
- Two evaluation modes: End-to-End and Frozen Retrieval
- 10 context distractor chunks per frozen context
- Custom eval dataset (no integration with RAGAS/LangChain Evaluators)

## Steps Completed

### 1. Repository Setup
- [x] Created initial `CLAUDE.md` (user enhanced with project details, ADR constraints, repo conventions)
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

### 3. New Skill Created: `mcq-prompt-generator`
- [x] Created `.claude/skills/mcq-prompt-generator/SKILL.md`
- [x] Created `.claude/skills/mcq-prompt-generator/reference.md` with:
  - YAML prompt template structure
  - Slice-specific strategies (A: 1-hop, B: 2-hop, C: hard agentic)
  - 3GPP RAN terminology table
  - ORAN terminology table
  - Reasoning type labels
  - Failure mode labels
  - Distractor quality guidelines
  - Evidence span extraction rules

## Current Status

**No failures.** PRD and task list are complete.

### 4. Implementation Task List Generated
- [x] Created `tasks/tasks-rag-benchmark-curation.md` with 6 parent tasks and ~50 sub-tasks
- [x] Defined relevant files: 30+ source files, tests, and configs
- [x] Task breakdown covers: project setup, ingestion, generation, validation, frozen context, export/CLI

## Current Files

```
.claude/
├── rules/
│   └── adr-0001-summary.md
└── skills/
    ├── create-prd/
    │   ├── SKILL.md
    │   └── reference.md
    ├── generate-tasks/
    │   ├── SKILL.md
    │   └── reference.md
    └── mcq-prompt-generator/
        ├── SKILL.md
        └── reference.md

tasks/
├── prd-rag-benchmark-curation.md
└── tasks-rag-benchmark-curation.md   <-- NEW
```

## Next Steps

1. **Start implementation** — Begin with Task 1.0 (project structure and dependencies)
2. **Design MCQ prompts** — Use `mcq-prompt-generator` skill to create Gemini prompt templates for each slice (A/B/C)
3. **Implement ingestion pipeline** — Task 2.0 (document parsing and CDR conversion)
