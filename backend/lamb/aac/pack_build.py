"""Validate/build authored AAC content; run python -m lamb.aac.pack_build [--write]."""
import argparse
import hashlib
import json
from pathlib import Path
from lamb.aac.pack_loader import Pack, packs_root, docs_root, load_pack
from lamb.aac.contract import validate_skill_contracts
from lamb.aac.documentation import validate_docs, sections, content_metadata
from lamb.aac.capability_lint import source_catalog, processor_catalog, validate_capability_prose


def generate_ui_glossaries(path, locale_root):
    """Build canonical key/label entries; retain separately authored domain terms."""
    keys = json.loads((path/'glossary/ui-keys.json').read_text())
    if not isinstance(keys, list) or len(keys) != len(set(keys)):
        raise ValueError('UI glossary keys must be a unique list')
    for code in ('en', 'es', 'ca', 'eu'):
        bundle = locale_root/f'{code}.json'
        if not bundle.is_file():
            raise ValueError(f'Generating glossaries requires the frontend locale bundle: {bundle}')
        source = json.loads(bundle.read_text())
        labels = {}
        for key in keys:
            value = source
            for part in key.split('.'):
                if not isinstance(value, dict) or part not in value:
                    raise ValueError(f'Missing frontend glossary key: {code}/{key}')
                value = value[part]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'Frontend glossary label must be text: {code}/{key}')
            labels[key] = value
        target = path/'glossary'/f'{code}.yaml'
        glossary = json.loads(target.read_text())
        glossary['ui'] = labels
        target.write_text(json.dumps(glossary, ensure_ascii=False, indent=2)+'\n')


def validate_routing(pack):
    """Reject unusable recipes and invalid layer assignments at build time."""
    import re
    from lamb.aac.skill_loader import list_skills, _parse_skill_file
    from lamb.aac.liteshell.shell import COMMAND_CONTRACTS
    skills = {item['id'] for item in list_skills(pack.skills_dir)}
    commands = set(COMMAND_CONTRACTS)
    layers = {'creator', 'lti', 'org_admin', 'admin'}
    routing = pack.data('routing.yaml')
    for field, known in [('skill_layers', skills), ('command_layers', commands)]:
        for key, layer in pack.manifest.get(field, {}).items():
            if key not in known or layer not in layers:
                raise ValueError(f'Invalid layer assignment: {field}/{key}/{layer}')
    if not set(routing['BOOTSTRAP']) <= commands:
        raise ValueError('Routing bootstrap names an unknown command')
    for skill, capabilities in routing['CAPABILITIES'].items():
        if skill not in skills or not set(capabilities) <= commands:
            raise ValueError(f'Invalid workflow capabilities: {skill}')
    for command, skill in routing['DEFAULT_SKILL'].items():
        if command not in commands or command not in routing['CAPABILITIES'].get(skill, []):
            raise ValueError(f'Default workflow cannot execute command: {command}/{skill}')
    if commands - set(routing['BOOTSTRAP']) - set(routing['DEFAULT_SKILL']):
        raise ValueError('Installed commands are missing workflow coverage')
    hints = routing.get('USER_ROUTING', {})
    for pattern in [hints.get('negative', ''), hints.get('assistant_id', ''),
                    *hints.get('read_only_constraints', []), *hints.get('facts', {}).values()]:
        re.compile(pattern)
    for rule in hints.get('rules', []):
        re.compile(rule['pattern'])
        if rule['skill'] not in skills:
            raise ValueError(f'Unknown routed workflow: {rule["skill"]}')
        for name in rule.get('all_facts', []) + rule.get('any_facts', []) + rule.get('exclude_facts', []):
            if name not in {*hints.get('facts', {}), 'linked_assistant'}:
                raise ValueError(f'Unknown routing fact: {name}')
    assignments = pack.manifest.get('skill_layers', {})
    for file in pack.skills_dir.glob('*.md'):
        meta, _ = _parse_skill_file(file)
        for included in meta.get('includes', []):
            if included not in skills:
                raise ValueError(f'Unknown included skill: {included}')
            if assignments.get(included, 'creator') not in {'creator', assignments.get(meta['id'], 'creator')}:
                raise ValueError(f'Skill include crosses role layers: {meta["id"]}/{included}')


def validate_question_bank(path, pack):
    bank = json.loads(path.read_text())
    if bank['version'] != 'qa-1.1' or bank['pack_version'] != pack.version:
        raise ValueError('Question bank must identify the tested pack release')
    if set(bank['locales']) != {'en', 'es', 'ca', 'eu'} or not bank.get('evaluator_model'):
        raise ValueError('Question bank requires four locales and one fixed evaluator')
    expected_roles = {(kind, administration) for kind in ('creator', 'lti_creator') for administration in ('none', 'org_admin', 'admin')}
    if {(r['creator_kind'], r['administration']) for r in bank['roles']} != expected_roles:
        raise ValueError('Question bank role matrix is incomplete')
    anchors = {anchor for topic in json.loads((docs_root()/'manifest.json').read_text())['topics'].values() for anchor in topic['anchors']}
    ids = set()
    for case in bank['cases']:
        if case['id'] in ids or not case['criteria'] or set(case['prompts']) != set(bank['locales']):
            raise ValueError(f'Incomplete question bank case: {case["id"]}')
        ids.add(case['id'])
        if case.get('expected_anchor') and case['expected_anchor'] not in anchors:
            raise ValueError(f'Unknown question bank anchor: {case["expected_anchor"]}')
        if 'ca' not in case.get('zero_translate_locales', []):
            raise ValueError('Catalan acceptance must forbid translate calls')
    if not bank['human_review'].get('acceptance_requires_review'):
        raise ValueError('Model grades cannot substitute for human acceptance')
    return len(bank['cases']) * len(bank['roles']) * len(bank['locales'])


def check_references(pack):
    import re
    metadata=json.loads((docs_root()/'manifest.json').read_text())
    for file in pack.skills_dir.glob('*.md'):
        for topic, anchor in re.findall(r'lamb docs read ([a-z][a-z0-9-]*) --section ["\']?([a-z][a-z0-9-]*)',file.read_text()):
            if topic not in metadata['topics'] or anchor not in metadata['topics'][topic]['anchors']:
                raise ValueError(f'Unknown documentation anchor: {file.name}: {topic}/{anchor}')
    for code in ('en','es','ca','eu'):
        glossary=pack.data(f'glossary/{code}.yaml')
        if glossary.get('language')!=code or len(glossary.get('terms',[]))<12 or not glossary.get('ui'):
            raise ValueError(f'Incomplete locale glossary: {code}')
        forms=[f.casefold() for term in glossary['terms'] for f in term['forms']]
        if len(forms)!=len(set(forms)):
            raise ValueError(f'Ambiguous glossary forms: {code}')
        from lamb.aac.glossary import vocabulary
        vocabulary(glossary)
        # Build-time check only: the runtime image needs no frontend source checkout.
        bundle=packs_root().parent.parent/'frontend/svelte-app/src/lib/locales'/f'{code}.json'
        if bundle.is_file():
            ui=json.loads(bundle.read_text())
            for key,label in glossary['ui'].items():
                value=ui
                for part in key.split('.'):value=value[part]
                if value!=label:raise ValueError(f'UI glossary drift: {code}/{key}')
    validate_docs()


def build(write=False):
    path=packs_root()/'lamb-default'
    manifest=json.loads((path/'manifest.yaml').read_text())
    if write:
        generate_ui_glossaries(path, packs_root().parent.parent/'frontend/svelte-app/src/lib/locales')
        (path/'capability-catalog.json').write_text(json.dumps(source_catalog(), ensure_ascii=False, indent=2)+'\n')
    hashes={str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob('*')) if p.is_file() and p.name!='manifest.yaml'}
    if write:
        manifest['hashes']=hashes
        (path/'manifest.yaml').write_text(json.dumps(manifest,indent=2)+'\n')
        doc_manifest_path = docs_root()/'manifest.json'
        doc_manifest = json.loads(doc_manifest_path.read_text())
        doc_manifest.update(content_metadata(docs_root(), doc_manifest))
        doc_manifest_path.write_text(json.dumps(doc_manifest, ensure_ascii=False, indent=2)+'\n')
    pack=load_pack(version=manifest['version'])
    validate_skill_contracts(pack)
    validate_routing(pack)
    check_references(pack)
    stored_catalog = pack.data('capability-catalog.json')
    for category, entries in processor_catalog().items():
        if stored_catalog.get(category) != entries:
            raise ValueError(f'Capability catalogue differs from module metadata: {category}')
    references = validate_capability_prose(pack, docs_root())
    qa_cells = validate_question_bank(packs_root()/'qa-1.1/bank.json', pack)
    return {'version':pack.version,'hash':pack.fingerprint,'files':len(hashes),'qa_cells':qa_cells,'capability_references':references,'docs_coverage':json.loads((docs_root()/'manifest.json').read_text())['coverage']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true')
    print(json.dumps(build(parser.parse_args().write),indent=2))
