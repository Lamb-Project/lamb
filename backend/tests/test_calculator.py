"""
Tests for the safe calculator tool.
"""

import pytest
from lamb.completions.tools.implementations.calculator import run_calculator


class TestCalculator:
    """Calculator is a pure function — no mocks needed."""

    def test_basic_arithmetic(self):
        """(3 + 5) * 2 = 16"""
        result = run_calculator({"expression": "(3 + 5) * 2"})
        assert result["success"] is True
        assert result["result"] == 16

    def test_division(self):
        """10 / 4 = 2.5"""
        result = run_calculator({"expression": "10 / 4"})
        assert result["success"] is True
        assert result["result"] == 2.5

    def test_exponentiation(self):
        """2 ** 10 = 1024"""
        result = run_calculator({"expression": "2 ** 10"})
        assert result["success"] is True
        assert result["result"] == 1024

    def test_modulo(self):
        """17 % 5 = 2"""
        result = run_calculator({"expression": "17 % 5"})
        assert result["success"] is True
        assert result["result"] == 2

    def test_floor_division(self):
        """17 // 5 = 3"""
        result = run_calculator({"expression": "17 // 5"})
        assert result["success"] is True
        assert result["result"] == 3

    def test_negative_numbers(self):
        """-5 + 3 = -2"""
        result = run_calculator({"expression": "-5 + 3"})
        assert result["success"] is True
        assert result["result"] == -2

    def test_division_by_zero(self):
        """Division by zero returns error, not crash."""
        result = run_calculator({"expression": "1 / 0"})
        assert result["success"] is False
        assert "error" in result

    def test_empty_expression(self):
        """Empty expression returns error."""
        result = run_calculator({"expression": ""})
        assert result["success"] is False
        assert "No expression" in result["error"]

    def test_missing_expression_key(self):
        """Missing 'expression' key returns error."""
        result = run_calculator({})
        assert result["success"] is False
        assert "No expression" in result["error"]

    def test_invalid_syntax(self):
        """Invalid syntax returns error, not crash."""
        result = run_calculator({"expression": "2 + +"})
        assert result["success"] is False
        assert "error" in result

    def test_eval_injection_blocked(self):
        """eval() call is blocked by AST parser."""
        result = run_calculator({"expression": "eval('print(1)')"})
        assert result["success"] is False
        assert "error" in result

    def test_import_injection_blocked(self):
        """__import__ call is blocked."""
        result = run_calculator({"expression": "__import__('os').system('ls')"})
        assert result["success"] is False
        assert "error" in result

    def test_string_input_blocked(self):
        """String constants are not allowed."""
        result = run_calculator({"expression": "'hello'"})
        assert result["success"] is False
        assert "error" in result

    def test_float_result(self):
        """0.1 + 0.2 returns a float."""
        result = run_calculator({"expression": "0.1 + 0.2"})
        assert result["success"] is True
        assert isinstance(result["result"], float)

    def test_large_numbers(self):
        """Large expressions should not overflow."""
        result = run_calculator({"expression": "2 ** 50"})
        assert result["success"] is True
        assert result["result"] == 2 ** 50