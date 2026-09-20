import json
import shlex
from unittest.mock import patch
from typer.testing import CliRunner
from lamb_cli.main import app

runner = CliRunner()


def test_news_uses_lamb_connection_and_preserves_course_and_timezone_arguments():
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value = {'coverage': {'complete': False}}
        result = runner.invoke(app, ['moodle', 'news', '--course', '1', '--course', '2', '--month', '2026-09', '--tz', 'Europe/Madrid'])
        assert result.exit_code == 0, result.output
        call = client.return_value.__enter__.return_value.post.call_args
        assert call.args == ('/creator/moodle/tasks',)
        tokens = shlex.split(call.kwargs['json']['command'])
        assert tokens.count('--course') == 2
        assert tokens[-2:] == ['--month', '2026-09']
        assert 'Europe/Madrid' in tokens
        assert json.loads(result.output)['coverage']['complete'] is False
        timeout = client.call_args.kwargs['timeout']
        assert timeout.connect == 5 and timeout.read == 120


def test_evidence_passes_returned_cursor_to_server():
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value = {'next_offset': None}
        result = runner.invoke(app, ['moodle', 'evidence', '11111111-1111-4111-8111-111111111111', '--offset', '8'])
        assert result.exit_code == 0, result.output
        assert client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'].endswith('--offset 8')


def test_continuation_and_recovery_use_the_same_authenticated_task_endpoint():
    for args, expected in [(['continue', '11111111-1111-4111-8111-111111111111'],
                            'moodle continue 11111111-1111-4111-8111-111111111111'),
                           (['runs'], 'moodle runs')]:
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {'continue_command': None}
            result = runner.invoke(app, ['moodle', *args])
            assert result.exit_code == 0, result.output
            call = client.return_value.__enter__.return_value.post.call_args
            assert call.args == ('/creator/moodle/tasks',)
            assert call.kwargs['json']['command'] == expected


def test_document_commands_use_owned_session_and_exact_review_handle():
    commands = [
        (['page', 'list', '10'], 'moodle page list 10'),
        (['book', 'list', '10'], 'moodle book list 10'),
        (['import', 'page', 'md_opaque', '--single-file'], 'moodle import page md_opaque --single-file'),
        (['import', 'book', 'md_opaque', '--to', 'kb', '12'], 'moodle import book md_opaque --to kb 12'),
        (['import', 'file', 'mf_opaque', '--to', 'kb', '12'], 'moodle import file mf_opaque --to kb 12'),
        (['import', 'check', 'receipt', '--verify-content'], 'moodle import check receipt --verify-content'),
        (['import', 'refresh', 'receipt', '--confirm', 'review'], 'moodle import refresh receipt'),
    ]
    for args, expected in commands:
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {'status': 'test'}
            result = runner.invoke(app, ['moodle', *args, '--session', 'owned-session'])
            assert result.exit_code == 0, result.output
            call = client.return_value.__enter__.return_value.post.call_args
            assert call.args == ('/creator/moodle/documents/commands',)
            assert call.kwargs['json'] == {'session': 'owned-session', 'command': expected,
                                          'confirm': 'review' if '--confirm' in args else None}


def test_document_session_is_required_and_start_is_authenticated():
    assert runner.invoke(app, ['moodle', 'page', 'list', '10']).exit_code != 0
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value = {'session': 'owned'}
        result = runner.invoke(app, ['moodle', 'documents', 'start'])
        assert result.exit_code == 0, result.output
        client.return_value.__enter__.return_value.post.assert_called_once_with('/creator/moodle/documents/sessions')


def test_folder_and_nested_file_options_reach_shared_backend_unchanged():
    examples = [
        (['folder', 'list', '10'], ['folder', 'list', '10']),
        (['course', 'contents', '10'], ['course', 'contents', '10']),
        (['file', 'list', '22', '--component', 'mod_folder', '--filepath', '/Unit 1/deep/', '--itemid', '0'],
         ['file', 'list', '22', '--component', 'mod_folder', '--filearea', 'content', '--filepath', '/Unit 1/deep/', '--itemid', '0']),
        (['folder', 'inspect', 'ref', '--path', '/Unit 1/', '--exclude', '/Unit 1/old/'],
         ['folder', 'inspect', 'ref', '--path', '/Unit 1/', '--exclude', '/Unit 1/old/']),
        (['import', 'folder', 'ref', '--to', 'kb', '12', '--exclude', '/a.md', '--exclude', '/b.md', '--confirm', 'review'],
         ['import', 'folder', 'ref', '--path', '/', '--exclude', '/a.md', '--exclude', '/b.md', '--to', 'kb', '12']),
        (['folder', 'status', 'batch'], ['folder', 'status', 'batch']),
        (['folder', 'finish', 'batch', '--confirm', 'batch'], ['folder', 'finish', 'batch'])]
    for args, expected in examples:
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {}
            result = runner.invoke(app, ['moodle', *args, '--session', 'owned'])
            assert result.exit_code == 0, result.output
            body = client.return_value.__enter__.return_value.post.call_args.kwargs['json']
            assert shlex.split(body['command']) == ['moodle', *expected]
            assert body['session'] == 'owned'
            assert body['confirm'] == (args[args.index('--confirm') + 1] if '--confirm' in args else None)
