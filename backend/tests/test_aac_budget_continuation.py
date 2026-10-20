"""Offline budget boundaries and retained-evidence continuation, both transports."""
import json
import unittest
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

from tests.test_aac_legacy import agent, message, tool, turn
from lamb.aac.language import budget_notice
from lamb.aac.authorization import classify_user_confirmation


class BudgetContinuationTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_reuses_evidence_with_fresh_budget(self):
        for streaming in (False, True):
            a, p, s = agent([
                message(tools=[tool('lamb assistant list', ident='first')]),
                message('Found assistants; knowledge bases remain unchecked.'),
                message(tools=[tool('lamb kb list', ident='second')]),
                message('Both checks complete.'),
            ], max_tool_rounds=1)
            first = await turn(a, streaming, 'Check assistants and knowledge bases')
            self.assertEqual(first.count('tool-round limit'), 1)
            self.assertNotIn('tools', p.calls[1])
            instruction = p.calls[1]['messages'][-1]['content']
            self.assertIn('unresolved questions', instruction)
            self.assertFalse(any(m['content'] == instruction for m in a.conversation))
            second = await turn(a, streaming, 'continue')
            self.assertIn('tools', p.calls[2])
            self.assertTrue(any(m.get('tool_call_id') == 'first' for m in p.calls[2]['messages']))
            self.assertFalse(any(m.get('content') == instruction for m in p.calls[2]['messages']))
            self.assertEqual([c.args[0] for c in s.execute.await_args_list], ['lamb assistant list', 'lamb kb list'])
            self.assertEqual(second.count('tool-round limit'), 1)
            self.assertTrue(second.endswith('Both checks complete.'))

    async def test_serialized_history_can_resume_or_change_question(self):
        for streaming in (False, True):
            a, _, _ = agent([message(tools=[tool()]), message('Partial')], max_tool_rounds=1)
            await turn(a, streaming)
            # Same JSON messages representation used by the session envelope.
            saved = json.loads(json.dumps({'messages': a.conversation}))
            b, p, s = agent([message('Answer to the new question')], max_tool_rounds=1)
            b.conversation = saved['messages']
            result = await turn(b, streaming, 'Instead, explain what an assistant is')
            self.assertEqual(result, 'Answer to the new question')
            self.assertIn('tools', p.calls[0])
            self.assertTrue(any(m['role'] == 'tool' for m in p.calls[0]['messages']))
            s.execute.assert_not_awaited()

    async def test_parallel_calls_count_as_one_round(self):
        for streaming in (False, True):
            a, p, s = agent([message(tools=[tool(ident='a'), tool('lamb kb list', ident='b')]), message('Complete')], max_tool_rounds=1)
            result = await turn(a, streaming)
            self.assertEqual(s.execute.await_count, 2)
            self.assertIn('tool-round limit (1)', result)
            self.assertNotIn('tools', p.calls[-1])

    async def test_real_session_store_roundtrip(self):
        from lamb.aac.session_manager import AACSessionManager
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sessions.db'
            with sqlite3.connect(path) as conn:
                conn.execute('CREATE TABLE aac_sessions (id TEXT, assistant_id INTEGER, user_email TEXT, organization_id INTEGER, status TEXT, conversation TEXT, title TEXT, created_at TEXT, updated_at TEXT)')
            mgr = AACSessionManager.__new__(AACSessionManager)
            mgr.db = SimpleNamespace(get_connection=lambda: sqlite3.connect(path))
            mgr._table = 'aac_sessions'
            session = mgr.create_session('fixture@example.invalid', 1)
            a, _, _ = agent([message(tools=[tool()]), message('Partial')], max_tool_rounds=1)
            await turn(a, False)
            mgr.update_conversation(session['id'], 'fixture@example.invalid', a.conversation)
            self.assertIsNone(mgr.get_session(session['id'], 'other@example.invalid'))
            stored = mgr.get_session(session['id'], 'fixture@example.invalid')
            b, p, _ = agent([message(tools=[tool('lamb kb list')]), message('Complete')], max_tool_rounds=1)
            b.conversation = stored['conversation']
            self.assertTrue((await turn(b, False, 'continue')).endswith('Complete'))
            self.assertIn('tools', p.calls[0])
            self.assertTrue(any(m['role'] == 'tool' for m in p.calls[0]['messages']))

    async def test_continuation_does_not_approve_pending_write(self):
        for streaming in (False, True):
            a, _, s = agent([], max_tool_rounds=1,
                pending_action={'command': 'lamb assistant create x', 'action_key': 'assistant.create'})
            result = await turn(a, streaming, 'continue investigating')
            s.execute.assert_not_awaited()
            self.assertIsNotNone(a.pending_action)
            self.assertNotIn('tool-round limit', result)

    async def test_notice_survives_final_provider_failure(self):
        for streaming in (False, True):
            a, _, s = agent([message(tools=[tool()]), RuntimeError('offline failure')], max_tool_rounds=1)
            with self.assertRaisesRegex(RuntimeError, 'offline failure'):
                await turn(a, streaming)
            self.assertTrue(any(m['role'] == 'tool' for m in a.conversation))
            self.assertEqual(sum('tool-round limit' in m.get('content', '') for m in a.conversation), 1)
            s.execute.assert_awaited_once()

    async def test_zero_budget_notice_and_transcript_once(self):
        for streaming in (False, True):
            a, p, s = agent([message('No checks performed.')], max_tool_rounds=0)
            result = await turn(a, streaming)
            self.assertIn('tool-round limit (0)', result)
            self.assertEqual(result, ''.join(m['content'] for m in a.conversation if m['role'] == 'assistant'))
            self.assertNotIn('tools', p.calls[0])
            s.execute.assert_not_awaited()

    def test_localized_notice_and_plain_continuation_not_approval(self):
        a, _, _ = agent([], max_tool_rounds=10)
        for code, word in [('en', 'tool-round'), ('es', 'rondas'), ('ca', 'rondes'), ('eu', 'tresna')]:
            a.skill_state = {'ui_language': code}
            self.assertIn(word, budget_notice(a))
            self.assertIn('(10)', budget_notice(a))
        for reply in ('continue', 'continue investigating', 'continúa investigando', 'continua investigant'):
            self.assertEqual(classify_user_confirmation(reply), 'other')
