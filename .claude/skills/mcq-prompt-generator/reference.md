# MCQ Prompt Generator Reference

## Prompt Template Structure

All prompts must be YAML files with the following structure:

```yaml
metadata:
  version: "1.0"
  target_slice: "A"  # A, B, or C
  reasoning_types: ["lookup", "definition"]
  doc_types: ["specification", "procedure"]
  created_date: "YYYY-MM-DD"

system: |
  <system prompt content>

user: |
  <user prompt template with {chunk_text} placeholder>

output_schema:
  type: object
  properties:
    question: { type: string }
    options:
      type: object
      properties:
        A: { type: string }
        B: { type: string }
        C: { type: string }
        D: { type: string }
    answer_key: { type: string, enum: ["A", "B", "C", "D"] }
    gold_evidence:
      type: array
      items:
        type: object
        properties:
          chunk_id: { type: string }
          text_span: { type: string }
          char_start: { type: integer }
          char_end: { type: integer }
    required_hops: { type: integer, enum: [1, 2, 3] }
    slice: { type: string, enum: ["A", "B", "C"] }
    reasoning_type: { type: string }
    failure_modes: { type: array, items: { type: string } }

examples:
  - input: |
      <example chunk text>
    output:
      question: "..."
      options: { A: "...", B: "...", C: "...", D: "..." }
      answer_key: "B"
      # ... rest of output
```

---

## Slice Definitions and Prompt Strategies

### Slice A: 1-Hop Lookup (Easy)
**Reasoning:** Direct fact retrieval from a single chunk.

**Target question types:**
- "What is the definition of X?"
- "Which parameter controls Y?"
- "What is the timer value for Z?"

**Prompt strategy:**
- Focus on explicit definitions, parameter values, acronym expansions
- Distractors should be plausible but clearly wrong (different parameters, wrong values)
- Evidence is always a single contiguous span

**Example (3GPP):**
```
Q: According to TS 38.331, what is the default value of t300 timer?
A) 100ms  B) 200ms  C) 400ms  D) 1000ms
Answer: D
Evidence: "t300: Timer started upon transmission of RRCSetupRequest... default 1000ms"
```

### Slice B: 2-Hop Compositional (Medium)
**Reasoning:** Requires combining information from 2 chunks or 2 parts of the same chunk.

**Target question types:**
- "If condition X is met, what procedure Y applies?"
- "Entity A sends message B to entity C. What is C's response?"
- "Parameter X is defined in section Y. What is its allowed range in context Z?"

**Prompt strategy:**
- Provide 2+ related chunks as input
- Question requires synthesizing both
- Distractors may be correct for one chunk but wrong when combined

**Example (ORAN):**
```
Q: When the Near-RT RIC receives an E2 Setup Request from an O-DU, and the O-DU's
   supported functions include E2SM-KPM, what response message is sent?
A) E2 Setup Failure with cause "Function not supported"
B) E2 Setup Response with RAN Function ID list
C) E2 Connection Update
D) RIC Subscription Request
Answer: B
Evidence: [Chunk 1: E2 Setup procedure] + [Chunk 2: E2SM-KPM function definition]
```

### Slice C: Hard Agentic (Difficult)
**Reasoning:** Exceptions, precedence rules, contradictions, table+prose joins, version-specific behavior.

**Target question types:**
- "If both X and Y apply, which takes precedence?"
- "The table specifies A, but the note says B under condition C. What is the correct behavior?"
- "Procedure X was deprecated in Release Y. What replaces it?"

**Prompt strategy:**
- Highlight exception clauses, notes, and conditional overrides
- Include version/release context when relevant
- Distractors should be "almost right" (correct for the general case but wrong for the exception)

**Example (3GPP):**
```
Q: Per TS 38.321, if the UE has pending data for transmission and receives a
   DRX command MAC CE, but the ongoing Random Access procedure is not yet complete,
   what is the UE's behavior?
A) Enter DRX immediately and abort RA
B) Complete RA procedure, then enter DRX
C) Ignore DRX command until RA completes, then restart drx-onDurationTimer
D) Enter DRX but continue RA in parallel
Answer: C
Evidence: "If a Random Access procedure is ongoing, the MAC entity shall ignore
           the DRX command... Upon completion, drx-onDurationTimer is started."
```

---

## Telecom Terminology Guidance

### 3GPP RAN Key Terms
| Acronym | Full Form | Context |
|---------|-----------|---------|
| UE | User Equipment | Mobile device |
| gNB | gNodeB | 5G NR base station |
| eNB | eNodeB | LTE base station |
| RRC | Radio Resource Control | Control plane protocol |
| NAS | Non-Access Stratum | Core network signaling |
| PDCP | Packet Data Convergence Protocol | Layer 2 protocol |
| RLC | Radio Link Control | Layer 2 protocol |
| MAC | Medium Access Control | Layer 2 protocol |
| PHY | Physical Layer | Layer 1 |
| SRB | Signaling Radio Bearer | Control plane bearer |
| DRB | Data Radio Bearer | User plane bearer |

### ORAN Key Terms
| Acronym | Full Form | Context |
|---------|-----------|---------|
| O-RU | O-RAN Radio Unit | Lower-layer split radio |
| O-DU | O-RAN Distributed Unit | Mid-layer processing |
| O-CU | O-RAN Centralized Unit | Upper-layer processing |
| SMO | Service Management & Orchestration | Management framework |
| Near-RT RIC | Near-Real-Time RAN Intelligent Controller | <10ms control loops |
| Non-RT RIC | Non-Real-Time RAN Intelligent Controller | >1s control loops |
| E2 | E2 Interface | RIC to O-DU/O-CU |
| O1 | O1 Interface | SMO to managed elements |
| A1 | A1 Interface | Non-RT RIC to Near-RT RIC |

---

## Reasoning Types

Use these labels in `reasoning_type` field:

| Type | Description |
|------|-------------|
| `lookup` | Direct fact retrieval |
| `definition` | Term/acronym definition |
| `parameter_value` | Specific config value |
| `procedure_step` | Step in a procedure |
| `cross_reference` | Info from multiple sources |
| `temporal_sequence` | Order of events/messages |
| `conditional_logic` | If-then-else behavior |
| `exception_handling` | Special case / override |
| `precedence_rule` | Priority when multiple rules apply |
| `table_prose_join` | Combining table + text |
| `version_specific` | Release-dependent behavior |

---

## Failure Mode Labels

Use these labels in `failure_modes` array:

| Mode | Description |
|------|-------------|
| `retrieval_miss` | Gold chunk not retrieved |
| `reasoning_miss` | Chunk retrieved but wrong conclusion |
| `term_confusion` | Similar terms conflated (e.g., SRB vs DRB) |
| `version_mismatch` | Wrong release assumed |
| `procedure_order` | Steps confused or skipped |
| `exception_ignored` | General rule applied, exception missed |
| `table_misread` | Table column/row mismatch |
| `benchmark_ambiguity` | Item itself is unclear (quality issue) |

---

## Distractor Quality Guidelines

Good distractors should be:
1. **Plausible** — A wrong answer that sounds reasonable
2. **Distinct** — Not too similar to correct answer (avoids ambiguity)
3. **Wrong for a reason** — Maps to a failure mode
4. **Consistent format** — Same grammatical structure as correct answer

Avoid:
- "None of the above" / "All of the above"
- Joke answers or obviously wrong options
- Distractors that are correct under different (unstated) conditions

---

## Evidence Span Extraction Rules

1. **Minimal span:** Include only text that directly supports the answer
2. **Context if needed:** May include surrounding sentence for clarity
3. **Multiple spans:** For 2+ hop, include one span per hop
4. **Exact offsets:** char_start and char_end must match the text_span exactly
5. **Page refs for PDFs:** Include page number when available

Example:
```json
{
  "chunk_id": "ts38331_sec10.2.1_chunk_42",
  "text_span": "t300: Timer started upon transmission of RRCSetupRequest. Value in ms. Default 1000.",
  "char_start": 1205,
  "char_end": 1289
}
```
