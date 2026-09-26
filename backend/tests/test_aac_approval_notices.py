"""#495: approval state is stated by the application, not left to model prose."""
import unittest
from tests.test_aac_legacy import agent, message, tool, turn

COMMAND = 'lamb assistant update 97 --description "New description"'
NOTE = 'has not been prepared for approval'
PENDING = 'still waiting for your decision'


class ApprovalNotices(unittest.IsolatedAsyncioTestCase):
    async def test_write_shown_only_as_text_gets_a_notice(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                a, p, s = agent([message(f'Ready for your confirmation:\n\n```\n{COMMAND}\n```')])
                answer = await turn(a, streaming, 'Change the description')
                self.assertIsNone(a.pending_action)
                self.assertIn(NOTE, answer)
                self.assertEqual(a.conversation[-1]['content'], answer)
                s.execute.assert_not_awaited()

    async def test_read_command_or_plain_answer_gets_no_notice(self):
        for text in ['You can inspect it with `lamb assistant get 97`.', 'An ordinary answer.']:
            with self.subTest(text=text):
                a, p, s = agent([message(text)])
                self.assertNotIn(NOTE, await turn(a, False, 'How do I check it?'))

    async def test_queued_proposal_gets_no_unqueued_notice(self):
        a, p, s = agent([message('Preparing.', [tool(COMMAND)])])
        a.required_skill = lambda *args: None
        answer = await turn(a, False, 'Change the description')
        self.assertEqual(a.pending_action['command'], COMMAND)
        self.assertNotIn(NOTE, answer)
        self.assertNotIn(PENDING, answer)

    async def test_new_request_while_pending_is_acknowledged_not_dropped(self):
        a, p, s = agent([message('Preparing.', [tool(COMMAND)]), message('Done.')])
        a.required_skill = lambda *args: None
        await turn(a, False, 'Change the description')
        answer = await turn(a, False, 'Actually, also change the system prompt to be shorter please')
        self.assertIn(PENDING, answer)
        self.assertEqual(a.pending_action['command'], COMMAND)
        s.execute.assert_not_awaited()
        # The notice is one-shot: an explicit decision afterwards executes the pending action once.
        await turn(a, False, 'yes')
        s.execute.assert_awaited_once_with(COMMAND)

    async def test_notices_follow_session_language(self):
        a, p, s = agent([message(f'```\n{COMMAND}\n```')])
        a.skill_state = {'ui_language': 'ca'}
        self.assertIn('no s’ha preparat per aprovar-lo', await turn(a, False, 'Canvia la descripció'))


def test_improve_skill_queues_requested_changes_instead_of_prose_proposals():
    """#495: the skill no longer contradicts the persona's queue-directly rule; 1.11.5 stays frozen."""
    from lamb.aac.pack_loader import load_pack
    skill = load_pack().text('skills/improve_assistant.md')
    assert 'show the proposed changes and wait for approval' not in skill
    assert 'queue the complete update command in the same turn' in skill
    assert 'Copy user-supplied text exactly' in skill
    assert 'wait for approval' in load_pack(version='1.11.5').text('skills/improve_assistant.md')
