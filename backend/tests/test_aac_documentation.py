"""Delivered section hashes, coverage and user-visible fallback evidence."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from lamb.aac.documentation import read_topic, validate_docs, manifest, docs_root, content_metadata
from lamb.aac.liteshell.shell import LiteShell
from tests.test_aac_legacy import agent, message, turn


class DocumentationTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_documentation_and_localized_methodology(self):
        self.assertTrue(validate_docs())
        metadata = manifest()
        self.assertEqual(metadata['coverage']['en']['translated_sections'], metadata['coverage']['en']['total_sections'])
        for language in ('ca', 'es'):
            for topic in metadata['topics']:
                if topic.startswith('design-'):
                    result = read_topic(topic, language)
                    self.assertEqual(result['fallback_sections'], [])
                    self.assertIsNone(result['notice'])
        result = read_topic('getting-started', 'ca', 'login')
        self.assertEqual(result['fallback_sections'], ['login'])
        self.assertEqual(result['fallback_language'], 'en')
        self.assertIn('English', result['notice'])
        with self.assertRaises(ValueError): read_topic('getting-started', 'ca', 'Login')
        with self.assertRaises(ValueError): read_topic('../secret', 'ca')

    async def test_stale_coverage_hashes_and_anchor_skeleton_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'docs'
            shutil.copytree(docs_root(), root)
            target = root/'ca/getting-started.md'
            original = target.read_text()
            target.write_text(original + '\nChanged')
            with self.assertRaisesRegex(ValueError, 'stale'): validate_docs(root)
            target.write_text(original.replace('id="login"', 'id="different"'))
            with self.assertRaisesRegex(ValueError, 'anchor mismatch'): validate_docs(root)
            target.write_text(original)
            index = root/'manifest.json'
            metadata = json.loads(index.read_text())
            metadata['coverage']['ca']['translated_sections'] = 86
            index.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'coverage is stale'): validate_docs(root)

    async def test_fallback_notice_survives_provider_omission_once_in_both_transports(self):
        for streaming in (False, True):
            state = {'ui_language': 'es'}
            shell = LiteShell(server_url='unused', token='fake', user_email='teacher@test', organization_id=4)
            shell.knowledge = {'brief': {'session_language': 'es'}, 'state': state}
            result = await shell.execute('lamb docs read getting-started --section login')
            self.assertTrue(result.success, result.error)
            a, provider, _ = agent([message('Respuesta'), message('Otra respuesta')], skill_state=state)
            text = await turn(a, streaming)
            self.assertIn('original en inglés', text)
            self.assertIn('getting-started#login', text)
            self.assertEqual(a.conversation[-1]['content'], text)
            self.assertNotIn('original en inglés', await turn(a, streaming))
            self.assertEqual(state['documentation_fallback']['sections'], ['login'])
