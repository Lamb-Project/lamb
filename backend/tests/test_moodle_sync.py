from urllib.parse import parse_qs
import pytest
import respx
from httpx import Response
from moodle_cli.client.http import MoodleHTTPClient
from lamb.moodle.cache import CourseCache
from lamb.moodle.sync import sync_course


@respx.mock
def test_full_sync_then_forum_delta_keeps_standing_threads_and_other_sections(tmp_path):
    generation=[0]
    def respond(request):
        body=parse_qs(request.content.decode());fn=body['wsfunction'][0]
        answers={
            'core_enrol_get_users_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'core_user_get_course_user_profiles':[{'id':7,'roles':[{'shortname':'teacher'}]}],
            'core_course_get_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'mod_forum_get_forums_by_courses':[{'id':20,'course':10,'name':'Questions'}],
            'mod_forum_get_forum_discussions':{'discussions':[{'id':90,'discussion':30,'userid':8,'usermodified':8,'numreplies':0}]+
                                             ([{'id':91,'discussion':31,'userid':8}] if generation[0] else [])},
            'mod_assign_get_assignments':{'courses':[{'id':10,'assignments':[{'id':40,'course':10,'name':'Demo work'}]}]},
            'mod_assign_get_submissions':{'assignments':[{'assignmentid':40,'submissions':[{'id':50,'userid':8,'status':'submitted','gradingstatus':'notgraded'}]}]},
            'core_enrol_get_enrolled_users':[{'id':7,'roles':[{'shortname':'teacher'}]},{'id':8,'lastcourseaccess':123}],
            'core_calendar_get_action_events_by_course':{'events':[{'id':60,'name':'Deadline','courseid':10}]},
        }
        assert fn in answers,fn
        return Response(200,json=answers[fn])
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    cache=CourseCache(1,7,base_url='https://moodle.test',moodle_user_id=7,root=tmp_path)
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True) as client:
        first=sync_course(client,cache,10)
        generation[0]=1
        second=sync_course(client,cache,10,'forums')
    assert len(first['sections'])==5
    assert second['sections']['forums']['delta']['new']==1
    snapshot=cache.read(10)
    assert len(snapshot['sections']['forums']['data'][0]['discussions'])==2
    assert snapshot['sections']['enrolment']['synced_at']==first['sections']['enrolment']['synced_at']
    assert snapshot['sections']['assignments']['data'][0]['submissions'][0]['gradingstatus']=='notgraded'
