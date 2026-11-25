"""Validate, build and promote knowledge packs.

  python -m lamb.aac.pack_build                 check the workspace and every installed pack
  python -m lamb.aac.pack_build --write         regenerate the workspace (glossaries, guide list, hashes)
  python -m lamb.aac.pack_build --start 2.1     begin a version: the workspace becomes 2.1-beta.1
  python -m lamb.aac.pack_build --bump          a new beta replaces the previous one (2.1-beta.2)
  python -m lamb.aac.pack_build --promote rc    the beta becomes the release candidate
  python -m lamb.aac.pack_build --promote stable   the release candidate becomes stable; the old stable becomes legacy

One beta, one release candidate, one stable and two legacy packs at most. Git keeps the rest.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from lamb.aac.pack_loader import (Pack, packs_root, docs_root, load_pack, read_pack, installed_lines, parse_version, about,
                                  ABOUT, WORKSPACE, SUMMARY_LIMIT)
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
    """Reject unusable recipes at build time. Guides are checked where they exist; a command
    needs none (issue #567), and which role may run a command is LAMB's policy, not the pack's."""
    import re
    from lamb.aac.skill_loader import list_skills, _parse_skill_file
    from lamb.aac.liteshell.shell import COMMAND_CONTRACTS
    skills = {item['id'] for item in list_skills(pack.skills_dir)}
    commands = set(COMMAND_CONTRACTS)
    layers = {'creator', 'lti', 'org_admin', 'admin'}
    routing = pack.data('routing.yaml')
    if any(key.startswith('moodle.') for key in routing['DEFAULT_SKILL']):
        from lamb.moodle.contract import command_specs
        from lamb.moodle.task_contract import task_specs
        from lamb.moodle.document_contract import document_specs
        commands |= {'moodle.' + key for key in document_specs() if 'moodle.' + key in routing['DEFAULT_SKILL']}
        # Packs before 1.11.8 predate the LAMB course inventory read (#521).
        commands |= {'moodle.'+key for key in command_specs()
                     if key != 'course.inventory' or 'moodle.course.inventory' in routing['DEFAULT_SKILL']} | {'moodle.sync','moodle.cache.show','moodle.import.file'}
        # Historical immutable packs predate the task vocabulary.
        if 'moodle.news' in routing['DEFAULT_SKILL']:
            commands |= {'moodle.'+key for key in task_specs() if 'moodle.'+key in routing['DEFAULT_SKILL']}
    if pack.manifest.get('command_layers'):
        raise ValueError('A pack cannot assign commands to roles; that policy lives in lamb.aac.authorization.COMMAND_LAYERS')
    for key, layer in pack.manifest.get('skill_layers', {}).items():
        if key not in skills or layer not in layers:
            raise ValueError(f'Invalid layer assignment: skill_layers/{key}/{layer}')
    if not set(routing['BOOTSTRAP']) <= commands:
        raise ValueError('Routing bootstrap names an unknown command')
    for skill, capabilities in routing['CAPABILITIES'].items():
        if skill not in skills or not set(capabilities) <= commands:
            raise ValueError(f'Invalid workflow capabilities: {skill}')
    for command, skill in routing['DEFAULT_SKILL'].items():
        if command not in commands or command not in routing['CAPABILITIES'].get(skill, []):
            raise ValueError(f'Default workflow cannot execute command: {command}/{skill}')
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


def validate_question_bank(path):
    bank = json.loads(path.read_text())
    # pack_version names the release the bank was last evaluated on; that pack may be retired since.
    if bank['version'] != 'qa-1.1' or not isinstance(bank.get('pack_version'), str):
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


GUIDES = 'Guides in this version'
REQUIRED_SECTIONS = ('What this version is for', 'What changed', GUIDES)
AUDIENCE = {'creator': 'Every creator', 'lti': 'Creators who arrive from the LMS',
            'org_admin': 'Organization administrators', 'admin': 'System administrators'}


def guides_table(pack):
    """The guide list of ABOUT.md, generated from the pack so that it cannot drift from it."""
    from lamb.aac.skill_loader import list_skills
    assignments = pack.manifest.get('skill_layers', {})
    cell = lambda text: str(text).replace('|', '/').replace('\n', ' ').strip()
    rows = ['| Guide | What it helps with | For | Needs |', '|---|---|---|---|']
    for skill in sorted(list_skills(pack.skills_dir), key=lambda item: item['id']):
        rows.append(f"| `{skill['id']}` | {cell(skill['description'])} | {AUDIENCE[assignments.get(skill['id'], 'creator')]} | "
                    f"{'Moodle connected' if skill.get('requires_integration') == 'moodle' else ''} |")
    return '\n'.join(rows)


def about_sections(document):
    """{heading: body} for the second-level headings of a pack document."""
    parts = re.split(r'^## (.+)$', document, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


def write_guides(pack):
    """Replace the generated guide list in the workspace document."""
    file = pack.path / ABOUT
    text = file.read_text(encoding='utf-8')
    pattern = re.compile(rf'(^## {re.escape(GUIDES)}\n)(.*?)(?=^## |\Z)', flags=re.M | re.S)
    if not pattern.search(text):
        raise ValueError(f'{ABOUT} needs a "## {GUIDES}" section')
    file.write_text(pattern.sub(lambda m: m.group(1) + '\n' + guides_table(pack) + '\n\n', text).rstrip('\n') + '\n', encoding='utf-8')


def validate_about(pack):
    """Every pack tells an organization administrator what it is and what changed."""
    summary, document = about(pack)
    if not summary or len(summary) > SUMMARY_LIMIT:
        raise ValueError(f'Pack {pack.version}: {ABOUT} must start with a summary line of at most {SUMMARY_LIMIT} characters')
    sections = about_sections(document)
    for heading in REQUIRED_SECTIONS:
        if not sections.get(heading):
            raise ValueError(f'Pack {pack.version}: {ABOUT} needs a "## {heading}" section')
    if sections[GUIDES] != guides_table(pack):
        raise ValueError(f'Pack {pack.version}: the guide list in {ABOUT} is out of date; run the build with --write')


def check_installed(root=None):
    """Only the packs named in lines.yaml are present, each verified and documented."""
    root = Path(root or packs_root()).resolve()
    lines = installed_lines(root)
    releases = root / 'releases' / 'lamb-default'
    present = {d.name for d in releases.iterdir() if d.is_dir()} if releases.is_dir() else set()
    expected = {lines[line] for line in ('stable', 'legacy-1', 'legacy-2', 'rc')} - {None}
    if present != expected:
        raise ValueError(f'Installed packs differ from lines.yaml: unexpected {sorted(present - expected)}, missing {sorted(expected - present)}')
    workspace = read_pack(root / WORKSPACE)
    if lines['beta'] and (workspace is None or workspace.version != lines['beta']):
        raise ValueError(f"The beta line names {lines['beta']} but the workspace holds {getattr(workspace, 'version', 'nothing')}")
    for line in ('rc', 'beta'):
        if lines[line] and parse_version(lines[line])[:3] <= parse_version(lines['stable'])[:3]:
            raise ValueError(f'The {line} pack {lines[line]} is not newer than the stable {lines["stable"]}; start the next version')
    checked = []
    for version in sorted(expected | ({lines['beta']} - {None})):
        pack = load_pack(version=version, root=root)
        validate_about(pack)
        checked.append(version)
    return {'lines': lines, 'verified': checked}


def write_lines(root, lines):
    # Versions are quoted: YAML would read 2.0 as a number, and 2.10 as 2.1.
    quoted = lambda v: f'"{v}"' if v else 'null'
    legacy = ', '.join(quoted(v) for v in (lines['legacy-1'], lines['legacy-2']) if v)
    (root / 'lines.yaml').write_text(
        '# Which knowledge pack each line holds. An organization follows a line, never a version.\n'
        '# Only the packs named here are installed; `python -m lamb.aac.pack_build` refuses any other.\n'
        '# Change this file with the build commands (--start, --bump, --promote), not by hand.\n'
        f"stable: {quoted(lines['stable'])}    # the pack shipped with this LAMB version\n"
        f"legacy: [{legacy}]    # at most two: the stable packs of the two previous LAMB versions\n"
        f"rc: {quoted(lines['rc'])}    # one release candidate, or none\n"
        f"beta: {quoted(lines['beta'])}    # the pack being written in {WORKSPACE}/, or none\n")


def _stamp(path, version):
    manifest = json.loads((path / 'manifest.yaml').read_text())
    manifest['version'] = version
    (path / 'manifest.yaml').write_text(json.dumps(manifest, indent=2) + '\n')


def _base(version):
    major, minor = parse_version(version)[:2]
    return f'{major}.{minor}'


def start(version, root=None):
    """Begin writing a version: the workspace becomes VERSION-beta.1."""
    root = Path(root or packs_root()).resolve()
    lines = installed_lines(root)
    if not re.fullmatch(r'\d+\.\d+', version) or parse_version(version)[:3] <= parse_version(lines['stable'])[:3]:
        raise ValueError(f'Start a version above the stable {lines["stable"]}, written as two numbers')
    lines['beta'] = f'{version}-beta.1'
    _stamp(root / WORKSPACE, lines['beta'])
    write_lines(root, lines)
    return lines


def bump(root=None):
    """A new beta replaces the previous one. Git keeps what it was."""
    root = Path(root or packs_root()).resolve()
    lines = installed_lines(root)
    if not lines['beta']:
        raise ValueError('No beta is being written; start a version first')
    lines['beta'] = f"{_base(lines['beta'])}-beta.{parse_version(lines['beta'])[4] + 1}"
    _stamp(root / WORKSPACE, lines['beta'])
    write_lines(root, lines)
    return lines


def promote(target, root=None):
    """beta -> rc copies the workspace into a frozen release; rc -> stable retires the oldest legacy."""
    root = Path(root or packs_root()).resolve()
    lines = installed_lines(root)
    releases = root / 'releases' / 'lamb-default'
    if target == 'rc':
        if not lines['beta']:
            raise ValueError('There is no beta to promote')
        validate_about(load_pack(version=lines['beta'], root=root))
        same = lines['rc'] and _base(lines['rc']) == _base(lines['beta'])
        new = f"{_base(lines['beta'])}-rc.{parse_version(lines['rc'])[4] + 1 if same else 1}"
        shutil.copytree(root / WORKSPACE, releases / new)
        _stamp(releases / new, new)
        if lines['rc']:
            shutil.rmtree(releases / lines['rc'])
        lines['rc'] = new
    elif target == 'stable':
        if not lines['rc']:
            raise ValueError('There is no release candidate to promote')
        new = _base(lines['rc'])
        shutil.copytree(releases / lines['rc'], releases / new)
        _stamp(releases / new, new)
        shutil.rmtree(releases / lines['rc'])
        if lines['legacy-2']:
            shutil.rmtree(releases / lines['legacy-2'])
        lines.update({'legacy-2': lines['legacy-1'], 'legacy-1': lines['stable'], 'stable': new, 'rc': None})
        if lines['beta'] and _base(lines['beta']) == new:
            lines['beta'] = None  # that version is released; start the next one to write again
    else:
        raise ValueError('Promote to rc or to stable')
    write_lines(root, lines)
    return lines


def content_hashes(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob('*')) if p.is_file() and str(p.relative_to(path)) not in ('manifest.yaml', ABOUT)}


def rehash(root=None):
    """Record the workspace content in its manifest and refresh its generated guide list."""
    path = Path(root or packs_root()).resolve() / WORKSPACE
    manifest = json.loads((path / 'manifest.yaml').read_text())
    manifest['hashes'] = content_hashes(path)
    (path / 'manifest.yaml').write_text(json.dumps(manifest, indent=2) + '\n')
    write_guides(read_pack(path))
    return read_pack(path)


def build(write=False):
    path=packs_root()/WORKSPACE
    if write:
        generate_ui_glossaries(path, packs_root().parent.parent/'frontend/svelte-app/src/lib/locales')
        (path/'capability-catalog.json').write_text(json.dumps(source_catalog(), ensure_ascii=False, indent=2)+'\n')
        rehash()
        doc_manifest_path = docs_root()/'manifest.json'
        doc_manifest = json.loads(doc_manifest_path.read_text())
        doc_manifest.update(content_metadata(docs_root(), doc_manifest))
        doc_manifest_path.write_text(json.dumps(doc_manifest, ensure_ascii=False, indent=2)+'\n')
    hashes=content_hashes(path)
    pack=read_pack(path)
    installed=check_installed()
    validate_skill_contracts(pack)
    validate_routing(pack)
    check_references(pack)
    stored_catalog = pack.data('capability-catalog.json')
    for category, entries in processor_catalog().items():
        if stored_catalog.get(category) != entries:
            raise ValueError(f'Capability catalogue differs from module metadata: {category}')
    references = validate_capability_prose(pack, docs_root())
    qa_cells = validate_question_bank(packs_root()/'qa-1.1/bank.json')
    return {'version':pack.version,'hash':pack.fingerprint,'files':len(hashes),'qa_cells':qa_cells,'capability_references':references,
            'docs_coverage':json.loads((docs_root()/'manifest.json').read_text())['coverage'], **installed}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--start',metavar='VERSION')
    parser.add_argument('--bump',action='store_true')
    parser.add_argument('--promote',choices=['rc','stable'])
    options=parser.parse_args()
    if options.start: start(options.start)
    if options.bump: bump()
    if options.promote: promote(options.promote)
    print(json.dumps(build(options.write),indent=2))
