import asyncio,json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from lamb.aac.liteshell.shell import LiteShell,prepare_command
from lamb.aac.authorization import ActionAuthorizer


def test_owned_reference_is_a_confirmed_metadata_binding_not_filesystem_access():
    http=SimpleNamespace(get=AsyncMock(return_value={'valid':True}),post=AsyncMock(return_value={'id':1}),put=AsyncMock())
    shell=LiteShell('', 'fixture', 'owner@test', 1, _http_client=http)
    async def run():
        command='lamb assistant create Grounded --rag-processor single_file_rag --file-reference 7/aac_owned.txt'
        assert ActionAuthorizer().check(prepare_command(command)[0])=='ask'
        result=await shell.execute(command)
        assert result.success,result.error
        http.get.assert_awaited_once_with('/creator/aac/files/validate',params={'reference':'7/aac_owned.txt'})
        assert json.loads(http.post.call_args.kwargs['json']['metadata'])['file_path']=='7/aac_owned.txt'
        http.get.return_value={'id':1,'name':'Grounded','metadata':json.dumps({'rag_processor':'single_file_rag','unchanged':'keep'})}
        result=await shell.execute('lamb assistant update 1 --file-reference 7/aac_new.txt')
        assert result.success,result.error
        metadata=json.loads(http.put.call_args.kwargs['json']['metadata'])
        assert metadata['file_path']=='7/aac_new.txt' and metadata['unchanged']=='keep'
    asyncio.run(run())
    with pytest.raises(ValueError,match='[Ll]ite[Ss]hell|filesystem'):
        prepare_command('lamb assistant create Grounded --file-path /etc/passwd')


@pytest.mark.parametrize('reference',['/etc/passwd','8/other.txt','7/../8/other.txt'])
def test_failed_owner_validation_prevents_any_create(reference):
    http=SimpleNamespace(get=AsyncMock(side_effect=ValueError('Not an owned document')),post=AsyncMock())
    shell=LiteShell('', 'fixture', 'owner@test', 1, _http_client=http)
    result=asyncio.run(shell.execute(f'lamb assistant create Grounded --file-reference {reference}'))
    assert not result.success
    http.post.assert_not_awaited()
