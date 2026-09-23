import json
import shlex
from unittest.mock import patch
from typer.testing import CliRunner
from lamb_cli.main import app

runner = CliRunner()


def test_forum_run_start_forward_exact_scope_and_calendar_bounds():
    for verb in ('run','start'):
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value={'run_id':'saved'}
            result=runner.invoke(app,['moodle','analytics',verb,'forum-participation','--course','7',
                '--forum','8','--since','2025-10-25','--through','2025-10-26','--tz','Europe/Madrid','--group','3'])
            assert result.exit_code==0,result.output
            tokens=shlex.split(client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'])
            for flag,value in [('--forum','8'),('--since','2025-10-25'),('--through','2025-10-26'),('--group','3')]:
                assert tokens[tokens.index(flag)+1]==value


def test_quiz_run_and_start_forward_exact_policy_and_scope():
    for verb in ('run', 'start'):
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {'run_id': 'saved'}
            result = runner.invoke(app, ['moodle', 'analytics', verb, 'quiz-overview', '--course', '9',
                '--quiz', '7', '--attempt-policy', 'all_finished', '--group', '3'])
            assert result.exit_code == 0, result.output
            tokens = shlex.split(client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'])
            for flag, value in [('--quiz','7'), ('--attempt-policy','all_finished'), ('--group','3')]:
                assert tokens[tokens.index(flag)+1] == value


def test_inclusive_window_is_forwarded_without_cli_date_reinterpretation():
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value={'calendar_days':92,'collection_supported':False}
        result=runner.invoke(app,['moodle','analytics','window','--since','2026-06-01',
            '--through','2026-08-31','--tz','Europe/Madrid'])
        assert result.exit_code==0,result.output
        tokens=shlex.split(client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'])
        assert tokens==['moodle','analytics','window','--since','2026-06-01','--tz','Europe/Madrid','--through','2026-08-31']
        result=runner.invoke(app,['moodle','analytics','run','view-trends','--course','7',
            '--since','2026-08-01','--through','2026-08-31','--tz','Europe/Madrid'])
        assert result.exit_code==0,result.output
        tokens=shlex.split(client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'])
        assert tokens[tokens.index('--through')+1]=='2026-08-31'


def test_view_trends_uses_authenticated_analytics_task_with_window_and_group():
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value={'chart_id':'saved'}
        result=runner.invoke(app,['moodle','analytics','run','view-trends','--course','7',
            '--since','2026-09-01','--until','2026-09-20','--group','2','--tz','Europe/Madrid'])
        assert result.exit_code==0,result.output
        call=client.return_value.__enter__.return_value.post.call_args
        assert call.args==('/creator/moodle/tasks',)
        tokens=shlex.split(call.kwargs['json']['command'])
        assert tokens[:4]==['moodle','analytics','run','view-trends']
        for flag,value in [('--course','7'),('--since','2026-09-01'),('--until','2026-09-20'),('--group','2')]:
            assert tokens[tokens.index(flag)+1]==value


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
        (['import', 'folder', 'ref', '--new-kb', 'Teacher readings', '--description', 'For teachers', '--confirm', 'review'],
         ['import', 'folder', 'ref', '--path', '/', '--new-kb', 'Teacher readings', '--description', 'For teachers']),
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


def test_ingestion_options_forwarded_for_all_sources_and_refresh():
    for kind in ('file', 'page', 'book', 'folder', 'refresh'):
        args = ['import', kind, 'ref'] + ([] if kind == 'refresh' else ['--to', 'kb', '12'])
        args += ['--chunk-size', '2000', '--chunk-overlap', '0', '--splitter-type', 'TokenTextSplitter']
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {}
            result = runner.invoke(app, ['moodle', *args, '--session', 'owned', '--confirm', 'review'])
            assert result.exit_code == 0, result.output
            body = client.return_value.__enter__.return_value.post.call_args.kwargs['json']
            tokens = shlex.split(body['command'])
            assert tokens[tokens.index('--chunk-size') + 1] == '2000'
            assert tokens[tokens.index('--chunk-overlap') + 1] == '0'
            assert tokens[tokens.index('--splitter-type') + 1] == 'TokenTextSplitter'
            assert body['confirm'] == 'review' and body['session'] == 'owned'


def test_chart_recipe_uses_same_readonly_task_contract():
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value = {'chart_id': 'saved'}
        result = runner.invoke(app, ['moodle', 'chart', 'submissions', '--course', '7', '--tz', 'Europe/Madrid', '--language', 'es'])
        assert result.exit_code == 0, result.output
        assert client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'] == 'moodle chart submissions --course 7 --tz Europe/Madrid --language es'
        assert json.loads(result.output)['chart_id'] == 'saved'


def test_saved_chart_list_and_read_contracts():
    for args, command in [(['list','--offset','20'], 'moodle chart list --offset 20'),
                           (['read','saved-id'], 'moodle chart read saved-id')]:
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {'refreshed':False}
            result = runner.invoke(app, ['moodle','chart',*args])
            assert result.exit_code == 0, result.output
            assert client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command'] == command


def test_analytics_commands_share_authenticated_task_contract():
    examples = [
        (['run','deadlines','--course','7','--since','2026-10-01','--until','2026-11-01'],
         'moodle analytics run deadlines --course 7 --tz UTC --language en --since 2026-10-01 --until 2026-11-01'),
        (['start','activity-completion','--course','7','--language','es'],
         'moodle analytics start activity-completion --course 7 --tz UTC --language es'),
        (['continue','run-id','--step','2'],'moodle analytics continue run-id --step 2'),
        (['runs'],'moodle analytics runs'),
        (['run','activity-completion','--course','7'],
         'moodle analytics run activity-completion --course 7 --tz UTC --language en'),
        (['run','grade-distribution','--course','7','--assignment','42'],
         'moodle analytics run grade-distribution --course 7 --tz UTC --language en --assignment 42'),
        (['capabilities', '--course', '7'],
         'moodle analytics capabilities --course 7'),
        (['run', 'grading-queue', '--course', '7'],
         'moodle analytics run grading-queue --course 7 --tz UTC --language en'),
        (['run', 'course-access', '--course', '7', '--since', '2026-09-01',
          '--tz', 'Europe/Madrid', '--language', 'es'],
         'moodle analytics run course-access --course 7 --tz Europe/Madrid --language es --since 2026-09-01'),
        (['result', 'saved-id', '--offset', '20'],
         'moodle analytics result saved-id --offset 20'),
    ]
    for args, command in examples:
        with patch('lamb_cli.commands.moodle.get_client') as client:
            client.return_value.__enter__.return_value.post.return_value = {'refreshed': False}
            result = runner.invoke(app, ['moodle', 'analytics', *args])
            assert result.exit_code == 0, result.output
            call = client.return_value.__enter__.return_value.post.call_args
            assert call.args == ('/creator/moodle/tasks',)
            assert call.kwargs['json']['command'] == command
            assert json.loads(result.output)['refreshed'] is False


def test_analytics_rejects_invalid_local_bounds_without_request():
    for args in [['capabilities', '--course', '0'],
                 ['run', 'course-access', '--course', '-1'],
                 ['result', 'saved-id', '--offset', '-1']]:
        with patch('lamb_cli.commands.moodle.get_client') as client:
            assert runner.invoke(app, ['moodle', 'analytics', *args]).exit_code != 0
            client.assert_not_called()


def test_resource_reach_forwards_group_and_exclusive_date_boundary():
    with patch('lamb_cli.commands.moodle.get_client') as client:
        client.return_value.__enter__.return_value.post.return_value={}
        result=runner.invoke(app,['moodle','analytics','run','resource-reach','--course','9',
            '--since','2026-09-01','--until','2026-09-22','--group','2'])
        assert result.exit_code == 0, result.output
        command=client.return_value.__enter__.return_value.post.call_args.kwargs['json']['command']
        assert shlex.split(command)[-6:] == ['--since','2026-09-01','--until','2026-09-22','--group','2']
