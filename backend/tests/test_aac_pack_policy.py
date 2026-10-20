"""Policy and content-pack invariants independent of model prose."""
import copy
import hashlib
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace as N
import unittest
from lamb.aac.pack_loader import load_pack, packs_root, render_prefix
from lamb.aac.preferences import validate_settings, response_policy, apply_policy
from lamb.aac.skill_routing import catalogue_prompt
from lamb.aac.language import apply_ui_language, append_turn_language

class PolicyTests(unittest.TestCase):
    providers={'ollama':{'enabled':True,'models':['qwen']},'openai':{'enabled':True,'models':['hosted']}}

    def test_default_and_explicit_driver(self):
        for settings in [{},{'provider':'ollama','model':'qwen','language_fallbacks':{'eu':'es'}}]:
            resolver=N(organization={'config':{'setups':{'default':{'providers':self.providers,'aac':settings}}}},get_global_default_model_config=lambda:{'provider':'openai','model':'hosted'})
            result=response_policy(resolver,'eu')
            self.assertEqual(result['model'],'qwen' if settings else 'hosted')
            self.assertEqual(result['effective_language'],'es' if settings else 'eu')

    def test_invalid_policy_rejected(self):
        for settings in [None, {'provider':'google','model':'x'}, {'provider':'ollama'},
                         {'provider':'ollama','model':'absent'}, {'language_fallbacks':{'eu':['es']}},
                         {'language_fallbacks':{'eu':'eu'}},{'language_fallbacks':{'eu':'es','es':'eu'}},
                         {'language_fallbacks':{'eu':'es','es':'en'}},{'pack_channel':'unknown'}, {'pack_version':'../evil'}]:
            with self.subTest(settings=settings),self.assertRaises(ValueError):validate_settings(settings,self.providers)

    def test_policy_appends_once_and_frontend_change_does_not_repin(self):
        agent=N(skill_state={'ui_language':'eu'},conversation=[{'role':'user','content':'original'}])
        apply_ui_language(agent,'eu')
        before=copy.deepcopy(agent.conversation)
        policy={'requested_language':'eu','effective_language':'es','fallback_applied':True,'provider':'ollama','model':'qwen'}
        apply_policy(agent,policy)
        pinned=copy.deepcopy(agent.conversation)
        apply_policy(agent,policy);apply_ui_language(agent,'en')
        self.assertEqual(agent.conversation,pinned)
        self.assertEqual(agent.conversation[:len(before)],before)
        self.assertEqual(agent.skill_state['ui_language'],'eu')
        append_turn_language(agent)
        self.assertIn('español',agent.conversation[-1]['content'])

class PackTests(unittest.TestCase):
    def test_10_extraction_has_identical_prefix(self):
        pack=load_pack(version='1.0.0')
        prefix=render_prefix(pack, {'layers':['creator']})
        expected=(Path(__file__).parent/'fixtures/aac_legacy_prefix.sha256').read_text().strip()
        self.assertEqual(hashlib.sha256(prefix.encode()).hexdigest(),expected)

    def test_missing_glossary_and_modified_or_extra_content_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'packs';shutil.copytree(packs_root(),root)
            persona=root/'lamb-default/persona.md';original=persona.read_text();persona.write_text(original+'changed')
            with self.assertRaises(ValueError):load_pack(root=root)
            persona.write_text(original)
            extra=root/'lamb-default/skills/unlisted.md';extra.write_text('unverified')
            with self.assertRaises(ValueError):load_pack(root=root)
            extra.unlink()
            (root/'lamb-default/glossary/eu.yaml').unlink()
            with self.assertRaises(ValueError):load_pack(root=root)

    def test_unknown_version_and_path_traversal_fail(self):
        for version in ['../evil','9.0.0']:
            with self.assertRaises(ValueError):load_pack(version=version)
