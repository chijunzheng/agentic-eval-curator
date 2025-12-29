# ADR-0001 Summary (RAG Benchmark)

- Benchmark items are MCQ (A–D) with single correct answer + answer key.
- Every item must include gold evidence spans (chunk ids + offsets/page refs).
- Support two evaluation modes:
  1) Frozen Retrieval (reasoning-only): identical retrieved chunks for naive vs agentic
  2) End-to-End: each system can retrieve normally
- Label items by slice:
  - Slice A: 1-hop lookup
  - Slice B: 2-hop compositional
  - Slice C: hard agentic (exceptions, precedence, contradictions, table+prose joins)
- Headline metric is deterministic MCQ accuracy. LLM-as-judge is optional and must not change the main score.
