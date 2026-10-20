"""Final grades must not be confused with rubric criterion scores."""
import pytest
from lamb.modules.file_evaluation.evaluator_client import EvaluatorClient

@pytest.mark.parametrize("feedback, expected", [
    ("Accuracy: Correct (Score: 4/4)\nTOTAL: 10.0 / 10.0\nSCORE: 10", 10),
    ("Score: 2\nFeedback revised.\nSCORE: 8.5", 8.5),
    ("Criterion (Score: 4/4)\n**FINAL SCORE**: 9 / 10", 9),
    ("Criterion (Score: 4/4)\nSCORE: 0", 0),
    ("Criterion (Score: 4/4)\nSCORE: 20", None),
    ("Nota final: 7", 7),
    ("Helpful feedback without a numerical grade.", None),
])
def test_final_score_extraction(feedback, expected):
    parsed = EvaluatorClient.parse_evaluation_response(
        {"choices": [{"message": {"content": feedback}}]}
    )
    assert parsed["success"] is True
    assert parsed["score"] == expected
    assert parsed["comment"] == feedback
