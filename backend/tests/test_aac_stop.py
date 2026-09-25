"""Stop closes the provider and preserves a valid, resumable transcript."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock
from tests.test_aac_legacy import agent, message, tool
from lamb.aac.previews import preview

class StopTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_mid_text_preserves_partial_and_closes_provider(self):
        a,p,s=agent([message('Partial response'),message('Resumed')])
        stream=a.chat_stream('hello')
        self.assertEqual((await anext(stream))['status'],'thinking')
        text=await anext(stream)
        await stream.aclose()
        self.assertTrue(p.streams[0].closed)
        self.assertEqual(a.conversation[-1],{'role':'assistant','content':text})
        self.assertEqual(len(p.calls),1)
        result=[e async for e in a.chat_stream('continue')]
        self.assertIn('Resumed',''.join(e for e in result if isinstance(e,str)))

    async def test_cancel_tool_does_not_run_next_tool_and_repairs_results(self):
        a,p,s=agent([message(tools=[tool(ident='first'),tool(ident='second')]),message('Recovered')])
        started=asyncio.Event()
        async def hang(*args):
            started.set()
            await asyncio.Event().wait()
        s.execute=AsyncMock(side_effect=hang)
        async def consume():
            async for _ in a.chat_stream('list'): pass
        task=asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(),2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        s.execute.assert_awaited_once()
        self.assertEqual(a.tool_audit[-1]["outcome"], "unknown")
        self.assertTrue(a.tool_audit[-1]["interrupted"])
        results=[m for m in a.conversation if m['role']=='tool']
        self.assertEqual({m['tool_call_id'] for m in results},{'first','second'})
        self.assertTrue(all(json.loads(m['content'])['interrupted'] for m in results))
        self.assertTrue(p.streams[0].closed)
        self.assertEqual(len(p.calls),1)
        _=[e async for e in a.chat_stream('what happened?')]

    async def test_stop_approved_write_records_unknown_outcome_without_requeue(self):
        a,p,s=agent([])
        a.pending_action={'command':'lamb assistant update 1 --description revised','action_key':'assistant.update'}
        started=asyncio.Event()
        async def hang(*args):
            started.set()
            await asyncio.Event().wait()
        s.execute=AsyncMock(side_effect=hang)
        async def consume():
            async for _ in a.chat_stream('yes'): pass
        task=asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(),2);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertIsNone(a.pending_action)
        self.assertEqual(a.tool_audit[-1]['outcome'], 'unknown')
        self.assertIn('Interrupted', a.tool_audit[-1]['summary'])
        self.assertIn('Outcome may be unknown',a.conversation[-1]['content'])
        self.assertEqual(len(p.calls),0)

    async def test_provider_close_failure_still_preserves_partial(self):
        a,p,s=agent([message('Partial response')], max_tool_rounds=0)
        stream=a.chat_stream('hello')
        await anext(stream);text=await anext(stream)
        p.streams[0].close=AsyncMock(side_effect=RuntimeError('close failed'))
        with self.assertRaisesRegex(RuntimeError,'close failed'):await stream.aclose()
        self.assertEqual(a.conversation[-1],{'role':'assistant','content':text})

    async def test_completed_turn_does_not_duplicate_text(self):
        a,p,s=agent([message('Complete')])
        _=[e async for e in a.chat_stream('hi')]
        self.assertEqual([m['content'] for m in a.conversation if m['role']=='assistant'],['Complete'])

class PreviewTests(unittest.TestCase):
    def test_extractive_titles_hide_internal_messages_and_preserve_renames(self):
        messages=[{'role':'user','content':'[System: private instructions]'}, {'role':'user','content':'Create an arithmetic tutor'}, {'role':'assistant','content':'Saved the tutor.'}]
        self.assertEqual(preview('LAMB Helper',messages)['display_title'],'Create an arithmetic tutor')
        self.assertNotIn('private',preview('',messages)['summary'])
        self.assertEqual(preview('My own title',messages)['title'],'My own title')
        self.assertEqual(preview('LAMB Helper',messages)['title'],'LAMB Helper')
        self.assertEqual(len(messages),3)
