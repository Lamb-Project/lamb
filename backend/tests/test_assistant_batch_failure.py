"""Controlled completion failures with real persisted run records, without provider calls."""
import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock,Mock,patch
from contextlib import ExitStack
from lamb.services.test_service import TestService

class BatchFailure(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'runs.db'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE assistant_test_runs(id TEXT,assistant_id INTEGER,scenario_id TEXT,input_messages TEXT,output TEXT,token_usage TEXT,assistant_snapshot TEXT,model_used TEXT,elapsed_ms REAL,created_at TEXT)')
        self.service=TestService.__new__(TestService)
        self.service._prefix=''
        self.service.db=N(get_connection=lambda:sqlite3.connect(self.path))
        self.service.list_scenarios=Mock(return_value=[{'id':str(i),'title':f'Case {i}','messages':[{'role':'user','content':str(i)}]} for i in range(3)])

    def pipeline(self, failure):
        stack=ExitStack();self.addCleanup(stack.close)
        assistant=N(system_prompt='Test',owner='owner@test')
        stack.enter_context(patch('lamb.services.assistant_service.AssistantService',return_value=N(get_assistant_by_id=Mock(return_value=assistant))))
        base='lamb.completions.main.'
        stack.enter_context(patch(base+'get_assistant_details',return_value=assistant))
        stack.enter_context(patch(base+'parse_plugin_config',return_value={'connector':'test','llm':'controlled','rag_processor':'no_rag','prompt_processor':'simple_augment'}))
        output={'choices':[{'message':{'content':'Completed'}}],'model':'controlled'}
        connector=AsyncMock(side_effect=[output,failure,output])
        stack.enter_context(patch(base+'load_and_validate_plugins',return_value=(None,{'test':connector},None)))
        stack.enter_context(patch(base+'get_rag_context',AsyncMock(return_value={})))
        stack.enter_context(patch(base+'process_completion_request',side_effect=lambda body,*args:body['messages']))
        return connector

    async def test_timeout_returns_partial_results_and_continues(self):
        connector=self.pipeline(TimeoutError('Injected completion timeout'))
        results=await self.service.run_all_scenarios(25,'owner@test')
        self.assertEqual(len(results),3)
        self.assertIn('id',results[0]);self.assertIn('id',results[2])
        self.assertIn('Injected completion timeout',results[1]['error'])
        self.assertEqual(results[1]['scenario_id'],'1')
        self.assertEqual(connector.await_count,3)
        saved=self.service.list_runs(25)
        self.assertEqual({r['scenario_id'] for r in saved},{'0','2'})
        for result in [results[0],results[2]]:
            self.assertEqual(self.service.get_run(result['id'])['output']['choices'][0]['message']['content'],'Completed')
        # The failed attempt is returned as an error, not saved as a successful run.

    async def test_cancel_preserves_finished_run_without_starting_later_scenario(self):
        connector=self.pipeline(asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.service.run_all_scenarios(25,'owner@test')
        self.assertEqual(connector.await_count,2)
        self.assertEqual([r['scenario_id'] for r in self.service.list_runs(25)],['0'])
