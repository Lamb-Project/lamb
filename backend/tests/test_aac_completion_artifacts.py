"""Durable collection progress is not a chart artifact."""
from types import SimpleNamespace
import pytest
from lamb.aac.agent.loop import _extract_artifacts


@pytest.mark.parametrize('command',[
    'moodle analytics run activity-completion --course 7',
    'moodle analytics continue 00000000-0000-0000-0000-000000000001 --step 1',
])
def test_progress_and_publication_have_distinct_artifacts(command):
    progress={'run_id':'run','processed_students':25,'continue_command':'next'}
    assert _extract_artifacts(command,SimpleNamespace(success=True,data=progress))==[]
    chart={'chart_id':'saved','title':'Completion'}
    assert _extract_artifacts(command,SimpleNamespace(success=True,data=chart))==[
        {'type':'chart','id':'saved','title':'Completion'}]
    assert not any(item['type']=='chart' for item in
        _extract_artifacts(command,SimpleNamespace(success=False,data=chart)))


def test_submission_chart_artifact_is_preserved():
    assert _extract_artifacts('moodle chart submissions --course 7',
        SimpleNamespace(success=True,data={'chart_id':'saved','title':'Submissions'}))==[
            {'type':'chart','id':'saved','title':'Submissions'}]
