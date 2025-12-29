---
name: mcq-prompt-generator
description: Generate and refine LLM prompts/templates for MCQ item generation from telecom specification documents (3GPP RAN, ORAN). Outputs reusable prompt templates for the curation pipeline.
---

# MCQ Prompt Generator

## When to use
Use this Skill when you need to:
- Create new MCQ generation prompts for 3GPP or ORAN document corpora
- Refine existing prompts based on quality feedback
- Generate slice-specific prompts (A: 1-hop, B: 2-hop, C: hard agentic)
- Adapt prompts for specific document types (specs, procedures, tables)

## Domain Context

### 3GPP RAN Documents
- Technical specifications for radio access networks (TS 38.xxx, TS 36.xxx series)
- Contains: procedures, message flows, parameter definitions, state machines
- Common entities: UE, gNB, eNB, RRC, NAS, PDCP, RLC, MAC, PHY

### ORAN Documents
- O-RAN Alliance specifications for open radio access networks
- Contains: interface definitions (O1, O2, A1, E2), functional splits, use cases
- Common entities: O-RU, O-DU, O-CU, SMO, Near-RT RIC, Non-RT RIC

## Instructions

1) **Gather requirements:**
   - Which slice(s)? (A, B, C, or all)
   - Which document types? (procedures, definitions, tables, message flows)
   - Any specific reasoning types to target? (lookup, cross-reference, temporal, conditional, exception handling)

2) **Generate prompt template(s)** following the structure in [reference.md](reference.md):
   - System prompt with domain context
   - User prompt with chunk input format
   - Output schema (JSON) matching ADR-0001 requirements
   - Few-shot examples for the target slice

3) **Include quality guardrails:**
   - Instructions to avoid ambiguous distractors
   - Rules for evidence span extraction
   - Hop-count verification guidance

4) **Output:**
   - Save prompts to `configs/prompts/mcq-{slice}-{doc_type}.yaml`
   - Include metadata: version, target_slice, reasoning_types, created_date

## Output Contract

- Prompts are YAML files with `system`, `user`, `output_schema`, and `examples` keys
- Each prompt clearly specifies the target slice and reasoning type
- Prompts include telecom-specific terminology guidance
- Examples demonstrate correct evidence span formatting
