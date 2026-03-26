"""Tests for output formatting utilities."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from lamb_cli.output import (
    format_output,
    print_detail,
    print_error,
    print_json,
    print_plain,
    print_success,
    print_table,
)

COLUMNS = [("id", "ID"), ("name", "Name")]
SAMPLE_DATA = [
    {"id": "1", "name": "Alpha"},
    {"id": "2", "name": "Beta"},
]


class TestPrintJson:
    def test_outputs_valid_json(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_json(SAMPLE_DATA)
        parsed = json.loads(mock_out.getvalue())
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Alpha"

    def test_single_dict(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_json({"id": "42", "status": "ok"})
        parsed = json.loads(mock_out.getvalue())
        assert parsed["id"] == "42"


class TestPrintPlain:
    def test_tab_separated(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_plain(SAMPLE_DATA, COLUMNS)
        lines = mock_out.getvalue().strip().split("\n")
        assert lines[0] == "1\tAlpha"
        assert lines[1] == "2\tBeta"

    def test_missing_key_becomes_empty(self):
        data = [{"id": "1"}]
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_plain(data, COLUMNS)
        # Output is "1\t\n" — the empty name produces a trailing tab
        assert mock_out.getvalue() == "1\t\n"


class TestPrintDetail:
    def test_key_value_output(self):
        data = {"id": "42", "name": "Test"}
        fields = [("id", "ID"), ("name", "Name")]
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_detail(data, fields)
        output = mock_out.getvalue()
        assert "ID" in output
        assert "42" in output
        assert "Name" in output
        assert "Test" in output


class TestPrintTable:
    def test_contains_data(self, capsys):
        print_table(SAMPLE_DATA, COLUMNS, title="Test")
        captured = capsys.readouterr()
        assert "Alpha" in captured.out
        assert "Beta" in captured.out


class TestFormatOutput:
    def test_json_mode(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            format_output(SAMPLE_DATA, COLUMNS, "json")
        parsed = json.loads(mock_out.getvalue())
        assert len(parsed) == 2

    def test_plain_mode(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            format_output(SAMPLE_DATA, COLUMNS, "plain")
        lines = mock_out.getvalue().strip().split("\n")
        assert len(lines) == 2

    def test_table_mode(self, capsys):
        format_output(SAMPLE_DATA, COLUMNS, "table")
        captured = capsys.readouterr()
        assert "Alpha" in captured.out

    def test_single_dict_json(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            format_output({"id": "1", "name": "X"}, COLUMNS, "json")
        parsed = json.loads(mock_out.getvalue())
        assert parsed["id"] == "1"

    def test_single_dict_detail(self, capsys):
        fields = [("id", "ID"), ("name", "Name")]
        format_output({"id": "1", "name": "X"}, COLUMNS, "table", detail_fields=fields)
        captured = capsys.readouterr()
        assert "ID" in captured.out
        assert "1" in captured.out

    def test_single_dict_plain(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            format_output({"id": "1", "name": "X"}, COLUMNS, "plain")
        lines = mock_out.getvalue().strip().split("\n")
        assert "1" in lines


class TestStderrMessages:
    def test_print_error(self, capsys):
        print_error("something went wrong")
        captured = capsys.readouterr()
        assert "something went wrong" in captured.err

    def test_print_success(self, capsys):
        print_success("all good")
        captured = capsys.readouterr()
        assert "all good" in captured.err
