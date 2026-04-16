"""Tests for pipeline/search.py parse_json_response (kimberlygarmoe-34)."""

import json
import pytest
from pipeline.search import parse_json_response


class TestParseJsonResponse:
    def test_plain_json_array(self):
        raw = '[{"title": "Writer", "url": "https://example.com"}]'
        result = parse_json_response(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Writer"

    def test_json_in_markdown_fences(self):
        raw = '```json\n[{"title": "Writer"}]\n```'
        result = parse_json_response(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Writer"

    def test_json_with_preamble_text(self):
        raw = 'Here are the results:\n[{"title": "Writer"}]\nEnd of results.'
        result = parse_json_response(raw)
        assert len(result) == 1

    def test_empty_array(self):
        result = parse_json_response("[]")
        assert result == []

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("")

    def test_nested_brackets_handled(self):
        raw = '[{"title": "Writer", "tags": ["tech", "docs"]}]'
        result = parse_json_response(raw)
        assert result[0]["tags"] == ["tech", "docs"]

    def test_markdown_fences_without_json_label(self):
        raw = '```\n[{"title": "Writer"}]\n```'
        result = parse_json_response(raw)
        assert len(result) == 1
