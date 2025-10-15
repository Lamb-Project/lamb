"""
Unit tests for rubric_rag processor
"""

import json
from unittest.mock import Mock, patch
from backend.lamb.completions.rag.rubric_rag import rag_processor


class MockAssistant:
    def __init__(self, metadata):
        self.api_callback = json.dumps(metadata)
        self.owner = "test@example.com"
        self.metadata = json.dumps(metadata)


def test_rubric_rag_with_valid_rubric_markdown():
    """Test rubric_rag processor with valid rubric in markdown format"""

    # Mock rubric data
    mock_rubric = {
        "rubric_id": "test-rubric-123",
        "title": "Test Rubric",
        "description": "Test Description",
        "rubric_data": {
            "title": "Test Rubric",
            "description": "Test Description",
            "scoringType": "points",
            "maxScore": 10,
            "metadata": {
                "subject": "Math",
                "gradeLevel": "9-12"
            },
            "criteria": [
                {
                    "id": "crit-1",
                    "name": "Accuracy",
                    "description": "Mathematical accuracy",
                    "weight": 50,
                    "order": 0,
                    "levels": [
                        {
                            "id": "level-1-1",
                            "score": 4,
                            "label": "Exemplary",
                            "description": "All correct",
                            "order": 0
                        },
                        {
                            "id": "level-1-2",
                            "score": 3,
                            "label": "Proficient",
                            "description": "Mostly correct",
                            "order": 1
                        }
                    ]
                }
            ]
        }
    }

    # Mock the entire database import and call
    with patch('backend.lamb.completions.rag.rubric_rag.RubricDatabaseManager') as mock_db_manager_class:
        mock_manager_instance = mock_db_manager_class.return_value
        mock_manager_instance.get_rubric_by_id.return_value = mock_rubric

        # Create mock assistant
        assistant = MockAssistant({
            "rag_processor": "rubric_rag",
            "rubric_id": "test-rubric-123",
            "rubric_format": "markdown"
        })

        # Call processor
        result = rag_processor(
            messages=[{"role": "user", "content": "How am I graded?"}],
            assistant=assistant
        )

        # Assertions
        assert result is not None
        assert "context" in result
        assert "sources" in result
        assert len(result["context"]) > 0
        assert "Test Rubric" in result["context"]
        assert "Accuracy" in result["context"]
        assert "Exemplary" in result["context"]
        assert "Proficient" in result["context"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["rubric_id"] == "test-rubric-123"
        assert result["sources"][0]["format"] == "markdown"


def test_rubric_rag_with_valid_rubric_json():
    """Test rubric_rag processor with valid rubric in JSON format"""

    # Mock rubric data
    mock_rubric = {
        "rubric_id": "test-rubric-456",
        "title": "JSON Test Rubric",
        "description": "JSON format test",
        "rubric_data": {
            "title": "JSON Test Rubric",
            "description": "JSON format test",
            "scoringType": "points",
            "maxScore": 10,
            "metadata": {
                "subject": "Science",
                "gradeLevel": "6-8"
            },
            "criteria": [
                {
                    "id": "crit-1",
                    "name": "Methodology",
                    "description": "Scientific method",
                    "weight": 100,
                    "order": 0,
                    "levels": [
                        {
                            "id": "level-1-1",
                            "score": 5,
                            "label": "Excellent",
                            "description": "Perfect methodology",
                            "order": 0
                        }
                    ]
                }
            ]
        }
    }

    # Mock database call
    with patch('backend.lamb.completions.rag.rubric_rag.RubricDatabaseManager') as mock_db_manager_class:
        mock_manager_instance = mock_db_manager_class.return_value
        mock_manager_instance.get_rubric_by_id.return_value = mock_rubric

        # Create mock assistant
        assistant = MockAssistant({
            "rag_processor": "rubric_rag",
            "rubric_id": "test-rubric-456",
            "rubric_format": "json"
        })

        # Call processor
        result = rag_processor(
            messages=[{"role": "user", "content": "How am I graded?"}],
            assistant=assistant
        )

        # Assertions
        assert result is not None
        assert "context" in result
        assert "sources" in result
        assert len(result["context"]) > 0

        # Verify it's JSON format
        try:
            json_data = json.loads(result["context"])
            assert json_data["title"] == "JSON Test Rubric"
            assert json_data["scoringType"] == "points"
        except json.JSONDecodeError:
            raise AssertionError("Context should be valid JSON")

        assert len(result["sources"]) == 1
        assert result["sources"][0]["rubric_id"] == "test-rubric-456"
        assert result["sources"][0]["format"] == "json"


def test_rubric_rag_missing_rubric_id():
    """Test rubric_rag processor when rubric_id is missing"""

    assistant = MockAssistant({
        "rag_processor": "rubric_rag"
        # No rubric_id
    })

    result = rag_processor(
        messages=[{"role": "user", "content": "Test"}],
        assistant=assistant
    )

    assert result["context"] == ""
    assert result["sources"] == []


def test_rubric_rag_rubric_not_found():
    """Test rubric_rag processor when rubric doesn't exist"""

    with patch('backend.lamb.completions.rag.rubric_rag.RubricDatabaseManager') as mock_db_manager_class:
        mock_manager_instance = mock_db_manager_class.return_value
        mock_manager_instance.get_rubric_by_id.return_value = None  # Rubric not found

        assistant = MockAssistant({
            "rag_processor": "rubric_rag",
            "rubric_id": "nonexistent-rubric"
        })

        result = rag_processor(
            messages=[{"role": "user", "content": "Test"}],
            assistant=assistant
        )

        assert "ERROR" in result["context"] or result["context"] == ""
        assert result["sources"] == []


def test_rubric_rag_invalid_format():
    """Test rubric_rag processor when rubric_format is invalid"""

    mock_rubric = {
        "rubric_id": "test-rubric-789",
        "title": "Invalid Format Test",
        "rubric_data": {
            "title": "Invalid Format Test",
            "criteria": []
        }
    }

    with patch('backend.lamb.completions.rag.rubric_rag.RubricDatabaseManager') as mock_db_manager_class:
        mock_manager_instance = mock_db_manager_class.return_value
        mock_manager_instance.get_rubric_by_id.return_value = mock_rubric

        assistant = MockAssistant({
            "rag_processor": "rubric_rag",
            "rubric_id": "test-rubric-789",
            "rubric_format": "invalid_format"  # Invalid format
        })

        result = rag_processor(
            messages=[{"role": "user", "content": "Test"}],
            assistant=assistant
        )

        # Should default to markdown format
        assert "Invalid Format Test" in result["context"]
        assert result["sources"][0]["format"] == "markdown"


def test_rubric_rag_default_format():
    """Test rubric_rag processor when rubric_format is not specified (should default to markdown)"""

    mock_rubric = {
        "rubric_id": "test-rubric-999",
        "title": "Default Format Test",
        "rubric_data": {
            "title": "Default Format Test",
            "criteria": []
        }
    }

    with patch('backend.lamb.completions.rag.rubric_rag.RubricDatabaseManager') as mock_db_manager_class:
        mock_manager_instance = mock_db_manager_class.return_value
        mock_manager_instance.get_rubric_by_id.return_value = mock_rubric

        assistant = MockAssistant({
            "rag_processor": "rubric_rag",
            "rubric_id": "test-rubric-999"
            # No rubric_format specified
        })

        result = rag_processor(
            messages=[{"role": "user", "content": "Test"}],
            assistant=assistant
        )

        # Should default to markdown format
        assert "Default Format Test" in result["context"]
        assert result["sources"][0]["format"] == "markdown"


def test_rubric_rag_assistant_no_owner():
    """Test rubric_rag processor when assistant has no owner"""

    assistant = MockAssistant({
        "rag_processor": "rubric_rag",
        "rubric_id": "test-rubric"
    })

    # Remove owner attribute
    delattr(assistant, 'owner')

    result = rag_processor(
        messages=[{"role": "user", "content": "Test"}],
        assistant=assistant
    )

    assert result["context"] == ""
    assert result["sources"] == []


if __name__ == "__main__":
    # Simple test runner
    import sys
    import traceback

    def run_test(test_func, test_name):
        try:
            print(f"Running {test_name}...")
            test_func()
            print(f"✅ {test_name} PASSED")
            return True
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            traceback.print_exc()
            return False

    # Run tests
    tests = [
        (test_rubric_rag_with_valid_rubric_markdown, "test_rubric_rag_with_valid_rubric_markdown"),
        (test_rubric_rag_with_valid_rubric_json, "test_rubric_rag_with_valid_rubric_json"),
        (test_rubric_rag_missing_rubric_id, "test_rubric_rag_missing_rubric_id"),
        (test_rubric_rag_rubric_not_found, "test_rubric_rag_rubric_not_found"),
        (test_rubric_rag_invalid_format, "test_rubric_rag_invalid_format"),
        (test_rubric_rag_default_format, "test_rubric_rag_default_format"),
        (test_rubric_rag_assistant_no_owner, "test_rubric_rag_assistant_no_owner"),
    ]

    passed = 0
    total = len(tests)

    for test_func, test_name in tests:
        if run_test(test_func, test_name):
            passed += 1

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)
