"""Gold evidence span extraction utilities."""

from src.models import CDRChunk, GoldEvidence


def find_span_in_chunk(text_span: str, chunk: CDRChunk) -> tuple[int, int] | None:
    """Find the exact character offsets of a text span within a chunk.

    Args:
        text_span: The text to find within the chunk.
        chunk: The CDRChunk to search in.

    Returns:
        Tuple of (start, end) character offsets, or None if not found.
    """
    # Normalize whitespace for matching
    normalized_span = " ".join(text_span.split())
    normalized_chunk = " ".join(chunk.text.split())

    # Try exact match first (case-sensitive)
    idx = chunk.text.find(text_span)
    if idx != -1:
        return idx, idx + len(text_span)

    # Try with normalized whitespace
    idx = normalized_chunk.find(normalized_span)
    if idx != -1:
        # Map normalized index back to original text
        return _map_normalized_index(chunk.text, normalized_span, idx)

    # Try case-insensitive match as fallback
    idx = chunk.text.lower().find(text_span.lower())
    if idx != -1:
        return idx, idx + len(text_span)

    return None


def _map_normalized_index(original: str, span: str, normalized_idx: int) -> tuple[int, int] | None:
    """Map an index from normalized text back to original text.

    Args:
        original: The original text with original whitespace.
        span: The span we're looking for.
        normalized_idx: Index in the normalized (whitespace-collapsed) text.

    Returns:
        Tuple of (start, end) in original text, or None if mapping fails.
    """
    # Walk through original text, tracking position in normalized text
    orig_idx = 0
    norm_idx = 0
    in_whitespace = False

    while orig_idx < len(original) and norm_idx < normalized_idx:
        if original[orig_idx].isspace():
            if not in_whitespace:
                norm_idx += 1
                in_whitespace = True
            orig_idx += 1
        else:
            norm_idx += 1
            orig_idx += 1
            in_whitespace = False

    start = orig_idx

    # Now find the end by matching the span
    span_idx = 0
    while orig_idx < len(original) and span_idx < len(span):
        if original[orig_idx].isspace() and span[span_idx].isspace():
            # Skip extra whitespace in original
            while orig_idx < len(original) and original[orig_idx].isspace():
                orig_idx += 1
            span_idx += 1
        elif original[orig_idx] == span[span_idx]:
            orig_idx += 1
            span_idx += 1
        else:
            # Mismatch - shouldn't happen if normalized match was correct
            return None

    return start, orig_idx


def extract_evidence_spans(
    text_spans: list[dict[str, str]],
    chunks: list[CDRChunk],
) -> list[GoldEvidence]:
    """Extract gold evidence spans from chunks based on LLM-provided text spans.

    Args:
        text_spans: List of dicts with 'chunk_id' and 'text_span' keys from LLM output.
        chunks: List of CDRChunks to search for evidence.

    Returns:
        List of GoldEvidence objects with calculated offsets.
    """
    chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
    evidence_list = []

    for span_info in text_spans:
        chunk_id = span_info.get("chunk_id", "")
        text_span = span_info.get("text_span", "")

        if not chunk_id or not text_span:
            continue

        chunk = chunk_map.get(chunk_id)
        if not chunk:
            # Chunk not found, create evidence without offsets
            evidence_list.append(
                GoldEvidence(
                    doc_id=chunk_id.rsplit("_", 1)[0] if "_" in chunk_id else chunk_id,
                    chunk_id=chunk_id,
                    char_start=None,
                    char_end=None,
                    page_ref=None,
                )
            )
            continue

        offsets = find_span_in_chunk(text_span, chunk)
        if offsets:
            char_start, char_end = offsets
        else:
            char_start, char_end = None, None

        evidence_list.append(
            GoldEvidence(
                doc_id=chunk.doc_id,
                chunk_id=chunk_id,
                char_start=char_start,
                char_end=char_end,
                page_ref=chunk.page_ref,
            )
        )

    return evidence_list


def validate_evidence_spans(
    evidence: list[GoldEvidence],
    chunks: list[CDRChunk],
) -> tuple[bool, list[str]]:
    """Validate that evidence spans exist in the referenced chunks.

    Args:
        evidence: List of GoldEvidence to validate.
        chunks: List of CDRChunks containing the source text.

    Returns:
        Tuple of (all_valid, list of error messages).
    """
    chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
    errors = []

    for ev in evidence:
        if ev.chunk_id not in chunk_map:
            errors.append(f"Evidence references non-existent chunk: {ev.chunk_id}")
            continue

        chunk = chunk_map[ev.chunk_id]

        if ev.char_start is not None and ev.char_end is not None:
            if ev.char_start < 0 or ev.char_end > len(chunk.text):
                errors.append(
                    f"Evidence span [{ev.char_start}:{ev.char_end}] out of bounds "
                    f"for chunk {ev.chunk_id} (length {len(chunk.text)})"
                )
            elif ev.char_start >= ev.char_end:
                errors.append(
                    f"Invalid evidence span: start ({ev.char_start}) >= end ({ev.char_end})"
                )

    return len(errors) == 0, errors


def get_evidence_text(evidence: GoldEvidence, chunks: list[CDRChunk]) -> str | None:
    """Get the actual text of an evidence span.

    Args:
        evidence: The GoldEvidence object.
        chunks: List of CDRChunks to search.

    Returns:
        The evidence text, or None if not found.
    """
    chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
    chunk = chunk_map.get(evidence.chunk_id)

    if not chunk:
        return None

    if evidence.char_start is not None and evidence.char_end is not None:
        return chunk.text[evidence.char_start : evidence.char_end]

    # If no offsets, return full chunk text as context
    return chunk.text
