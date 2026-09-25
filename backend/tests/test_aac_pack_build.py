"""Build failures prevent stale UI vocabulary and unusable workflow packs."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N
import unittest
from lamb.aac.pack_build import generate_ui_glossaries, validate_routing
from lamb.aac.pack_loader import load_pack
from lamb.aac.contract import validate_skill_contracts
from lamb.aac.capability_lint import validate_capability_prose, processor_catalog
from lamb.aac.pack_loader import docs_root


class BuildTests(unittest.TestCase):
    def test_full_command_parser_rejects_missing_args_and_invalid_values(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            file = directory/'example.md'
            pack = N(skills_dir=directory)
            for command in ['lamb assistant get', 'lamb kb query 1 question --top-k',
                            'frontend-manage open assistant 1 --tab made-up',
                            'lamb assistant create Example --rag-top-k -1']:
                file.write_text('```aac-command\n'+command+'\n```')
                with self.subTest(command=command), self.assertRaises(ValueError): validate_skill_contracts(pack)
            file.write_text('`frontend-manage open rubric RUBRIC_ID`')
            self.assertTrue(validate_skill_contracts(pack))

    def test_named_capabilities_must_exist_in_registry_metadata(self):
        pack = load_pack()
        catalog = pack.data('capability-catalog.json')
        for category, entries in processor_catalog().items():
            self.assertEqual(catalog[category], entries)
        self.assertIn('simple_rag', validate_capability_prose(pack, docs_root(), catalog))
        catalog['rag_processors'] = [item for item in catalog['rag_processors'] if item['id'] != 'simple_rag']
        with self.assertRaisesRegex(ValueError, 'absent from registry metadata: simple_rag'):
            validate_capability_prose(pack, docs_root(), catalog)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'invented.md').write_text('Select Quantum Rag or `quantum_rag`.')
            with self.assertRaisesRegex(ValueError, 'quantum_rag'):
                validate_capability_prose(pack, root)

    def test_glossary_build_uses_canonical_ui_keys_and_preserves_authored_terms(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack, locales = root/'pack', root/'locales'
            (pack/'glossary').mkdir(parents=True)
            locales.mkdir()
            (pack/'glossary/ui-keys.json').write_text(json.dumps(['nav.assistants']))
            terms = [{'english': 'assistant', 'forms': ['authored']}]
            for code, label in [('en', 'Assistants'), ('es', 'Asistentes'), ('ca', 'Assistents'), ('eu', 'Laguntzaileak')]:
                (locales/f'{code}.json').write_text(json.dumps({'nav': {'assistants': label}}))
                (pack/f'glossary/{code}.yaml').write_text(json.dumps({'language': code, 'ui': {'old': 'stale'}, 'terms': terms}))
            generate_ui_glossaries(pack, locales)
            output = json.loads((pack/'glossary/ca.yaml').read_text())
            self.assertEqual(output['ui'], {'nav.assistants': 'Assistents'})
            self.assertEqual(output['terms'], terms)
            (locales/'ca.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Missing frontend glossary key'): generate_ui_glossaries(pack, locales)

    def test_routing_rejects_unknown_commands_skills_and_invalid_layers(self):
        pack = load_pack()
        validate_routing(pack)
        for defect in ('bootstrap', 'default', 'capability', 'hint', 'layer'):
            routing = copy.deepcopy(pack.data('routing.yaml'))
            metadata = copy.deepcopy(pack.manifest)
            if defect == 'bootstrap': routing['BOOTSTRAP'].append('invented.command')
            if defect == 'default': routing['DEFAULT_SKILL']['assistant.get'] = 'configure-agent'
            if defect == 'capability': routing['CAPABILITIES']['create-assistant'].append('invented.command')
            if defect == 'hint': routing['USER_ROUTING']['rules'][0]['skill'] = 'missing-skill'
            if defect == 'layer': metadata['skill_layers']['test-lti-tools'] = 'root'
            candidate = N(skills_dir=pack.skills_dir, manifest=metadata, data=lambda _: routing)
            with self.subTest(defect=defect), self.assertRaises(ValueError): validate_routing(candidate)
