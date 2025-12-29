"""Pytest fixtures and shared test utilities."""

import tempfile
from pathlib import Path

import pytest

from src.models import (
    CDRChunk,
    FailureMode,
    GoldEvidence,
    MCQItem,
    ReasoningType,
    Slice,
    SourceType,
)


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_chunk() -> CDRChunk:
    """Provide a sample CDR chunk for testing."""
    return CDRChunk(
        doc_id="doc_abc123",
        source_type=SourceType.TXT,
        chunk_id="doc_abc123_0",
        text="The 3GPP Release 18 specification defines the maximum UE transmit power as 23 dBm for FR1 bands.",
        page_ref=None,
        section_path="3.1.2",
        table_json=None,
    )


@pytest.fixture
def sample_chunks() -> list[CDRChunk]:
    """Provide multiple sample chunks for testing."""
    return [
        CDRChunk(
            doc_id="doc_abc123",
            source_type=SourceType.TXT,
            chunk_id="doc_abc123_0",
            text="The 3GPP Release 18 specification defines the maximum UE transmit power as 23 dBm for FR1 bands.",
        ),
        CDRChunk(
            doc_id="doc_abc123",
            source_type=SourceType.TXT,
            chunk_id="doc_abc123_1",
            text="For FR2 bands, the maximum transmit power is reduced to 22 dBm due to thermal constraints.",
        ),
        CDRChunk(
            doc_id="doc_def456",
            source_type=SourceType.PDF,
            chunk_id="doc_def456_0",
            text="O-RAN fronthaul interface uses eCPRI protocol for communication between O-DU and O-RU.",
            page_ref=42,
        ),
    ]


@pytest.fixture
def sample_mcq_item() -> MCQItem:
    """Provide a sample MCQ item for testing."""
    return MCQItem(
        qid="doc_abc123_q1",
        question="What is the maximum UE transmit power for FR1 bands according to 3GPP Release 18?",
        options={
            "A": "20 dBm",
            "B": "23 dBm",
            "C": "26 dBm",
            "D": "30 dBm",
        },
        answer_key="B",
        gold_evidence=[
            GoldEvidence(
                doc_id="doc_abc123",
                chunk_id="doc_abc123_0",
                char_start=45,
                char_end=51,
            )
        ],
        slice=Slice.A,
        required_hops=1,
        reasoning_type=ReasoningType.FACTUAL_LOOKUP,
        failure_modes=[FailureMode.RETRIEVAL_MISS],
    )


@pytest.fixture
def sample_text_file(temp_dir: Path) -> Path:
    """Create a sample text file for testing."""
    file_path = temp_dir / "sample.txt"
    file_path.write_text(
        "This is a sample document for testing.\n"
        "It contains multiple paragraphs.\n\n"
        "The second paragraph has more content.\n"
        "This helps test chunking behavior."
    )
    return file_path
