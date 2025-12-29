"""Document parsers for various file formats."""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pdfplumber
from bs4 import BeautifulSoup

from src.models import SourceType


class ParseResult:
    """Result from parsing a document."""

    def __init__(
        self,
        text: str,
        page_texts: list[str] | None = None,
        tables: list[dict[str, Any]] | None = None,
    ):
        """Initialize parse result.

        Args:
            text: Full extracted text.
            page_texts: Optional per-page text list (for PDFs).
            tables: Optional list of extracted tables as dicts.
        """
        self.text = text
        self.page_texts = page_texts
        self.tables = tables or []


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse a document and extract text.

        Args:
            file_path: Path to the document file.

        Returns:
            ParseResult containing extracted text and metadata.
        """
        pass


class TextParser(BaseParser):
    """Parser for plain text and markdown files."""

    def parse(self, file_path: Path) -> ParseResult:
        """Parse a text or markdown file.

        Args:
            file_path: Path to the .txt or .md file.

        Returns:
            ParseResult with file contents.
        """
        text = file_path.read_text(encoding="utf-8")
        return ParseResult(text=text)


class PDFParser(BaseParser):
    """Parser for PDF documents with page reference preservation."""

    def parse(self, file_path: Path) -> ParseResult:
        """Parse a PDF file, extracting text and tables.

        Args:
            file_path: Path to the .pdf file.

        Returns:
            ParseResult with text, per-page text, and tables.
        """
        page_texts: list[str] = []
        tables: list[dict[str, Any]] = []

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract text
                page_text = page.extract_text() or ""
                page_texts.append(page_text)

                # Extract tables
                for table_data in page.extract_tables():
                    if table_data:
                        tables.append({
                            "page": page_num,
                            "data": table_data,
                        })

        full_text = "\n\n".join(page_texts)
        return ParseResult(text=full_text, page_texts=page_texts, tables=tables)


class CSVParser(BaseParser):
    """Parser for CSV files with table structure preservation."""

    def parse(self, file_path: Path) -> ParseResult:
        """Parse a CSV file.

        Args:
            file_path: Path to the .csv file.

        Returns:
            ParseResult with text representation and table data.
        """
        rows: list[list[str]] = []

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Convert to text representation
        text_lines = []
        for row in rows:
            text_lines.append(" | ".join(row))

        # Store as table structure
        tables = [{
            "data": rows,
            "headers": rows[0] if rows else [],
        }]

        return ParseResult(text="\n".join(text_lines), tables=tables)


class JSONParser(BaseParser):
    """Parser for JSON files."""

    def parse(self, file_path: Path) -> ParseResult:
        """Parse a JSON file.

        Args:
            file_path: Path to the .json file.

        Returns:
            ParseResult with flattened text representation.
        """
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        text = self._flatten_json(data)
        return ParseResult(text=text)

    def _flatten_json(self, obj: Any, prefix: str = "") -> str:
        """Recursively flatten JSON to readable text.

        Args:
            obj: JSON object (dict, list, or scalar).
            prefix: Key path prefix for nested values.

        Returns:
            Flattened text representation.
        """
        lines = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                lines.append(self._flatten_json(value, new_prefix))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_prefix = f"{prefix}[{i}]"
                lines.append(self._flatten_json(item, new_prefix))
        else:
            lines.append(f"{prefix}: {obj}")

        return "\n".join(filter(None, lines))


class HTMLParser(BaseParser):
    """Parser for HTML files."""

    def parse(self, file_path: Path) -> ParseResult:
        """Parse an HTML file, stripping tags.

        Args:
            file_path: Path to the .html file.

        Returns:
            ParseResult with extracted text content.
        """
        html_content = file_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "meta", "link"]):
            element.decompose()

        # Get text with whitespace normalization
        text = soup.get_text(separator="\n", strip=True)

        # Extract tables
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append({"data": rows})

        return ParseResult(text=text, tables=tables)


# Parser registry
_PARSERS: dict[SourceType, type[BaseParser]] = {
    SourceType.TXT: TextParser,
    SourceType.MD: TextParser,
    SourceType.PDF: PDFParser,
    SourceType.CSV: CSVParser,
    SourceType.JSON: JSONParser,
    SourceType.HTML: HTMLParser,
}


def get_parser(file_path: Path) -> BaseParser:
    """Get appropriate parser for a file.

    Args:
        file_path: Path to the document.

    Returns:
        Parser instance for the file type.

    Raises:
        ValueError: If file type is not supported.
    """
    extension = file_path.suffix.lower().lstrip(".")
    try:
        source_type = SourceType(extension)
    except ValueError:
        supported = ", ".join(st.value for st in SourceType)
        raise ValueError(
            f"Unsupported file type: {file_path.suffix}. Supported: {supported}"
        )

    parser_class = _PARSERS[source_type]
    return parser_class()
