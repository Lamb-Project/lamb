"""One-off debug must inspect the supplied input, never run saved scenarios."""
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from lamb.aac.liteshell.shell import LiteShell
from lamb.completions.connectors.bypass import llm_connect

class DebugEvidence(unittest.IsolatedAsyncioTestCase):
    def shell(self, response):
        http = N(post=AsyncMock(return_value=response))
        return LiteShell('unused', 'token', 'owner@test', 1, _http_client=http), http

    async def test_actual_bypass_format_and_nonpersistent_endpoint(self):
        messages = [{'role':'system','content':'Tutor'}, {'role':'user','content':'Context: retrieved text\nPregunta: atención'}]
        response = await llm_connect(messages, body={}, llm='debug-bypass')
        shell, http = self.shell(response)
        result = await shell.execute('lamb assistant debug 95 --message "atención"')
        self.assertTrue(result.success, result.error)
        http.post.assert_awaited_once_with('/creator/assistant/95/chat/completions', json={
            'messages':[{'role':'user','content':'atención'}], 'debug_bypass':True,
            'stream':False, 'persist_chat':False})
        self.assertEqual(result.data['assembled_messages'], messages)
        self.assertFalse(result.data['saved_test_run'])
        self.assertFalse(result.data['persisted_chat'])

    async def test_empty_saved_runs_and_invalid_completions_fail_closed(self):
        responses = [{'runs':[], 'count':0}, {}, None,
                     {'model':'ordinary','choices':[{'message':{'content':'All good'}}]},
                     {'model':'debug-bypass','choices':[]}]
        responses += [{'model':'debug-bypass','choices':[{'message':{'content':text}}]}
                      for text in ['', 'Messages:\n[]', 'Messages:\nnull', 'Messages:\n[{}]', 'Messages:\nnot json']]
        for response in responses:
            with self.subTest(response=response):
                shell, http = self.shell(response)
                result = await shell.execute('lamb assistant debug 95 --message question')
                self.assertFalse(result.success)
                self.assertIn('no valid assembled input', result.error)
                self.assertEqual(http.post.await_count, 1)

    async def test_http_failures_are_not_inspection_success(self):
        for code in [403, 404, 500, 503]:
            shell, http = self.shell({})
            http.post.side_effect = ValueError(f'API error ({code})')
            result = await shell.execute('lamb assistant debug 95 --message question')
            self.assertFalse(result.success)
            self.assertIn(str(code), result.error)

    async def test_kb_probe_preserves_results_and_labels_limits(self):
        chunks = [{'text':'Hardware', 'score':0.512}]
        shell, http = self.shell({'results':chunks})
        result = await shell.execute('lamb kb query 25 "atención" --top-k 3')
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data['results'], chunks)
        self.assertEqual(result.data['evidence']['type'], 'direct_kb_query')
        self.assertEqual(result.data['evidence']['query'], {'query_text':'atención','plugin_params':{'top_k':3}})
        self.assertIn('not proof', result.data['evidence']['limitations'])
