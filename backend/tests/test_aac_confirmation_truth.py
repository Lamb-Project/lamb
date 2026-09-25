"""Unexecuted proposals cannot be displayed as successful mutations."""
import unittest
from tests.test_aac_legacy import agent, message, tool, turn

class ConfirmationTruth(unittest.IsolatedAsyncioTestCase):
    async def test_false_tool_preamble_is_suppressed_and_exact_confirmation_is_saved(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                command = 'lamb assistant update 97 --description "New description"'
                a,p,s = agent([message('I have applied the change.', [tool(command)]), message('Saved.')])
                a.skill_state = {'ui_language':'es'}
                # Do not load a recipe in this boundary test.
                a.required_skill = lambda *args: None
                answer = await turn(a, streaming, 'Change the description')
                self.assertNotIn('applied', answer)
                self.assertNotIn('applied', str(a.conversation))
                self.assertIn('no se ha ejecutado', answer)
                self.assertIn(command, answer)
                self.assertEqual(a.conversation[-1]['content'], answer)
                self.assertEqual(a.pending_action['command'], command)
                self.assertEqual(len(p.calls), 1)
                s.execute.assert_not_awaited()
                await turn(a, streaming, 'yes')
                s.execute.assert_awaited_once_with(command)
                self.assertIsNone(a.pending_action)

    async def test_tool_free_answer_is_delivered_once(self):
        for streaming in (False, True):
            a,p,s = agent([message('An ordinary answer.')])
            self.assertEqual(await turn(a, streaming), 'An ordinary answer.')
            s.execute.assert_not_awaited()
