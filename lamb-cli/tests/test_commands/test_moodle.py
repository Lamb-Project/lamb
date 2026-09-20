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
