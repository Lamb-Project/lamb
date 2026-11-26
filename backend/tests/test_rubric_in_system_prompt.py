"""Issue 577: a rubric assistant gets its rubric at the end of the system prompt and the input alone as user message."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from lamb.completions.pps.simple_augment import prompt_processor
from lamb.completions.rag import rubric_rag

RUBRIC = {'title': 'Lab 3', 'description': '', 'rubric_data': {'title': 'Lab 3', 'scoringType': 'points', 'maxScore': 10, 'criteria': [
    {'id': 'c1', 'name': 'Evidence', 'description': 'Shows a real run', 'weight': 100, 'levels': [
        {'id': 'l1', 'score': 4, 'label': 'Complete', 'description': 'Shows the output of the run'},
        {'id': 'l2', 'score': 1, 'label': 'Missing', 'description': 'Shows no output'}]}]}}


def assistant(template, system='You are the teaching assistant of this course.\n\nASSIGNMENT: write a report with a real run.'):
    return SimpleNamespace(owner='teacher@example.test', system_prompt=system, prompt_template=template,
                           metadata=json.dumps({'rubric_id': 'r1', 'rubric_format': 'markdown'}), api_callback='')


def assembled(a, text, maximum=10):
    rubric = json.loads(json.dumps(RUBRIC))
    rubric['rubric_data']['maxScore'] = maximum
    with patch('lamb.evaluaitor.rubric_database.RubricDatabaseManager') as manager:
        manager.return_value.get_rubric_by_id.return_value = rubric
        context = rubric_rag.rag_processor([{'role': 'user', 'content': text}], assistant=a)
    return prompt_processor({'messages': [{'role': 'user', 'content': text}]}, assistant=a, rag_context=context), context


def test_the_rubric_and_the_grade_line_end_the_system_prompt_and_the_user_message_is_the_input():
    a = assistant('{user_input}')
    first, context = assembled(a, 'Submission of student one.')
    second, _ = assembled(a, 'A different submission.')
    assert [m['role'] for m in first] == ['system', 'user']
    system = first[0]['content']
    assert system.startswith(a.system_prompt) and 'Shows the output of the run' in system
    assert system.rstrip().splitlines()[-1].startswith('N is the final score on a scale from 0 to 10')
    assert system.index('ASSIGNMENT') < system.index('PERFORMANCE LEVELS') < system.index('FINAL SCORE: N')
    assert first[1]['content'] == 'Submission of student one.', 'the user message is exactly the input'
    assert first[0] == second[0], 'the same system message for every submission'
    assert context['context'] == '' and context['sources'][0]['type'] == 'rubric'


def test_a_rubric_scored_out_of_another_maximum_is_converted_and_one_without_instructions_still_works():
    messages, _ = assembled(assistant('', system=''), 'Submission.', maximum=100)
    assert messages[0]['role'] == 'system' and messages[0]['content'].startswith('#'), 'the system message is the rubric'
    assert 'divide the final score by 100 and multiply by 10' in messages[0]['content']
    assert messages[1]['content'] == 'Submission.'


def test_an_assistant_saved_the_earlier_way_is_assembled_as_before():
    a = assistant('Rubric:\n{context}\n\nSubmission: {user_input}')
    messages, context = assembled(a, 'Submission of student one.')
    assert messages[0] == {'role': 'system', 'content': a.system_prompt}
    assert 'Shows the output of the run' in messages[1]['content'] and 'Submission of student one.' in messages[1]['content']
    assert 'system_context' not in context and 'FINAL SCORE: N' not in messages[1]['content']


def test_the_grade_line_is_read_by_supervised_assessment():
    from lamb.modules.file_evaluation.evaluator_client import EvaluatorClient
    answer = '### Overall Feedback\nGood evidence. Score: 3/4 on the first criterion.\n\nFINAL SCORE: 7.5'
    assert EvaluatorClient._extract_score_and_feedback(answer)['score'] == 7.5
