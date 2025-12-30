"""Document preprocessor for RAG - cleans text before chunking.

Handles:
- Table of contents removal (consecutive dots, page numbers)
- Header/footer removal (repeated text across pages)
- Hyphenation repair (words split across lines)
- Whitespace normalization
- Boilerplate removal (copyright notices, document IDs)
"""

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PreprocessorConfig:
    """Configuration for document preprocessing."""

    remove_toc: bool = True
    remove_headers_footers: bool = True
    repair_hyphenation: bool = True
    remove_page_numbers: bool = True
    remove_boilerplate: bool = True
    normalize_whitespace: bool = True
    min_line_length: int = 10  # Lines shorter than this may be headers/footers
    custom_patterns: list[str] = field(default_factory=list)


class DocumentPreprocessor:
    """Clean and normalize document text for better chunking."""

    def __init__(self, config: PreprocessorConfig | None = None):
        """Initialize preprocessor with configuration.

        Args:
            config: Preprocessing configuration. Uses defaults if None.
        """
        self.config = config or PreprocessorConfig()
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        # Table of contents patterns (dots followed by page number)
        self.toc_patterns = [
            # "Chapter 1 .......... 5" or "1.1 Introduction.....10"
            # Match lines with 3+ consecutive dots (periods) followed by optional page number
            re.compile(r'^.*?\.{3,}.*$', re.MULTILINE),
            # Section headers followed by dots and page numbers (e.g., "Foreword ... 3")
            re.compile(r'^[A-Za-z][\w\s()]+\.{2,}\s*\d+\s*$', re.MULTILINE),
            # Tab-separated TOC entries: "1.1 Introduction\t5"
            re.compile(r'^\d+[\d.]*\s+[A-Za-z][^\n]*\t\d+\s*$', re.MULTILINE),
            # Numbered section followed by title and page (e.g., "2. References .... 4")
            re.compile(r'^\d+[\d.]*\.?\s+[A-Za-z].*?\.{2,}\s*\d+\s*$', re.MULTILINE),
            # Lines that are mostly dots (common in PDF-extracted TOC)
            re.compile(r'^[^.]*\.{10,}[^.]*$', re.MULTILINE),
            # "Contents" header line
            re.compile(r'^Contents\s*$', re.MULTILINE | re.IGNORECASE),
            # TOC remnants: lines with only section numbers like "2 2.1 2.2" or "7 7.1 7.1.1"
            # These are left over after dots are removed
            re.compile(r'^[\d.\s]+$', re.MULTILINE),
            # Lines with Annex references that are TOC-like (e.g., "Annex A (normative)")
            re.compile(r'^Annex\s+[A-Z]\s*\([^)]+\).*$', re.MULTILINE),
        ]

        # Page number patterns
        self.page_number_patterns = [
            # Standalone page numbers
            re.compile(r'^\s*\d+\s*$', re.MULTILINE),
            # "Page X of Y" or "Page X"
            re.compile(r'^[Pp]age\s+\d+(\s+of\s+\d+)?\s*$', re.MULTILINE),
            # "- X -" centered page numbers
            re.compile(r'^\s*[-–—]\s*\d+\s*[-–—]\s*$', re.MULTILINE),
            # Underscore separator lines with optional page number (footer separators)
            re.compile(r'^[_\s]+\d*\s*$', re.MULTILINE),
            # Lines that are mostly underscores (horizontal rules/separators)
            re.compile(r'^_{5,}.*$', re.MULTILINE),
        ]

        # Boilerplate patterns
        self.boilerplate_patterns = [
            # Copyright notices (with "Copyright" prefix or just ©)
            re.compile(r'Copyright\s*©\s*\d{4}[^\n]*', re.IGNORECASE),
            re.compile(r'©\s*\d{4}[^\n]*', re.IGNORECASE),
            # O-RAN Document IDs - full line (e.g., O-RAN.WG10.TS.TE&IV-DM.0-R004-v02.00)
            re.compile(r'^O-RAN\.[A-Z0-9.&-]+[-v]\d+\.\d+\s*$', re.MULTILINE | re.IGNORECASE),
            # O-RAN Document IDs with text after (e.g., "O-RAN.WG1.CCIN-R004-v01.00 Technical Report")
            re.compile(r'^O-RAN\.[A-Z0-9.&-]+[-v]\d+\.\d+\s+.*$', re.MULTILINE | re.IGNORECASE),
            # O-RAN ALLIANCE address/registration info
            re.compile(r'^O-RAN ALLIANCE e\.V\..*$', re.MULTILINE),
            re.compile(r'^Register of Associations.*$', re.MULTILINE),
            # O-RAN Work Group headers (e.g., "O-RAN Work Group 10 (OAM for O-RAN)")
            re.compile(r'^O-RAN Work Group \d+\s*\([^)]+\)\s*$', re.MULTILINE),
            # 3GPP document IDs
            re.compile(r'^3GPP\s+T[RS]\s+[\d.]+.*$', re.MULTILINE),
            # "Your use is subject to..." disclaimers
            re.compile(r'Your use is subject to.*?specification\.', re.IGNORECASE | re.DOTALL),
            # Long copyright disclaimer paragraphs (O-RAN style)
            re.compile(
                r'The copying or incorporation into any other work.*?must comply with them\.',
                re.IGNORECASE | re.DOTALL
            ),
            # "Technical Specification" or "Technical Report" header lines
            re.compile(r'^Technical (Specification|Report)\s*$', re.MULTILINE),
            # Modal verbs terminology boilerplate
            re.compile(r'^Modal verbs terminology\s*$', re.MULTILINE | re.IGNORECASE),
            # Foreword/Executive summary headers (often boilerplate sections)
            re.compile(r'^Foreword\s*$', re.MULTILINE),
            re.compile(r'^Executive summary\s*$', re.MULTILINE | re.IGNORECASE),
            # Document titles that are just the technology name (often on cover pages)
            re.compile(r'^Communication and Computing Integrated Networks\s*$', re.MULTILINE),
            re.compile(r'^Topology Exposure and Inventory Data Model.*$', re.MULTILINE),
        ]

        # Header/footer detection (short repeated lines)
        self.header_footer_patterns = [
            # Common header patterns
            re.compile(r'^(CONFIDENTIAL|DRAFT|INTERNAL|PUBLIC)\s*$', re.MULTILINE | re.IGNORECASE),
            # Version/revision headers
            re.compile(r'^[Vv]ersion\s+[\d.]+\s*$', re.MULTILINE),
            re.compile(r'^[Rr]evision\s+[\d.]+\s*$', re.MULTILINE),
        ]

        # Hyphenation pattern (word-hyphen at end of line)
        self.hyphen_pattern = re.compile(r'(\w+)-\n(\w+)')

        # Compile custom patterns
        self.custom_compiled = [
            re.compile(p) for p in self.config.custom_patterns
        ]

    def preprocess(self, text: str, page_texts: list[str] | None = None) -> str:
        """Preprocess document text for chunking.

        Args:
            text: Full document text.
            page_texts: Optional per-page text for header/footer detection.

        Returns:
            Cleaned text ready for chunking.
        """
        if not text:
            return text

        # Apply preprocessing steps in order
        if self.config.remove_toc:
            text = self._remove_toc(text)

        if self.config.remove_boilerplate:
            text = self._remove_boilerplate(text)

        if self.config.remove_headers_footers and page_texts:
            text = self._remove_headers_footers(text, page_texts)

        if self.config.remove_page_numbers:
            text = self._remove_page_numbers(text)

        if self.config.repair_hyphenation:
            text = self._repair_hyphenation(text)

        if self.config.normalize_whitespace:
            text = self._normalize_whitespace(text)

        # Apply custom patterns
        for pattern in self.custom_compiled:
            text = pattern.sub('', text)

        return text.strip()

    def _remove_toc(self, text: str) -> str:
        """Remove table of contents entries.

        Args:
            text: Input text.

        Returns:
            Text with TOC entries removed.
        """
        for pattern in self.toc_patterns:
            text = pattern.sub('', text)
        return text

    def _remove_page_numbers(self, text: str) -> str:
        """Remove standalone page numbers.

        Args:
            text: Input text.

        Returns:
            Text with page numbers removed.
        """
        for pattern in self.page_number_patterns:
            text = pattern.sub('', text)
        return text

    def _remove_boilerplate(self, text: str) -> str:
        """Remove boilerplate text like copyright notices.

        Args:
            text: Input text.

        Returns:
            Text with boilerplate removed.
        """
        for pattern in self.boilerplate_patterns:
            text = pattern.sub('', text)
        return text

    def _remove_headers_footers(self, text: str, page_texts: list[str]) -> str:
        """Remove repeated headers and footers.

        Detects text that appears at similar positions across multiple pages.

        Args:
            text: Full document text.
            page_texts: Per-page text list.

        Returns:
            Text with headers/footers removed.
        """
        if len(page_texts) < 3:
            return text  # Need at least 3 pages to detect patterns

        # Extract potential headers (first few lines of each page)
        # and footers (last few lines of each page)
        potential_headers: dict[str, int] = {}
        potential_footers: dict[str, int] = {}

        for page_text in page_texts:
            lines = page_text.strip().split('\n')

            # Check first 3 lines for headers
            for line in lines[:3]:
                line = line.strip()
                if line and len(line) < 100:  # Headers are typically short
                    potential_headers[line] = potential_headers.get(line, 0) + 1

            # Check last 3 lines for footers
            for line in lines[-3:]:
                line = line.strip()
                if line and len(line) < 100:
                    potential_footers[line] = potential_footers.get(line, 0) + 1

        # Lines appearing on more than half the pages are likely headers/footers
        threshold = len(page_texts) // 2

        headers_to_remove = {
            line for line, count in potential_headers.items()
            if count >= threshold
        }
        footers_to_remove = {
            line for line, count in potential_footers.items()
            if count >= threshold
        }

        # Remove identified headers/footers
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped not in headers_to_remove and stripped not in footers_to_remove:
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _repair_hyphenation(self, text: str) -> str:
        """Repair words split across lines with hyphens.

        Args:
            text: Input text.

        Returns:
            Text with hyphenated words rejoined.
        """
        # Join "word-\nword" into "wordword" (removing hyphen and newline)
        # But preserve legitimate hyphens (e.g., "well-known")
        def replace_hyphen(match: re.Match) -> str:
            word1 = match.group(1)
            word2 = match.group(2)
            # If second part starts with lowercase, likely a broken word
            if word2[0].islower():
                return word1 + word2
            # Otherwise keep the hyphen (might be intentional)
            return match.group(0)

        return self.hyphen_pattern.sub(replace_hyphen, text)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        - Collapse multiple spaces to single space
        - Collapse 3+ newlines to double newline
        - Remove trailing whitespace from lines

        Args:
            text: Input text.

        Returns:
            Text with normalized whitespace.
        """
        # Remove trailing whitespace from each line
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Collapse multiple spaces (but not newlines)
        text = re.sub(r'[ \t]+', ' ', text)

        # Collapse 3+ newlines to 2 (preserve paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text


def get_preprocessor(
    remove_toc: bool = True,
    remove_headers_footers: bool = True,
    repair_hyphenation: bool = True,
    custom_patterns: list[str] | None = None,
) -> DocumentPreprocessor:
    """Factory function to create a configured preprocessor.

    Args:
        remove_toc: Whether to remove table of contents.
        remove_headers_footers: Whether to remove repeated headers/footers.
        repair_hyphenation: Whether to repair hyphenated words.
        custom_patterns: Additional regex patterns to remove.

    Returns:
        Configured DocumentPreprocessor instance.
    """
    config = PreprocessorConfig(
        remove_toc=remove_toc,
        remove_headers_footers=remove_headers_footers,
        repair_hyphenation=repair_hyphenation,
        custom_patterns=custom_patterns or [],
    )
    return DocumentPreprocessor(config)
