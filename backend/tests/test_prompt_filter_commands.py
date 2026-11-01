import json
import unittest
from lamb.aac.liteshell.shell import prepare_command
from lamb.aac.authorization import ActionAuthorizer
from tests.test_aac_authoring import Authoring


class FilterCommands(unittest.IsolatedAsyncioTestCase):
    async def test_create_update_and_preview(self):
        s, h = Authoring().shell()
        r = await s.execute('lamb assistant create Interview --system-prompt "Age {{RANDOM:25-70}}" --random-filter')
        self.assertTrue(r.success, r.error)
        body = h.post.call_args.kwargs['json']
        md = json.loads(body['metadata']); identity = md['prompt_filters']['items'][0]['id']
        md['custom'] = 'keep'
        h.get.return_value = {**body, 'metadata': json.dumps(md)}
        r = await s.execute('lamb assistant update 42 --no-random-filter')
        self.assertTrue(r.success, r.error)
        changed = json.loads(h.put.call_args.kwargs['json']['metadata'])
        self.assertEqual(changed['custom'], 'keep')
        self.assertEqual(changed['prompt_filters']['items'][0]['id'], identity)
        self.assertFalse(changed['prompt_filters']['items'][0]['enabled'])
        r = await s.execute('lamb assistant preview-filters 42')
        self.assertTrue(r.success, r.error)
        h.post.assert_awaited_with('/creator/assistant/prompt-filters/preview', json={'system_prompt': body['system_prompt'], 'metadata': md})
        self.assertEqual(ActionAuthorizer().check('assistant.preview-filters'), 'auto')
        self.assertEqual(ActionAuthorizer().check('assistant.update'), 'ask')

    async def test_clear_and_invalid_json(self):
        s, h = Authoring().shell()
        h.get.return_value = {'name': 'Interview', 'metadata': {'prompt_filters': {'version': 1, 'items': []}, 'custom': 'keep'}}
        r = await s.execute('lamb assistant update 42 --prompt-filters null')
        self.assertTrue(r.success, r.error)
        self.assertIsNone(json.loads(h.put.call_args.kwargs['json']['metadata'])['prompt_filters'])
        h.put.reset_mock()
        r = await s.execute("lamb assistant update 42 --prompt-filters '[]'")
        self.assertFalse(r.success); h.put.assert_not_awaited()
        for args in ['--random-filter --no-random-filter', '--random-filter --prompt-filters null', '--random-filter maybe', '--prompt-filters']:
            with self.subTest(args=args), self.assertRaises(ValueError):
                prepare_command('lamb assistant update 42 '+args)

    def test_new_pack_teaches_filters_and_persistence(self):
        from lamb.aac.pack_loader import load_pack
        p = load_pack()
        self.assertEqual(p.version, '1.11.18')
        for name in ['create_assistant', 'improve_assistant']:
            text = p.text('skills/'+name+'.md')
            for required in ['{{RANDOM:25-70}}', '--random-filter', '--no-random-filter', 'preview-filters', '--persist', '--chat-id']:
                self.assertIn(required, text)
