# RAG Document Preprocessing Skill

Use this skill to clean and preprocess documents for RAG (Retrieval Augmented Generation) pipelines.

## When to Use

- Before chunking documents for vector storage
- When dealing with PDF-extracted text that has artifacts
- When documents contain TOC, headers, footers, or boilerplate text
- When text has line-wrapped paragraphs or hyphenated words split across lines

## Preprocessing Capabilities

The `DocumentPreprocessor` class in `src/ingest/preprocessor.py` provides:

1. **TOC Removal** - Removes table of contents entries with:
   - Consecutive dots (e.g., "Introduction .......... 5")
   - Tab-separated page numbers (e.g., "1.1 Overview\t10")

2. **Header/Footer Removal** - Detects and removes repeated text across pages

3. **Page Number Removal** - Removes standalone page numbers and "Page X of Y" patterns

4. **Boilerplate Removal** - Removes copyright notices, disclaimers, document IDs

5. **Hyphenation Repair** - Joins words split across lines (e.g., "exam-\nple" → "example")

6. **Whitespace Normalization** - Collapses multiple spaces and excessive blank lines

7. **Custom Patterns** - Add regex patterns for domain-specific cleanup

## Usage

### Python API

```python
from src.ingest.preprocessor import DocumentPreprocessor, PreprocessorConfig, get_preprocessor

# Quick start with defaults
preprocessor = get_preprocessor()
cleaned_text = preprocessor.preprocess(raw_text)

# With page-aware header/footer removal
cleaned_text = preprocessor.preprocess(raw_text, page_texts=list_of_page_texts)

# Custom configuration
config = PreprocessorConfig(
    remove_toc=True,
    remove_headers_footers=True,
    repair_hyphenation=True,
    remove_page_numbers=True,
    remove_boilerplate=True,
    normalize_whitespace=True,
    custom_patterns=[
        r'\[DRAFT\]',
        r'CONFIDENTIAL',
    ]
)
preprocessor = DocumentPreprocessor(config)
cleaned_text = preprocessor.preprocess(raw_text, page_texts=page_texts)
```

### CLI (via Ingest Pipeline)

Preprocessing is automatically applied during ingestion:

```bash
rag-bench ingest --input-dir /path/to/documents/
```

The pipeline uses the `sentence_table_aware` chunking strategy by default, which includes preprocessing.

## Configuration

Edit `configs/default.yaml` to customize preprocessing behavior (preprocessing is enabled by default in the pipeline).

## Testing

```bash
pytest tests/test_preprocessor.py -v
```

## Implementation Details

- Location: `src/ingest/preprocessor.py`
- Integrated into: `src/ingest/pipeline.py`
- Tests: `tests/test_preprocessor.py`
