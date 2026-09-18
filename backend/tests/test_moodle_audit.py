from types import SimpleNamespace
from lamb.moodle.audit import command_artifacts
from tests.test_aac_legacy import agent


def test_forum_proposal_and_saved_reply_have_explicit_phases_and_ids():
    a,_,_=agent([])
    command='moodle forum reply --post-id 7 --subject "A subject" --message "A reply"'
    a._record_audit(command,'moodle.forum.reply',True,0,None,queued=True)
    queued=a.tool_audit[-1]
    assert queued['phase']=='awaiting_confirmation'
    assert queued['artifacts']==[{'type':'moodle_post','id':None,'action':'reply','parent_post_id':7}]
    a._record_audit(command,'moodle.forum.reply',True,20,SimpleNamespace(data={'post_id':8}))
    saved=a.tool_audit[-1]
    assert saved['phase']=='completed'
    assert saved['artifacts'][0]['id']==8
    a._record_interrupted(command,'moodle.forum.reply')
    assert a.tool_audit[-1]['phase']=='interrupted'
    assert a.tool_audit[-1]['outcome']=='unknown'


def test_grade_and_import_artifacts_identify_the_actual_resource():
    command='moodle assign grade --assignment-id 2 --user-id 4 --grade 80 --feedback "Good" --rationale "Source evidence"'
    artifacts=command_artifacts(command,None)
    assert artifacts==[{'type':'moodle_assignment','id':2,'action':'grade','user_id':4}]
    artifacts=command_artifacts('moodle import file mf_example --to kb 3',None)
    assert artifacts==[{'type':'kb','id':3,'action':'import','source_file_id':'mf_example'}]
