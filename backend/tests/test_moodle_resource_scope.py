import asyncio
from urllib.parse import parse_qs
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from lamb.aac.liteshell.shell import LiteShell


def setup(stores):
    rt=runtime(stores);calls=[];present=[True]
    def reply(request):
        p=parse_qs(request.content.decode());fn=p['wsfunction'][0];calls.append(fn)
        responses={
            'core_enrol_get_users_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'core_user_get_course_user_profiles':[{'id':70,'roles':[{'shortname':'teacher'}]}],
            'core_course_get_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'core_course_get_contents':[{'id':1,'name':'Section','modules':[
                {'id':20,'instance':30,'modname':'quiz','contextid':200},
                {'id':21,'instance':31,'modname':'resource','contextid':201}]}],
            'core_enrol_get_enrolled_users':[{'id':70},{'id':80}],
            'mod_quiz_get_user_attempts':{'attempts':[{'id':50,'quiz':30,'userid':80}] if present[0] else []},
            'mod_quiz_get_attempt_review':{'questions':[{'id':1,'response':'Fixture answer'}]},
            'core_files_get_files':{'files':[{'filename':'lesson.txt','fileurl':'https://moodle.test/webservice/pluginfile.php/201/mod_resource/content/0/lesson.txt'}]},
        }
        assert fn in responses,fn
        return Response(200,json=responses[fn])
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    return LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available()),calls,present


@respx.mock
def test_review_requires_listed_attempt_and_revalidates_it(stores):
    shell,calls,present=setup(stores)
    async def run():
        await shell.execute('moodle course get 10')
        assert not (await shell.execute('moodle quiz review 50')).success
        assert 'mod_quiz_get_attempt_review' not in calls
        assert (await shell.execute('moodle quiz attempts 30 --user-id 80')).success
        result=await shell.execute('moodle quiz review 50')
        assert result.success,result.error
        present[0]=False
        assert not (await shell.execute('moodle quiz review 50')).success
        assert calls.count('mod_quiz_get_attempt_review')==1
    asyncio.run(run())


@respx.mock
def test_file_context_and_area_must_belong_to_course_module(stores):
    shell,calls,_=setup(stores)
    async def run():
        await shell.execute('moodle course get 10')
        for flags in ['999 --component mod_resource --filearea content',
                      '201 --component user --filearea private']:
            assert not (await shell.execute('moodle file list '+flags)).success
        assert 'core_files_get_files' not in calls
        result=await shell.execute('moodle file list 201 --component mod_resource --filearea content')
        assert result.success,result.error
        assert result.data[0]['filename']=='lesson.txt'
    asyncio.run(run())
