"""Translation escape-hatch provenance and actual approval-path regressions."""
import copy
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
from lamb.aac.pack_loader import load_pack
from lamb.aac.translation import translation_request, translate
from lamb.aac.authorization import ActionAuthorizer
from tests.test_aac_legacy import agent, message, tool, turn


class TranslationTests(unittest.IsolatedAsyncioTestCase):
    def knowledge(self):
        pack = load_pack()
        return {'pack': pack, 'brief': {'session_language': 'ca', 'layers': ['creator'],
                'glossary': pack.data('glossary/ca.yaml')},
                'state': {'last_user_input': 'Vull fer un qüestionari'}}

    async def test_term_must_be_missing_and_occur_as_a_complete_term(self):
        knowledge = self.knowledge()
        options = {'reason': 'missing-term', 'command': 'test.add', 'blocker': 'Identify the requested activity'}
        source, target, provenance = translation_request(knowledge, 'qüestionari', options)
        self.assertEqual((source, target), ('qüestionari', 'English'))
        self.assertEqual(provenance['command'], 'test.add')
        for term, override in [('qüest', {}), ('invented', {}), ('assistent', {}),
                               ('qüestionari', {'command': 'made.up'}),
                               ('qüestionari', {'blocker': ''}), ('qüestionari', {'reason': 'chat'})]:
            with self.subTest(term=term, override=override), self.assertRaises(ValueError):
                translation_request(knowledge, term, {**options, **override})

    async def test_document_translation_requires_observed_missing_section(self):
        knowledge = self.knowledge()
        options = {'reason': 'missing-doc', 'topic': 'topic', 'section': 'section'}
        with self.assertRaises(ValueError): translation_request(knowledge, '', options)
        knowledge['state']['documentation_fallback'] = {'topic': 'topic', 'sections': ['section']}
        with patch('lamb.aac.translation.read_topic', return_value={'content': 'Actual section', 'fallback_sections': ['section']}):
            self.assertEqual(translation_request(knowledge, 'injected content', options)[:2], ('Actual section', 'Catalan'))
        with patch('lamb.aac.translation.read_topic', return_value={'content': 'Available', 'fallback_sections': []}):
            with self.assertRaises(ValueError): translation_request(knowledge, '', options)

    async def test_utility_is_explicit_and_result_carries_provenance(self):
        knowledge = self.knowledge()
        options = {'reason': 'missing-term', 'command': 'test.add', 'blocker': 'Activity meaning'}
        config = {'setups': {'default': {'providers': {'ollama': {'enabled': True, 'models': ['utility']}},
                  'aac': {'utility_provider': 'ollama', 'utility_model': 'utility'}}}}
        resolver = N(organization={'config': config}, get_provider_config=lambda _: {'base_url': 'http://utility.test'})
        client = AsyncMock()
        client.chat.completions.create.return_value = N(choices=[N(message=N(content='quiz'))])
        with patch('lamb.aac.translation.OrganizationConfigResolver', return_value=resolver), patch('lamb.aac.translation.AsyncOpenAI') as factory:
            factory.return_value.__aenter__.return_value = client
            result = await translate(knowledge, 'user@test', 'qüestionari', options)
            self.assertTrue(result['machine_translation'])
            self.assertEqual(result['translation'], 'quiz')
            self.assertEqual(result['command'], 'test.add')
            self.assertEqual(knowledge['state']['translation_interpretations'], [result])
            self.assertEqual(client.chat.completions.create.call_args.kwargs['model'], 'utility')
            self.assertEqual(factory.call_args.kwargs['base_url'], 'http://utility.test/v1')
            config['setups']['default']['aac'] = {}
            factory.reset_mock()
            with self.assertRaisesRegex(ValueError, 'no translation utility'): await translate(knowledge, 'user@test', 'qüestionari', options)
            factory.assert_not_called()

    async def test_translation_forces_review_and_is_visible_in_both_transports(self):
        interpretation = {'source': 'qüestionari', 'translation': 'quiz ``` unsafe', 'machine_translation': True}
        for streaming in (False, True):
            state = {'ui_language': 'es', 'translation_interpretations': [copy.deepcopy(interpretation)]}
            a, provider, shell = agent([message(tools=[tool('lamb test add 3 Quiz --message Hola')]), message('¿Confirmar?')], skill_state=state)
            with patch.object(a, 'required_skill', return_value=None):
                text = await turn(a, streaming, 'Crear')
            shell.execute.assert_not_awaited()
            self.assertIn('Traducción automática', text)
            self.assertIn('Original: qüestionari', text)
            self.assertIn('Interpretación: quiz ``` unsafe', text)
            self.assertIn('````text', text)
            self.assertEqual(a.conversation[-1]['content'], text)
            self.assertEqual(a.pending_action['machine_translation_interpretations'], [interpretation])
            state['translation_interpretations'][0]['translation'] = 'later changed'
            self.assertEqual(a.pending_action['machine_translation_interpretations'][0]['translation'], interpretation['translation'])

    async def test_translation_never_overrides_denial_and_reads_remain_automatic(self):
        for action, command in [('test.add', 'lamb test add 3 Quiz --message Hola'), ('session.rename', 'lamb session rename Quiz')]:
            a, _, shell = agent([], skill_state={'translation_interpretations': [{'source': 'x', 'translation': 'y'}]}, authorizer=ActionAuthorizer({action: 'never'}))
            with patch.object(a, 'required_skill', return_value=None): result = await a._execute_tool(tool(command))
            self.assertFalse(result['success'])
            self.assertIsNone(a.pending_action)
            shell.execute.assert_not_awaited()
        a, _, shell = agent([], skill_state={'translation_interpretations': [{'source': 'x', 'translation': 'y'}]})
        with patch.object(a, 'required_skill', return_value=None): result = await a._execute_tool(tool('lamb assistant list'))
        self.assertTrue(result['success'])
        shell.execute.assert_awaited_once()
