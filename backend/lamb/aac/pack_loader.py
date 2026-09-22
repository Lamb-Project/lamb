"""Immutable, hash-verified AAC content packs. Paths may be mounted outside the image."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import yaml

BACKEND = Path(__file__).resolve().parents[2]
ENGINE_VERSION = '0.7.18'


def packs_root():
    return Path(os.environ.get('LAMB_AAC_PACKS_DIR', BACKEND / 'aac-packs')).resolve()


def docs_root():
    return Path(os.environ.get('LAMB_AGENT_DOCS_DIR', BACKEND / 'agent-docs')).resolve()


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Invalid pack version')
    return tuple(map(int, value.split('.')))


@dataclass(frozen=True)
class Pack:
    path: Path
    manifest: dict
    fingerprint: str

    @property
    def version(self):
        return self.manifest['version']

    @property
    def skills_dir(self):
        return self.path / 'skills'

    def text(self, relative):
        if relative not in self.manifest['hashes']:
            raise ValueError('Content is not in the pack manifest')
        return (self.path / relative).read_text(encoding='utf-8')

    def data(self, relative):
        return yaml.safe_load(self.text(relative))


def load_pack(settings=None, *, version=None, root=None):
    root = Path(root or packs_root()).resolve()
    settings = settings or {}
    channels = yaml.safe_load((root / 'channels.yaml').read_text())
    selected = version or settings.get('pack_version') or channels.get(settings.get('pack_channel', 'stable'))
    version_tuple(selected)
    candidates = [root / 'lamb-default', root / 'releases' / 'lamb-default' / selected]
    for path in candidates:
        file = path / 'manifest.yaml'
        if not file.is_file():
            continue
        manifest = yaml.safe_load(file.read_text())
        if manifest.get('version') != selected:
            continue
        requirement = manifest.get('requires', '')
        match = re.fullmatch(r'lamb >= (\d+\.\d+(?:\.\d+)?)', requirement)
        if not match:
            raise ValueError('Pack must declare requires: lamb >= VERSION')
        minimum = match.group(1)
        if minimum.count('.') == 1:
            minimum += '.0'
        if version_tuple(ENGINE_VERSION) < version_tuple(minimum):
            raise ValueError('Pack requires a newer LAMB engine')
        hashes = manifest.get('hashes', {})
        if not hashes:
            raise ValueError('Pack manifest has no content hashes')
        required = {'persona.md', 'compass.md', 'routing.yaml'} | {f'glossary/{language}.yaml' for language in ('en','es','ca','eu')}
        if not required <= hashes.keys():
            raise ValueError('Pack is missing required content or a locale glossary')
        actual = {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p.name != 'manifest.yaml'}
        if actual != set(hashes):
            raise ValueError('Pack contains unlisted or missing content')
        for relative, digest in hashes.items():
            item = path / relative
            if item.is_symlink() or not item.resolve().is_relative_to(path.resolve()) or not item.is_file():
                raise ValueError(f'Unsafe or missing pack file: {relative}')
            if hashlib.sha256(item.read_bytes()).hexdigest() != digest:
                raise ValueError(f'Pack content changed without a release: {relative}')
        fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        return Pack(path, manifest, fingerprint)
    raise ValueError(f'AAC pack {selected} is not installed; ask the administrator')


def allowed_skills(pack, layers, integrations=None):
    from lamb.aac.skill_loader import list_skills
    assignments = pack.manifest.get('skill_layers', {'test-lti-tools':'admin'})
    return {s['id'] for s in list_skills(pack.skills_dir) if assignments.get(s['id'],'creator') in layers
            and (integrations is None or not s.get('requires_integration') or s['requires_integration'] in integrations)}


def allowed_commands(pack, layers):
    from lamb.aac.liteshell.shell import COMMAND_CONTRACTS
    assignments = pack.manifest.get('command_layers', {})
    return {key for key in COMMAND_CONTRACTS if assignments.get(key,'creator') in layers}


def render_prefix(pack, brief):
    from lamb.aac.brief import render_brief
    from lamb.aac.contract import command_reference
    from lamb.aac.skill_routing import catalogue_prompt
    if pack.manifest.get('compatibility') == 'legacy-prefix':
        return pack.text('persona.md') + catalogue_prompt(pack.skills_dir)
    layers = brief['layers']
    parts = [render_brief(brief), pack.text('persona.md'), pack.text('compass.md')]
    for layer in layers:
        for file in pack.manifest['layers'].get(layer, []):
            parts.append(pack.text(file))
    parts.append(command_reference(allowed_commands(pack,layers)))
    parts.append(catalogue_prompt(pack.skills_dir, allowed_skills(pack,layers,integrations=())))
    return '\n\n'.join(parts)
