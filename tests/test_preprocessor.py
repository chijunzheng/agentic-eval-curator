"""Unit tests for document preprocessor."""

import pytest

from src.ingest.preprocessor import (
    DocumentPreprocessor,
    PreprocessorConfig,
    get_preprocessor,
)


class TestDocumentPreprocessor:
    """Tests for DocumentPreprocessor."""

    def test_removes_toc_with_dots(self):
        """Test removal of TOC entries with dots."""
        text = """Introduction
1. Overview .............. 5
2. Background ............ 10
3. Methods ............... 15

This is the actual content."""

        config = PreprocessorConfig(remove_toc=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        assert "1. Overview" not in result
        assert "This is the actual content" in result

    def test_removes_toc_with_tabs(self):
        """Test removal of TOC entries with tabs."""
        text = """1.1 Introduction\t5
1.2 Background\t10

This is the actual content."""

        config = PreprocessorConfig(remove_toc=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        assert "1.1 Introduction\t5" not in result
        assert "This is the actual content" in result

    def test_removes_page_numbers(self):
        """Test removal of standalone page numbers."""
        text = """Some content here.

5

More content here.

Page 10 of 20

Even more content."""

        config = PreprocessorConfig(remove_page_numbers=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        # Standalone "5" should be removed
        assert "\n5\n" not in result
        assert "Page 10 of 20" not in result
        assert "Some content here" in result

    def test_removes_boilerplate(self):
        """Test removal of copyright and boilerplate text."""
        text = """© 2025 by the O-RAN ALLIANCE e.V. Your use is subject to the copyright statement on the cover page of this specification.

This is the actual content.

O-RAN.WG10.TS.Information Model.v1.00"""

        config = PreprocessorConfig(remove_boilerplate=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        assert "O-RAN ALLIANCE" not in result
        assert "Your use is subject to" not in result
        assert "This is the actual content" in result

    def test_repairs_hyphenation(self):
        """Test repair of hyphenated words split across lines."""
        text = """This is an exam-
ple of hyphen-
ated text that should be
joined properly."""

        config = PreprocessorConfig(repair_hyphenation=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        assert "example" in result
        assert "hyphenated" in result

    def test_preserves_intentional_hyphens(self):
        """Test that intentional hyphens are preserved."""
        text = """This is a well-
Known pattern."""

        config = PreprocessorConfig(repair_hyphenation=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        # "well-Known" has uppercase K, so hyphen should be preserved
        assert "well-\nKnown" in result or "well-Known" in result

    def test_normalizes_whitespace(self):
        """Test whitespace normalization."""
        text = """Multiple   spaces   here.



Too many blank lines above."""

        config = PreprocessorConfig(normalize_whitespace=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        assert "  " not in result  # Multiple spaces collapsed
        assert "\n\n\n" not in result  # 3+ newlines collapsed to 2

    def test_removes_headers_footers(self):
        """Test removal of repeated headers and footers."""
        page_texts = [
            "CONFIDENTIAL\n\nPage 1 content.\n\nDocument v1.0",
            "CONFIDENTIAL\n\nPage 2 content.\n\nDocument v1.0",
            "CONFIDENTIAL\n\nPage 3 content.\n\nDocument v1.0",
            "CONFIDENTIAL\n\nPage 4 content.\n\nDocument v1.0",
        ]
        full_text = "\n\n".join(page_texts)

        config = PreprocessorConfig(remove_headers_footers=True)
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(full_text, page_texts=page_texts)

        # CONFIDENTIAL appears on all pages, should be removed
        assert "CONFIDENTIAL" not in result
        # Content should remain
        assert "Page 1 content" in result

    def test_custom_patterns(self):
        """Test custom regex patterns for removal."""
        text = """DRAFT - DO NOT DISTRIBUTE

Actual content here.

[INTERNAL USE ONLY]"""

        config = PreprocessorConfig(
            custom_patterns=[
                r'\[INTERNAL USE ONLY\]',
                r'DRAFT - DO NOT DISTRIBUTE',
            ]
        )
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        assert "DRAFT" not in result
        assert "INTERNAL USE ONLY" not in result
        assert "Actual content here" in result

    def test_empty_text(self):
        """Test preprocessing empty text."""
        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess("")
        assert result == ""

    def test_all_options_disabled(self):
        """Test with all preprocessing disabled."""
        text = """1. Intro ......... 5

Content here.

© 2025 Copyright"""

        config = PreprocessorConfig(
            remove_toc=False,
            remove_headers_footers=False,
            repair_hyphenation=False,
            remove_page_numbers=False,
            remove_boilerplate=False,
            normalize_whitespace=False,
        )
        preprocessor = DocumentPreprocessor(config)
        result = preprocessor.preprocess(text)

        # Everything should be preserved
        assert "1. Intro ......... 5" in result
        assert "© 2025 Copyright" in result


class TestORANSpecificPreprocessing:
    """Tests for O-RAN document-specific preprocessing."""

    def test_removes_oran_document_id(self):
        """Test removal of O-RAN document IDs."""
        text = """O-RAN.WG10.TS.TE&IV-DM.0-R004-v02.00

Technical Specification

O-RAN Work Group 10 (OAM for O-RAN)

This is the actual content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        assert "O-RAN.WG10.TS.TE&IV-DM.0-R004-v02.00" not in result
        assert "O-RAN Work Group 10" not in result
        assert "Technical Specification" not in result
        assert "actual content" in result

    def test_removes_oran_document_id_with_technical_report(self):
        """Test removal of O-RAN document IDs with 'Technical Report' suffix."""
        text = """O-RAN.WG1.CCIN-R004-v01.00 Technical Report

Communication and Computing Integrated Networks

This is the actual content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        assert "O-RAN.WG1.CCIN-R004-v01.00" not in result
        assert "Technical Report" not in result
        assert "Communication and Computing Integrated Networks" not in result
        assert "actual content" in result

    def test_removes_oran_copyright_block(self):
        """Test removal of full O-RAN copyright block."""
        text = """Copyright © 2025 by the O-RAN ALLIANCE e.V.

The copying or incorporation into any other work of part or all of the material available in this specification in any form without the prior written permission of O-RAN ALLIANCE e.V. is prohibited, save that you may print or download extracts of the material of this specification for your personal use, or copy the material of this specification for the purpose of sending to individual third parties for their information provided that you acknowledge O-RAN ALLIANCE as the source of the material and that you inform the third party that these conditions apply to them and that they must comply with them.

This is the actual content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        assert "Copyright © 2025" not in result
        assert "copying or incorporation" not in result
        assert "must comply with them" not in result
        assert "actual content" in result

    def test_removes_oran_alliance_address(self):
        """Test removal of O-RAN ALLIANCE address block."""
        text = """O-RAN ALLIANCE e.V., Buschkauler Weg 27, 53347 Alfter, Germany

Register of Associations, Bonn VR 11238, VAT ID DE321720189

This is the actual content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        assert "O-RAN ALLIANCE e.V." not in result
        assert "Register of Associations" not in result
        assert "actual content" in result

    def test_removes_oran_toc_with_many_dots(self):
        """Test removal of TOC entries with many consecutive dots (O-RAN style)."""
        text = """Contents

Foreword ............................................................................................................................................................. 3

Modal verbs terminology .................................................................................................................................... 3

Executive summary ............................................................................................................................................ 3

1. Scope ........................................................................................................................................................ 4

2. References ................................................................................................................................................ 4

This is the actual specification content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        assert "Contents" not in result
        assert "Foreword" not in result
        assert "Modal verbs terminology" not in result
        assert "Executive summary" not in result
        assert "............" not in result
        assert "actual specification content" in result

    def test_removes_oran_numbered_toc_entries(self):
        """Test removal of numbered TOC entries."""
        text = """2. 2.1. 2.2.

References ................................................................................................................................................ 4 Normative references ......................................................................................................................................... 4 Informative references ........................................................................................................................................ 4

3. 3.1. 3.2. 3.3.

Definition of terms, symbols and abbreviations ....................................................................................... 4 Terms .................................................................................................................................................................. 4 Symbols .............................................................................................................................................................. 4 Abbreviations ..................................................................................................................................................... 4

This is the actual content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        # Lines with many dots should be removed
        assert "............" not in result
        assert "actual content" in result

    def test_removes_toc_section_number_remnants(self):
        """Test removal of TOC remnants that are just section numbers."""
        text = """2 2.1 2.2

3 3.1 3.2 3.3

4 4.1 4.1.1 4.1.2 4.1.3 4.1.4 4.1.5 4.2 4.3 4.4

7 7.1 7.1.1 7.1.2 7.1.3 7.1.4 7.2 7.2.1 7.2.2 7.2.3

This is the actual specification content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        # Lines with only section numbers should be removed
        assert "2 2.1 2.2" not in result
        assert "3 3.1 3.2 3.3" not in result
        assert "4 4.1 4.1.1" not in result
        assert "7 7.1 7.1.1" not in result
        assert "actual specification content" in result

    def test_removes_underscore_footer_separators(self):
        """Test removal of underscore footer/separator lines."""
        text = """Some content here.

________________________________________________________________________________________________ 3

More content.

_______________________________________________________________________________

Even more content."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        # Underscore lines should be removed
        assert "________________________________" not in result
        assert "_______________" not in result
        assert "Some content here" in result
        assert "More content" in result
        assert "Even more content" in result

    def test_preserves_actual_oran_content(self):
        """Test that actual O-RAN specification content is preserved."""
        text = """The NF Topology Exposure service provides APIs to SMO for topology data discovery and lifecycle management.

The service uses RESTful APIs with JSON payloads following YANG data models.

Figure 1: NF Topology Architecture

The topology includes relationships between NFs such as nearRTRIC, O-CU-CP, O-CU-UP, and O-DU."""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        # All actual content should be preserved
        assert "NF Topology Exposure" in result
        assert "RESTful APIs" in result
        assert "nearRTRIC" in result
        assert "O-CU-CP" in result

    def test_handles_mixed_oran_content(self):
        """Test preprocessing of mixed O-RAN document with boilerplate and content."""
        text = """O-RAN.WG10.TS.TE&IV-DM.0-R004-v02.00

Technical Specification

Copyright © 2025 by the O-RAN ALLIANCE e.V.

Contents

1. Scope ........................................................................................................................................................ 4

4. Solution Set (SS) definitions

4.1 YANG based Solution Set (SS) definitions

The TE&IV Data Model defines entities and relationships for O-RAN topology exposure.

module o-ran-smo-teiv-ran {
  namespace "urn:o-ran:smo-teiv-ran";
  prefix teiv-ran;
}"""

        preprocessor = DocumentPreprocessor()
        result = preprocessor.preprocess(text)

        # Boilerplate should be removed
        assert "O-RAN.WG10.TS" not in result
        assert "Technical Specification" not in result
        assert "Copyright © 2025" not in result
        assert "Contents" not in result
        assert "........................" not in result

        # Actual content should be preserved
        assert "TE&IV Data Model" in result
        assert "module o-ran-smo-teiv-ran" in result


class TestGetPreprocessor:
    """Tests for get_preprocessor factory function."""

    def test_default_preprocessor(self):
        """Test getting default preprocessor."""
        preprocessor = get_preprocessor()
        assert preprocessor.config.remove_toc is True
        assert preprocessor.config.repair_hyphenation is True

    def test_custom_options(self):
        """Test getting preprocessor with custom options."""
        preprocessor = get_preprocessor(
            remove_toc=False,
            custom_patterns=[r'\[DRAFT\]'],
        )
        assert preprocessor.config.remove_toc is False
        assert len(preprocessor.config.custom_patterns) == 1
