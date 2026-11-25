"""Knowledge pack lines: an organization follows stable, a legacy pack, rc or beta, never a version.

Marc, 25 November 2026: "stable, rc and beta (are the terms)"; "org admin has to ckeck that he is
in dev mode to select rc and beta, otherwise only sees stable"; "we add numbering to the alpha, but
we only keep the last one"; "we will keep the two latest stable as legacy, the rest goest into oblivion".
"""
import copy
import json
import shutil
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from lamb.aac import pack_build
from lamb.aac.pack_loader import (load_pack, packs_root, installed_lines, selected_line, development_mode, parse_version,
                                  about, lines_view, LINES, SUMMARY_LIMIT)
from lamb.aac.preferences import validate_settings


@pytest.fixture
def packs(tmp_path, monkeypatch):
    """A private copy of the installed packs, so that a test may start, bump and promote."""
    root = tmp_path / 'aac-packs'
    shutil.copytree(packs_root(), root)
    monkeypatch.setenv('LAMB_AAC_PACKS_DIR', str(root))
    return root


def test_the_tree_holds_only_the_packs_its_lines_name_and_each_is_documented():
    report = pack_build.check_installed()
    lines = installed_lines()
    assert lines['stable'] and report['lines'] == lines
    releases = {d.name for d in (packs_root() / 'releases' / 'lamb-default').iterdir() if d.is_dir()}
    assert releases == {lines[line] for line in ('stable', 'legacy-1', 'legacy-2', 'rc')} - {None}
    assert len(releases) + bool(lines['beta']) <= 5
    assert not (packs_root() / 'channels.yaml').exists()
    for version in report['verified']:
        summary, document = about(load_pack(version=version))
        assert 0 < len(summary) <= SUMMARY_LIMIT
        assert '## What changed' in document and '| Guide | What it helps with | For | Needs |' in document


def test_versions_order_beta_before_rc_before_stable():
    ordered = ['1.13.6', '2.0-beta.1', '2.0-beta.12', '2.0-rc.1', '2.0', '2.1-beta.1']
    assert sorted(ordered, key=parse_version) == ordered
    for bad in ['2', '2.0-alpha.1', '2.0-rc', '../2.0', '', None, '2.0.0.1']:
        with pytest.raises(ValueError):
            parse_version(bad)


def test_an_organization_follows_a_line_and_needs_development_mode_for_rc_and_beta(packs):
    pack_build.start('2.0', packs)
    stable, beta = installed_lines()['stable'], installed_lines()['beta']
    assert beta == '2.0-beta.1'
    assert load_pack().version == load_pack({}).version == load_pack({'pack_line': 'stable'}).version == stable
    assert load_pack({'pack_line': 'beta', 'pack_dev_mode': True}).version == beta
    # Without development mode the rc and beta lines are not followed, whatever was stored.
    assert load_pack({'pack_line': 'beta'}).version == stable
    assert load_pack({'pack_line': 'beta', 'pack_dev_mode': False}).version == stable
    # An empty line follows stable: there is no release candidate and no legacy pack yet.
    assert load_pack({'pack_line': 'rc', 'pack_dev_mode': True}).version == stable
    assert load_pack({'pack_line': 'legacy-1'}).version == load_pack({'pack_line': 'legacy-2'}).version == stable


def test_settings_saved_before_the_lines_existed_are_read_as_a_line():
    for stored, line, development in [({}, 'stable', False),
                                      ({'pack_channel': 'stable', 'pack_version': ''}, 'stable', False),
                                      ({'pack_channel': 'stable', 'pack_version': '1.0.0'}, 'stable', False),
                                      ({'pack_channel': 'beta', 'pack_version': ''}, 'beta', True),
                                      ({'pack_channel': 'rc', 'pack_version': '1.11.17'}, 'rc', True)]:
        assert (selected_line(stored), development_mode(stored)) == (line, development)
        checked = validate_settings(stored, {})
        assert (checked['pack_line'], checked['pack_dev_mode']) == (line, development)
        assert 'pack_channel' not in checked and 'pack_version' not in checked


def test_what_an_administrator_may_save():
    assert validate_settings({'pack_line': 'beta', 'pack_dev_mode': True}, {})['pack_line'] == 'beta'
    assert validate_settings({'pack_line': 'legacy-1'}, {})['pack_dev_mode'] is False
    for refused in [{'pack_line': 'beta'}, {'pack_line': 'rc', 'pack_dev_mode': False}, {'pack_line': '1.13.6'},
                    {'pack_line': 'stable', 'pack_dev_mode': 1}]:
        with pytest.raises(ValueError):
            validate_settings(refused, {})
    # Leaving development mode while on beta returns the organization to stable.
    assert validate_settings({'pack_channel': 'beta', 'pack_dev_mode': False}, {})['pack_line'] == 'stable'


def test_a_new_beta_replaces_the_previous_one_and_a_candidate_is_a_frozen_copy(packs):
    releases = packs / 'releases' / 'lamb-default'
    stable = installed_lines()['stable']
    with pytest.raises(ValueError, match='above the stable'):
        pack_build.start('1.0', packs)
    assert pack_build.start('2.0', packs)['beta'] == '2.0-beta.1'
    assert pack_build.bump(packs)['beta'] == '2.0-beta.2'
    with pytest.raises(ValueError, match='not installed'):
        load_pack(version='2.0-beta.1')
    assert {d.name for d in releases.iterdir()} == {stable}, 'a beta is the workspace, never a kept release'

    assert pack_build.promote('rc', packs)['rc'] == '2.0-rc.1'
    candidate = load_pack({'pack_line': 'rc', 'pack_dev_mode': True})
    assert candidate.version == '2.0-rc.1' and candidate.path == releases / '2.0-rc.1'
    # Work goes on in the beta without touching the candidate.
    (packs / 'lamb-default' / 'compass.md').write_text((packs / 'lamb-default' / 'compass.md').read_text() + '\nMore.\n')
    pack_build.bump(packs)
    pack_build.rehash(packs)
    assert load_pack(version='2.0-rc.1').text('compass.md') != load_pack(version='2.0-beta.3').text('compass.md')
    assert pack_build.promote('rc', packs)['rc'] == '2.0-rc.2'
    assert {d.name for d in releases.iterdir()} == {stable, '2.0-rc.2'}, 'only the last candidate is kept'


def test_promotion_to_stable_keeps_two_legacy_packs_and_forgets_the_rest(packs):
    releases = packs / 'releases' / 'lamb-default'
    first = installed_lines()['stable']
    history = [first]
    for version in ['2.0', '2.1', '3.0']:
        pack_build.start(version, packs)
        pack_build.promote('rc', packs)
        lines = pack_build.promote('stable', packs)
        history.insert(0, version)
        assert lines['stable'] == version and lines['rc'] is None and lines['beta'] is None
        assert [lines['legacy-1'], lines['legacy-2']] == (history[1:3] + [None, None])[:2]
        assert {d.name for d in releases.iterdir()} == set(history[:3])
        pack_build.check_installed(packs)
    assert load_pack({'pack_line': 'legacy-1'}).version == '2.1' and load_pack({'pack_line': 'legacy-2'}).version == '2.0'
    with pytest.raises(ValueError, match='not installed'):
        load_pack(version=first)
    # A pack that no line names is refused, so the tree cannot grow back to forty-eight versions.
    shutil.copytree(releases / '3.0', releases / '2.5')
    with pytest.raises(ValueError, match="unexpected \\['2.5'\\]"):
        pack_build.check_installed(packs)


def test_a_pack_without_its_document_or_with_a_stale_guide_list_is_refused(packs):
    pack_build.start('2.0', packs)
    document = packs / 'lamb-default' / 'ABOUT.md'
    good = document.read_text()
    for broken, message in [(good.replace('## What changed', '## Changes'), 'What changed'),
                            (good.replace('summary: ', 'summary: ' + 'x' * SUMMARY_LIMIT), 'summary line'),
                            (good.replace('| `about-lamb` |', '| `about-lamb-renamed` |'), 'out of date')]:
        document.write_text(broken)
        with pytest.raises(ValueError, match=message):
            pack_build.promote('rc', packs)
    document.write_text(good)
    assert pack_build.promote('rc', packs)['rc'] == '2.0-rc.1'


def test_the_settings_screen_gets_each_line_with_its_summary_document_and_the_tools_of_this_lamb(packs):
    from creator_interface import organization_router as r
    from tests.aac_knowledge_fixtures import CONFIG
    pack_build.start('2.0', packs)
    config = copy.deepcopy(CONFIG)
    config['setups']['default']['aac'] = {'pack_channel': 'stable', 'pack_version': '1.0.0'}
    auth = N(user={'id': 1, 'email': 'admin@school.example', 'name': 'Admin'}, is_system_admin=False, is_org_admin=True,
             organization={'id': 7, 'slug': 'own', 'config': config}, organization_role='admin')
    db = Mock()
    db.update_organization_config.return_value = True
    request = N(headers={'Authorization': 'Bearer token'})

    import asyncio
    with patch.object(r, '_build_auth_context', return_value=auth), patch.object(r, 'db_manager', db):
        data = asyncio.run(r.get_agent_settings(request))
        rows = {row['line']: row for row in data['pack_lines']}
        assert list(rows) == list(LINES)
        assert rows['stable']['version'] == installed_lines()['stable'] and rows['stable']['summary'] and '## What changed' in rows['stable']['about']
        assert rows['beta']['version'] == '2.0-beta.1' and rows['beta']['development'] and not rows['stable']['development']
        assert rows['rc']['version'] is None and rows['legacy-1']['version'] is None
        assert data['settings']['pack_line'] == 'stable' and data['settings']['pack_dev_mode'] is False
        assert 'pack_version' not in data['settings'] and 'pack_channel' not in data['settings']
        # The exact version saved earlier is named once, so the administrator knows it is no longer followed.
        assert data['pack_notice'] == {'retired_version': '1.0.0', 'line': 'stable'}
        assert '- lamb assistant create' in data['tools_reference']

        with pytest.raises(HTTPException) as refused:
            asyncio.run(r.update_agent_settings(request, {'pack_line': 'beta'}))
        assert refused.value.status_code == 400 and 'development mode' in refused.value.detail
        saved = asyncio.run(r.update_agent_settings(request, {'pack_line': 'beta', 'pack_dev_mode': True}))
        assert saved['settings']['pack_line'] == 'beta'
        stored = db.update_organization_config.call_args.args[1]['setups']['default']['aac']
        assert stored['pack_line'] == 'beta' and 'pack_version' not in stored and 'pack_channel' not in stored
        auth.organization['config'] = db.update_organization_config.call_args.args[1]
        assert asyncio.run(r.get_agent_settings(request))['pack_notice'] is None
