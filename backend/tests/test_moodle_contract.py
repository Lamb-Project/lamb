import pytest
from moodle_cli.cli.readonly import READONLY_COMMANDS
from lamb.moodle.contract import command_specs, prepare_moodle, command_reference, CURATED_WRITES


def test_generated_contract_exactly_covers_installed_remote_reads_and_curated_writes():
    expected = {f'{g}.{c}' for g,names in READONLY_COMMANDS.items() if g != 'auth' for c in names}
    specs = command_specs()
    assert set(specs) == expected | CURATED_WRITES
    assert all(specs[k].policy == 'auto' for k in expected)
    assert all(specs[k].policy == 'ask' for k in CURATED_WRITES)


def test_typed_parser_uses_installed_arguments_options_and_required_fields():
    spec, params = prepare_moodle('moodle forum posts 42')
    assert spec.key == 'forum.posts' and params == {'discussion_id':42}
    _, params = prepare_moodle('moodle forum reply --post-id 7 --message "Hello teacher"')
    assert params == {'post_id':7,'subject':'Re:','message':'Hello teacher'}
    for command in ['moodle forum posts nope','moodle forum posts 1 2','moodle forum reply --post-id 7',
                    'moodle forum posts 2 --profile admin','moodle call anything','moodle auth profiles',
                    'moodle forum delete 7']:
        with pytest.raises(ValueError):prepare_moodle(command)


def test_dynamic_reference_absent_without_connection_and_filters_writes():
    assert command_reference(enabled=True) == ''
    assert command_reference(connected=True) == ''
    reads = command_reference(enabled=True,connected=True)
    assert 'moodle forum posts' in reads and 'moodle forum reply' not in reads
    forum = command_reference(enabled=True,connected=True,write_groups=['forum'])
    assert 'moodle forum reply' in forum and 'moodle assign grade ' not in forum
    assert 'moodle assign grade ' in command_reference(enabled=True,connected=True,allow_grade_write=True)
