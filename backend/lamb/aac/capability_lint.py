"""Build-time provenance checks for named capabilities in authored agent content.

This checks named processor/plugin references, not the truth of pedagogical prose.
Judgments remain subject to the question bank and human review. Session availability
continues to come from the live registries, never this build-time source catalogue.
"""
import ast
import json
from pathlib import Path
import re

BACKEND = Path(__file__).resolve().parents[2]


def literal_assignments(nodes):
    result = {}
    for node in nodes:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = node.value.value
    return result


def processor_catalog(backend=BACKEND):
    catalog = {}
    for category, directory in [('rag_processors', 'rag'), ('prompt_processors', 'pps'), ('connectors', 'connectors')]:
        catalog[category] = []
        for path in sorted((backend/'lamb/completions'/directory).glob('*.py')):
            if path.name == '__init__.py':
                continue
            description = literal_assignments(ast.parse(path.read_text()).body).get('AAC_DESCRIPTION')
            if not isinstance(description, str) or not description.strip() or '\n' in description:
                raise ValueError(f'Missing module-owned capability description: {directory}/{path.name}')
            catalog[category].append({'id':path.stem, 'description':description})
    return catalog


def source_catalog(backend=BACKEND):
    catalog = processor_catalog(backend)
    plugin_dir = backend.parent/'lamb-kb-server-stable/backend/plugins'
    if not plugin_dir.is_dir():
        raise ValueError('Generating capability references requires the KB plugin source checkout')
    catalog['ingestion_plugins'] = []
    for path in sorted(plugin_dir.glob('*.py')):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.ClassDef) or 'PluginRegistry.register' not in [ast.unparse(d) for d in node.decorator_list]:
                continue
            fields = literal_assignments(node.body)
            if not fields.get('name') or not fields.get('description'):
                raise ValueError(f'Missing registered ingestion-plugin metadata: {path.name}')
            catalog['ingestion_plugins'].append({'id':fields['name'], 'description':fields['description']})
    return catalog


def validate_capability_prose(pack, documentation_root, catalog=None):
    catalog = catalog if catalog is not None else pack.data('capability-catalog.json')
    known = {item['id'] for items in catalog.values() for item in items}
    errors = []
    references = set()
    paths = [p for p in pack.path.rglob('*.md')] + list(documentation_root.rglob('*.md'))
    for path in paths:
        text = path.read_text()
        names = set(re.findall(r'\b[a-z][a-z0-9_-]*(?:_rag|_ingest|_augment)\b', text))
        # UI display names are derived from processor identifiers, not a second
        # hand-maintained list of available algorithms.
        names.update(match.lower().replace(' ', '_') for match in re.findall(r'\b(?:[A-Z][a-z]+ ){1,3}Rag\b', text))
        for name in names:
            references.add(name)
            if name not in known:
                errors.append(f'{path.name}: capability is absent from registry metadata: {name}')
    if errors:
        raise ValueError('\n'.join(errors))
    return sorted(references)
