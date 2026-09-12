"""Continuation must send saved conversation to the model and reject foreign chat IDs."""
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock,Mock,patch
from fastapi import HTTPException
from creator_interface import learning_assistant_proxy as proxy

class Continuation(unittest.IsolatedAsyncioTestCase):
    async def request(self,chat,body):
        service=Mock()
        service.get_chat.return_value=chat
        service.add_user_message_and_create_if_needed.return_value={'chat_id':'saved'}
        completion=AsyncMock(return_value={'choices':[{'message':{'content':'violet'}}]})
        auth=N(user={'id':7,'email':'owner@test'},can_access_assistant=Mock(return_value='owner'))
        with patch.object(proxy,'chats_service',service),patch.object(proxy,'run_lamb_assistant',completion):
            try:
                result=await proxy.proxy_assistant_chat(25,N(json=AsyncMock(return_value=body)),auth)
            except HTTPException:
                service.add_user_message_and_create_if_needed.assert_not_called()
                completion.assert_not_awaited()
                raise
        return result,service,completion

    def saved(self,**kwargs):
        return dict(user_id=7,assistant_id=25,chat={'history':{'messages':{
            'q':{'role':'user','content':'My private marker is violet','timestamp':1},
            'a':{'role':'assistant','content':'Remembered','timestamp':2}
        }}},**kwargs)

    async def test_single_followup_includes_saved_history(self):
        _,_,completion=await self.request(self.saved(),{'chat_id':'saved','messages':[{'role':'user','content':'What marker?'}]})
        self.assertEqual(completion.call_args.kwargs['request']['messages'],[
            {'role':'user','content':'My private marker is violet'},
            {'role':'assistant','content':'Remembered'},
            {'role':'user','content':'What marker?'}])

    async def test_full_client_history_is_not_duplicated(self):
        messages=[{'role':'user','content':'Prior'},{'role':'assistant','content':'Answer'},{'role':'user','content':'Next'}]
        _,_,completion=await self.request(self.saved(),{'chat_id':'saved','messages':messages})
        self.assertEqual(completion.call_args.kwargs['request']['messages'],messages)

    async def test_foreign_missing_and_wrong_assistant_rejected(self):
        for chat in [None,{**self.saved(),'user_id':8},{**self.saved(),'assistant_id':250}]:
            with self.subTest(chat=chat):
                with self.assertRaises(HTTPException) as err:
                    await self.request(chat,{'chat_id':'saved','messages':[{'role':'user','content':'Next'}]})
                self.assertEqual(err.exception.status_code,404)
