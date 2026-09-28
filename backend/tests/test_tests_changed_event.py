"""An open test tab reloads when LAMB LEGATUS changes that assistant's saved tests or runs."""
import unittest

from lamb.aac.language import changed_test_assistant
from tests.test_aac_legacy import agent, message, tool


def test_commands_that_change_tests_name_their_assistant():
    assert changed_test_assistant('lamb test run 9 --timeout 900') == 9
    assert changed_test_assistant('lamb test add 9 "RAG" --message "¿Qué es RAG?" --type single_turn') == 9
    assert changed_test_assistant('lamb test evaluate 88bf --assistant 12 --verdict good') == 12
    assert changed_test_assistant('lamb test delete-case 4 --assistant 3') == 3
    for other in ('lamb test cases 9', 'lamb test run-detail 88bf --assistant 9', 'lamb assistant get 9', '', None):
        assert changed_test_assistant(other) is None


class Event(unittest.IsolatedAsyncioTestCase):
    async def test_loop_emits_tests_changed_after_a_successful_run(self):
        a, p, s = agent([message('', [tool('lamb test run 9')]), message('Hecho.')])
        a.required_skill = lambda *args: None
        a.authorizer.check = lambda key: 'auto'
        events = [e async for e in a.chat_stream('ejecuta los tests del asistente 9')]
        assert {'status': 'tests_changed', 'assistant_id': 9} in events
