"""An open test tab reloads when LAMB LEGATUS changes that assistant's saved tests or runs."""
import unittest

from lamb.aac.language import changed_test_assistant
from tests.test_aac_legacy import agent, message, tool


def test_commands_that_change_tests_name_their_assistant():
    assert changed_test_assistant('lamb test run 9 --timeout 900') == 9
    assert changed_test_assistant('lamb test add 9 "RAG" --message "¿Qué es RAG?" --type single_turn') == 9
    assert changed_test_assistant('lamb test evaluate 88bf good --assistant 12') == 12
    assert changed_test_assistant('lamb test delete-case 4 3') == 3
    assert changed_test_assistant('lamb test delete-scenario 4 3') == 3
    assert changed_test_assistant('lamb test update 9 4 --title Changed') == 9
    assert changed_test_assistant('lamb test evaluate 88bf 12 good') == 12
    assert changed_test_assistant('lamb test evaluate 88bf good 12') == 12
    for other in ('lamb test cases 9', 'lamb test run-detail 88bf --assistant 9', 'lamb assistant get 9', '', None, 'lamb test delete-case 4 --assistant 3', 'lamb test run --help'):
        assert changed_test_assistant(other) is None


class Event(unittest.IsolatedAsyncioTestCase):
    async def test_loop_emits_tests_changed_after_a_successful_run(self):
        a, p, s = agent([message('', [tool('lamb test run 9')]), message('Hecho.')])
        a.required_skill = lambda *args: None
        a.authorizer.check = lambda key: 'auto'
        events = [e async for e in a.chat_stream('ejecuta los tests del asistente 9')]
        assert {'status': 'tests_changed', 'assistant_id': 9} in events


    async def test_approved_mutations_emit_once_and_failures_or_rejections_do_not(self):
        from lamb.aac.liteshell.shell import ShellResult
        for command, key in [('lamb test add 9 "Case" --message "Question"', 'test.add'),
                             ('lamb test update 9 4 --title Changed', 'test.update'),
                             ('lamb test delete-case 4 9', 'test.delete-case')]:
            for decision, success in [('approve', True), ('approve', False), ('reject', True), ('edit', True)]:
                with self.subTest(command=command, decision=decision, success=success):
                    a, _, shell = agent([message('Done.')])
                    a.pending_action = {'command': command, 'action_key': key}
                    a.approval_decision = decision
                    shell.execute.return_value = ShellResult(success, data={})
                    events = [event async for event in a.chat_stream('yes')]
                    changed = [e for e in events if isinstance(e, dict) and e.get('status') == 'tests_changed']
                    assert changed == ([{'status': 'tests_changed', 'assistant_id': 9}]
                                       if decision == 'approve' and success else [])
