"""Unit tests for document parsers."""

import json
from pathlib import Path

import pytest

from src.ingest.parsers import (
    CSVParser,
    HTMLParser,
    JSONParser,
    TextParser,
    get_parser,
)


class TestTextParser:
    """Tests for TextParser."""

    def test_parse_txt_file(self, temp_dir: Path):
        """Test parsing a plain text file."""
        file_path = temp_dir / "test.txt"
        content = "Line 1\nLine 2\nLine 3"
        file_path.write_text(content)

        parser = TextParser()
        result = parser.parse(file_path)

        assert result.text == content
        assert result.page_texts is None

    def test_parse_md_file(self, temp_dir: Path):
        """Test parsing a markdown file."""
        file_path = temp_dir / "test.md"
        content = "# Header\n\nParagraph text."
        file_path.write_text(content)

        parser = TextParser()
        result = parser.parse(file_path)

        assert result.text == content

    def test_parse_unicode(self, temp_dir: Path):
        """Test parsing file with unicode characters."""
        file_path = temp_dir / "unicode.txt"
        content = "Hello 世界 🌍"
        file_path.write_text(content, encoding="utf-8")

        parser = TextParser()
        result = parser.parse(file_path)

        assert result.text == content


class TestCSVParser:
    """Tests for CSVParser."""

    def test_parse_csv_simple(self, temp_dir: Path):
        """Test parsing a simple CSV file."""
        file_path = temp_dir / "test.csv"
        content = "name,age,city\nAlice,30,NYC\nBob,25,LA"
        file_path.write_text(content)

        parser = CSVParser()
        result = parser.parse(file_path)

        assert "name | age | city" in result.text
        assert "Alice | 30 | NYC" in result.text
        assert len(result.tables) == 1
        assert result.tables[0]["headers"] == ["name", "age", "city"]

    def test_parse_csv_with_quotes(self, temp_dir: Path):
        """Test parsing CSV with quoted fields."""
        file_path = temp_dir / "quoted.csv"
        content = 'name,desc\n"Smith, John","A description"'
        file_path.write_text(content)

        parser = CSVParser()
        result = parser.parse(file_path)

        assert "Smith, John" in result.text


class TestJSONParser:
    """Tests for JSONParser."""

    def test_parse_json_dict(self, temp_dir: Path):
        """Test parsing a JSON object."""
        file_path = temp_dir / "test.json"
        data = {"name": "Test", "value": 42, "nested": {"key": "val"}}
        file_path.write_text(json.dumps(data))

        parser = JSONParser()
        result = parser.parse(file_path)

        assert "name: Test" in result.text
        assert "value: 42" in result.text
        assert "nested.key: val" in result.text

    def test_parse_json_array(self, temp_dir: Path):
        """Test parsing a JSON array."""
        file_path = temp_dir / "array.json"
        data = [{"id": 1}, {"id": 2}]
        file_path.write_text(json.dumps(data))

        parser = JSONParser()
        result = parser.parse(file_path)

        assert "[0].id: 1" in result.text
        assert "[1].id: 2" in result.text


class TestHTMLParser:
    """Tests for HTMLParser."""

    def test_parse_html_simple(self, temp_dir: Path):
        """Test parsing simple HTML."""
        file_path = temp_dir / "test.html"
        content = """
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Header</h1>
            <p>Paragraph text.</p>
        </body>
        </html>
        """
        file_path.write_text(content)

        parser = HTMLParser()
        result = parser.parse(file_path)

        assert "Header" in result.text
        assert "Paragraph text." in result.text
        # Script/style should be removed
        assert "<script>" not in result.text

    def test_parse_html_strips_scripts(self, temp_dir: Path):
        """Test that scripts are stripped."""
        file_path = temp_dir / "script.html"
        content = """
        <html>
        <body>
            <p>Text</p>
            <script>alert('evil');</script>
        </body>
        </html>
        """
        file_path.write_text(content)

        parser = HTMLParser()
        result = parser.parse(file_path)

        assert "Text" in result.text
        assert "alert" not in result.text

    def test_parse_html_table(self, temp_dir: Path):
        """Test extracting tables from HTML."""
        file_path = temp_dir / "table.html"
        content = """
        <table>
            <tr><th>A</th><th>B</th></tr>
            <tr><td>1</td><td>2</td></tr>
        </table>
        """
        file_path.write_text(content)

        parser = HTMLParser()
        result = parser.parse(file_path)

        assert len(result.tables) == 1
        assert result.tables[0]["data"][0] == ["A", "B"]
        assert result.tables[0]["data"][1] == ["1", "2"]


class TestGetParser:
    """Tests for get_parser factory function."""

    def test_get_parser_txt(self, temp_dir: Path):
        """Test getting parser for .txt file."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        parser = get_parser(file_path)
        assert isinstance(parser, TextParser)

    def test_get_parser_md(self, temp_dir: Path):
        """Test getting parser for .md file."""
        file_path = temp_dir / "test.md"
        file_path.touch()

        parser = get_parser(file_path)
        assert isinstance(parser, TextParser)

    def test_get_parser_csv(self, temp_dir: Path):
        """Test getting parser for .csv file."""
        file_path = temp_dir / "test.csv"
        file_path.touch()

        parser = get_parser(file_path)
        assert isinstance(parser, CSVParser)

    def test_get_parser_json(self, temp_dir: Path):
        """Test getting parser for .json file."""
        file_path = temp_dir / "test.json"
        file_path.touch()

        parser = get_parser(file_path)
        assert isinstance(parser, JSONParser)

    def test_get_parser_html(self, temp_dir: Path):
        """Test getting parser for .html file."""
        file_path = temp_dir / "test.html"
        file_path.touch()

        parser = get_parser(file_path)
        assert isinstance(parser, HTMLParser)

    def test_get_parser_unsupported(self, temp_dir: Path):
        """Test error for unsupported file type."""
        file_path = temp_dir / "test.xyz"
        file_path.touch()

        with pytest.raises(ValueError, match="Unsupported file type"):
            get_parser(file_path)

    def test_get_parser_case_insensitive(self, temp_dir: Path):
        """Test that file extension matching is case insensitive."""
        file_path = temp_dir / "test.TXT"
        file_path.touch()

        parser = get_parser(file_path)
        assert isinstance(parser, TextParser)
