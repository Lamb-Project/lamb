import asyncio
from urllib.parse import parse_qs
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from lamb.aac.liteshell.shell import LiteShell
from lamb.moodle.contract import command_specs


@respx.mock
def test_catalogue_metadata_uses_connected_account_and_propagates_moodle_denial(stores):
    rt=runtime(stores);seen=[]
    def respond(request):
        p=parse_qs(request.content.decode());seen.append(p)
        if p['wsfunction']==['core_course_get_categories']:
            return Response(200,json=[{'id':1,'name':'Teaching'}])
        assert p['wsfunction']==['core_cohort_get_cohorts']
        return Response(200,json={'exception':'required_capability_exception','errorcode':'nopermissions','message':'Cohort view permission required'})
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    async def run():
        result=await shell.execute('moodle course categories')
        assert result.success and result.data[0]['name']=='Teaching'
        result=await shell.execute('moodle cohort list')
        assert not result.success and 'permission' in result.error
    asyncio.run(run())
    assert len(seen)==2 and all(p['wstoken']==['fixture'] for p in seen)
    assert all('userid' not in p for p in seen)


def test_all_installed_remote_reads_are_exposed_when_connected(stores):
    keys=runtime(stores).available()
    assert {'moodle.'+key for key,spec in command_specs().items() if spec.policy=='auto'}<=keys
