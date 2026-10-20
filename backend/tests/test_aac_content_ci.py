"""Small deterministic content gate; runs without a database or model SDK."""
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from lamb.aac.brief import session_brief, render_brief
from lamb.aac.pack_loader import load_pack, render_prefix, Pack
from lamb.aac.session_guidance import refresh_guidance
from lamb.aac.glossary import annotate, model_messages


class ContentCI(unittest.TestCase):
    def test_every_role_brief_matches_independently_authored_fixture(self):
        for kind in ('creator', 'lti_creator'):
            for administration in ('none', 'org_admin', 'admin'):
                auth = N(user={'id':7,'email':'fixture@example.test','auth_provider':kind}, organization={'id':4,'name':'Fixture School','slug':'qa-school'}, is_system_admin=administration=='admin', is_org_admin=administration=='org_admin')
                pack = N(version='1.1.0',fingerprint='fixture-pack-hash',data=lambda _: {'language':'en','ui':{},'terms':[]})
                brief = session_brief(auth,'en',{'rag_processors':[]},{'translated_sections':1,'total_sections':2},pack)
                expected = (Path(__file__).parent/'fixtures/aac-roles'/f'{kind}-{administration}.txt').read_text()
                with self.subTest(kind=kind,administration=administration): self.assertEqual(render_brief(brief),expected)

    def test_legacy_extraction_and_pack_refresh_are_stable(self):
        legacy = load_pack(version='1.0.0')
        expected = (Path(__file__).parent/'fixtures/aac_legacy_prefix.sha256').read_text().strip()
        self.assertEqual(hashlib.sha256(render_prefix(legacy,{}).encode()).hexdigest(),expected)
        pack = load_pack()
        brief = {'layers':['creator'],'session_language':'ca','glossary':pack.data('glossary/ca.yaml')}
        state = {'brief':brief,'ui_language':'ca'}
        agent = N(pack=pack,system_prompt='')
        refresh_guidance(agent,state,{},None)
        original = copy.deepcopy(state)
        self.assertIsNone(refresh_guidance(agent,state,{},None))
        self.assertEqual(state,original)
        agent.pack = Pack(pack.path,{**pack.manifest,'version':'1.1.1'},'next-hash')
        self.assertIsNotNone(refresh_guidance(agent,state,{},None))
        changed = copy.deepcopy(state)
        self.assertIsNone(refresh_guidance(agent,state,{},None))
        self.assertEqual(state,changed)
        self.assertNotEqual(state['system_prompt'],original['system_prompt'])

    def test_glossary_protects_quotes_code_negatives_and_original(self):
        glossary = load_pack().data('glossary/ca.yaml')
        original = [{'role':'user','content':'assistents "assistent" `assistent` assistència'}]
        saved = copy.deepcopy(original)
        copy_for_model = model_messages(original,glossary)
        self.assertEqual(original,saved)
        self.assertEqual(copy_for_model[0]['content'],'assistents (en:assistant) "assistent" `assistent` assistència')
