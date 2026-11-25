"""Immutable, hash-verified AAC content packs. Paths may be mounted outside the image."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import yaml

BACKEND = Path(__file__).resolve().parents[2]
ENGINE_VERSION = '0.9.0'


def packs_root():
    return Path(os.environ.get('LAMB_AAC_PACKS_DIR', BACKEND / 'aac-packs')).resolve()


def docs_root():
    return Path(os.environ.get('LAMB_AGENT_DOCS_DIR', BACKEND / 'agent-docs')).resolve()


def version_tuple(value):
    """A LAMB engine version, three numbers."""
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Invalid LAMB version')
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


# -- lines ----------------------------------------------------------------------------
# An organization follows a line, never an exact version (Marc, 25 November 2026). At most
# five packs are installed: the stable one shipped with this LAMB version, the stable packs
# of the two previous LAMB versions, one release candidate and one beta. Git has the rest.
LINES = ('stable', 'legacy-1', 'legacy-2', 'rc', 'beta')
DEV_LINES = ('rc', 'beta')  # offered only to an organization in development mode
WORKSPACE = 'lamb-default'  # where the beta is written; every other pack is a frozen release
ABOUT = 'ABOUT.md'          # written for people, never sent to the model, outside the content hashes
SUMMARY_LIMIT = 240


def parse_version(value):
    """Order a pack version: '1.13.6' or '2.0' (stable), '2.0-rc.1', '2.0-beta.4'."""
    match = re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?(?:-(beta|rc)\.(\d+))?', value) if isinstance(value, str) else None
    if not match:
        raise ValueError('Invalid pack version')
    major, minor, patch, stage, number = match.groups()
    return (int(major), int(minor), int(patch or 0), {'beta': 0, 'rc': 1, None: 2}[stage], int(number or 0))


def installed_lines(root=None):
    """Which version each line holds, from lines.yaml; None where a line is empty."""
    root = Path(root or packs_root()).resolve()
    data = yaml.safe_load((root / 'lines.yaml').read_text()) or {}
    legacy = data.get('legacy') or []
    if not isinstance(legacy, list) or len(legacy) > 2:
        raise ValueError('At most two legacy packs are kept')
    lines = {'stable': data.get('stable'), 'legacy-1': legacy[0] if legacy else None,
             'legacy-2': legacy[1] if len(legacy) > 1 else None, 'rc': data.get('rc') or None, 'beta': data.get('beta') or None}
    if not lines['stable']:
        raise ValueError('No stable knowledge pack is installed; ask the administrator')
    for line, version in lines.items():
        if version is not None and not isinstance(version, str):
            raise ValueError('Write pack versions in quotes in lines.yaml')
        if version is not None and parse_version(version)[3] != {'beta': 0, 'rc': 1}.get(line, 2):
            raise ValueError(f'The {line} line cannot hold pack {version}')
    return lines


def development_mode(settings):
    """Whether the organization asked to see the rc and beta lines. A channel saved before the
    switch existed counts as having asked."""
    if 'pack_dev_mode' in settings:
        return settings['pack_dev_mode'] is True
    return 'pack_line' not in settings and settings.get('pack_channel') in DEV_LINES


def selected_line(settings):
    """The line an organization follows. Settings saved before the lines existed held a channel,
    which becomes the line, and sometimes an exact version, which is no longer honoured."""
    line = settings.get('pack_line') or settings.get('pack_channel') or 'stable'
    if line not in LINES or (line in DEV_LINES and not development_mode(settings)):
        return 'stable'
    return line


def read_pack(path, version=None):
    """Verify one pack directory. None when it is absent or holds another version than asked."""
    file = path / 'manifest.yaml'
    if not file.is_file():
        return None
    manifest = yaml.safe_load(file.read_text())
    if version is not None and manifest.get('version') != version:
        return None
    parse_version(manifest.get('version'))
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
    actual = {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()} - {'manifest.yaml', ABOUT}
    if actual != set(hashes):
        raise ValueError('Pack contains unlisted or missing content')
    for relative, digest in hashes.items():
        item = path / relative
        if item.is_symlink() or not item.resolve().is_relative_to(path.resolve()) or not item.is_file():
            raise ValueError(f'Unsafe or missing pack file: {relative}')
        if hashlib.sha256(item.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Pack content changed without a release: {relative}')
    return Pack(path, manifest, hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest())


def load_pack(settings=None, *, version=None, root=None):
    root = Path(root or packs_root()).resolve()
    lines = installed_lines(root)
    # An empty line (no release candidate now, no second legacy pack) follows stable.
    selected = version or lines[selected_line(settings or {})] or lines['stable']
    parse_version(selected)
    # The beta is the workspace itself; every other pack is a frozen release.
    for path in ([root / WORKSPACE] if selected == lines['beta'] else []) + [root / 'releases' / 'lamb-default' / selected]:
        pack = read_pack(path, selected)
        if pack:
            return pack
    raise ValueError(f'AAC pack {selected} is not installed; ask the administrator')


def about(pack):
    """(summary, document) of a pack's ABOUT.md; empty strings when it has none."""
    file = pack.path / ABOUT
    if not file.is_file() or file.is_symlink():
        return '', ''
    text = file.read_text(encoding='utf-8')
    match = re.match(r'---\nsummary: (.+)\n---\n', text)
    return (match.group(1).strip(), text[match.end():].lstrip('\n')) if match else ('', text)


def lines_view(root=None):
    """What an administrator chooses from: each line with its version, summary and document."""
    lines, warnings, rows = installed_lines(root), [], []
    for line in LINES:
        row = {'line': line, 'version': lines[line], 'development': line in DEV_LINES, 'summary': '', 'about': ''}
        if lines[line]:
            try:
                row['summary'], row['about'] = about(load_pack(version=lines[line], root=root))
            except (ValueError, OSError) as exc:
                row['version'] = None
                warnings.append(f'The {line} knowledge pack could not be verified: {exc}')
        rows.append(row)
    return rows, warnings


def allowed_skills(pack, layers, integrations=None):
    """Guides shown to these role layers. Presentation only: what may run is LAMB's decision."""
    from lamb.aac.skill_loader import list_skills
    assignments = pack.manifest.get('skill_layers', {'test-lti-tools':'admin'})
    return {s['id'] for s in list_skills(pack.skills_dir) if assignments.get(s['id'],'creator') in layers
            and (integrations is None or not s.get('requires_integration') or s['requires_integration'] in integrations)}


def render_prefix(pack, brief):
    from lamb.aac.brief import render_brief
    from lamb.aac.contract import command_reference
    from lamb.aac.skill_routing import catalogue_prompt
    from lamb.aac.authorization import allowed_commands
    if pack.manifest.get('compatibility') == 'legacy-prefix':
        return pack.text('persona.md') + catalogue_prompt(pack.skills_dir)
    layers = brief['layers']
    parts = [render_brief(brief), pack.text('persona.md'), pack.text('compass.md')]
    for layer in layers:
        for file in pack.manifest['layers'].get(layer, []):
            parts.append(pack.text(file))
    parts.append(command_reference(allowed_commands(layers)))
    parts.append(catalogue_prompt(pack.skills_dir, allowed_skills(pack,layers,integrations=())))
    return '\n\n'.join(parts)
