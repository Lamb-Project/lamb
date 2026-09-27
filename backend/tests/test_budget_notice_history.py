"""A budget notice in history never reads to the model as a rule for later turns."""
from types import SimpleNamespace as N

from lamb.aac.language import budget_notice, budget_model_note, is_budget_notice
from lamb.aac.result_store import provider_messages


def notice(code, limit=10):
    return budget_notice(N(skill_state={'ui_language': code}, max_tool_rounds=limit))


def test_saved_notices_in_every_language_reach_the_model_as_the_neutral_note():
    for code in ('en', 'es', 'ca', 'eu'):
        assert is_budget_notice(notice(code)) and is_budget_notice(notice(code, 7).strip())
        [out] = provider_messages([{'role': 'assistant', 'content': notice(code, 7)}])
        assert out['content'] == budget_model_note(7) and 'resets with every new user message' in out['content']


def test_ordinary_assistant_text_and_tool_calls_are_untouched():
    text = 'Este turno ha alcanzado algo distinto. No es un aviso.'
    assert not is_budget_notice(text)
    msgs = [{'role': 'assistant', 'content': text}, {'role': 'user', 'content': notice('es')},
            {'role': 'assistant', 'content': notice('es'), 'tool_calls': [{'id': 'x'}]}]
    assert provider_messages(msgs) == msgs


def test_new_notices_carry_the_model_note_and_keep_the_displayed_text():
    stored = {'role': 'assistant', 'content': notice('es'), '_aac_model_content': budget_model_note(10)}
    [out] = provider_messages([stored])
    assert out['content'] == budget_model_note(10) and stored['content'].startswith('Este turno')
