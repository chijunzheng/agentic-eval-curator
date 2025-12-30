# RAG Document Chunking Skill

Use this skill to chunk documents for RAG pipelines using **unstructured.io** for intelligent semantic and table-aware chunking.

## When to Use

- When preparing documents for vector embeddings
- When dealing with technical documents containing tables
- When you need semantic chunking that preserves document structure
- When documents have mixed prose and structured content (tables, lists, headers)

## Prerequisites

Install the unstructured library with document support:

```bash
pip install "unstructured[all-docs]"
```

For PDF support specifically:
```bash
pip install "unstructured[pdf]"
```

## Chunking with Unstructured.io

### Basic Usage

```python
from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title

# Partition document into semantic elements
elements = partition(filename="document.pdf")

# Chunk by title/section boundaries (recommended)
chunks = chunk_by_title(
    elements,
    max_characters=1500,           # Hard max size
    new_after_n_chars=1000,        # Soft target size
    combine_text_under_n_chars=200, # Merge small sections
    overlap=100,                    # Overlap for text-splitting
)

for chunk in chunks:
    print(f"Type: {type(chunk).__name__}")
    print(f"Text: {chunk.text[:100]}...")
    print(f"Metadata: {chunk.metadata}")
```

### Table Handling

Unstructured.io handles tables intelligently:
- **Tables are always isolated** - never combined with other elements
- Each table becomes its own chunk
- Table structure is preserved in `metadata.text_as_html`

```python
from unstructured.documents.elements import Table

for chunk in chunks:
    if isinstance(chunk, Table):
        print("Table chunk:")
        print(chunk.metadata.text_as_html)  # HTML representation
    else:
        print("Text chunk:")
        print(chunk.text)
```

### Chunking Strategies

#### 1. `by_title` (Recommended for technical docs)
Preserves section boundaries based on document structure:

```python
from unstructured.chunking.title import chunk_by_title

chunks = chunk_by_title(
    elements,
    max_characters=1500,
    new_after_n_chars=1000,
    multipage_sections=True,  # Allow sections across pages
)
```

#### 2. `basic`
Simple sequential chunking without section awareness:

```python
from unstructured.chunking.basic import chunk_elements

chunks = chunk_elements(
    elements,
    max_characters=1500,
    new_after_n_chars=1000,
)
```

### During Partitioning

Apply chunking directly when partitioning:

```python
from unstructured.partition.pdf import partition_pdf

chunks = partition_pdf(
    filename="document.pdf",
    chunking_strategy="by_title",
    max_characters=1500,
    new_after_n_chars=1000,
)
```

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_characters` | 500 | Hard maximum chunk size |
| `new_after_n_chars` | max_characters | Soft target size |
| `overlap` | 0 | Character overlap between chunks |
| `combine_text_under_n_chars` | 0 | Merge sections smaller than this |
| `multipage_sections` | True | Allow sections to span pages |

## Integration with Project

### Update pyproject.toml

```toml
[project.optional-dependencies]
unstructured = [
    "unstructured[all-docs]>=0.16.0",
]
```

### Creating an Unstructured-based Chunker

```python
# src/ingest/unstructured_chunker.py
from pathlib import Path
from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import Table

from src.ingest.chunker import BaseChunker, ChunkMetadata
from src.ingest.parsers import ParseResult


class UnstructuredChunker(BaseChunker):
    """Chunker using unstructured.io for semantic chunking."""

    def __init__(
        self,
        max_characters: int = 1500,
        new_after_n_chars: int = 1000,
        combine_text_under_n_chars: int = 200,
        overlap: int = 100,
    ):
        self.max_characters = max_characters
        self.new_after_n_chars = new_after_n_chars
        self.combine_text_under_n_chars = combine_text_under_n_chars
        self.overlap = overlap

    def chunk_file(self, file_path: Path) -> list[ChunkMetadata]:
        """Chunk directly from file using unstructured."""
        elements = partition(filename=str(file_path))
        chunks = chunk_by_title(
            elements,
            max_characters=self.max_characters,
            new_after_n_chars=self.new_after_n_chars,
            combine_text_under_n_chars=self.combine_text_under_n_chars,
            overlap=self.overlap,
        )

        result = []
        for chunk in chunks:
            is_table = isinstance(chunk, Table)
            metadata = ChunkMetadata(
                text=chunk.text,
                page_ref=chunk.metadata.page_number,
                table_json=chunk.metadata.text_as_html if is_table else None,
            )
            result.append(metadata)

        return result

    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Fallback for pre-parsed text (less accurate)."""
        # For pre-parsed text, fall back to sentence-aware chunking
        from src.ingest.chunker import SentenceTableAwareChunker
        fallback = SentenceTableAwareChunker(
            min_chunk_size=self.combine_text_under_n_chars,
            max_chunk_size=self.max_characters,
        )
        return fallback.chunk(parse_result)
```

## Benefits of Unstructured.io

1. **Document-aware partitioning** - Understands document structure (headers, paragraphs, lists, tables)
2. **Table isolation** - Tables are never split or merged with prose
3. **Section preservation** - `by_title` keeps sections together
4. **Multi-format support** - PDF, DOCX, HTML, PPTX, and 25+ formats
5. **Metadata extraction** - Page numbers, coordinates, section hierarchy

## Testing

```bash
# Install with unstructured support
pip install -e ".[unstructured]"

# Test chunking
python -c "
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title

elements = partition_pdf('test.pdf')
chunks = chunk_by_title(elements, max_characters=1500)
for c in chunks[:3]:
    print(f'{type(c).__name__}: {c.text[:80]}...')
"
```

## Sources

- [Unstructured Chunking Documentation](https://docs.unstructured.io/open-source/core-functionality/chunking)
- [Unstructured GitHub](https://github.com/Unstructured-IO/unstructured)
- [Chunking Strategies API Reference](https://docs.unstructured.io/api-reference/api-services/chunking)
