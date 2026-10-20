"""Scenario updates preserve omitted fields and cannot address another assistant."""
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from lamb.services import test_router as r
from lamb.aac.liteshell.commands import test_update as command_test_update
from lamb.aac.liteshell.shell import prepare_command
from lamb.aac.authorization import ActionAuthorizer

class ScenarioUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_and_delete_require_scenario_belongs_to_owned_assistant(self):
        for endpoint in [r.update_scenario,r.delete_scenario]:
            for scenario in [None,{'assistant_id':99}]:
                svc=Mock();svc.get_scenario.return_value=scenario;auth=Mock()
                with patch.object(r,'TestService',return_value=svc):
                    with self.assertRaises(HTTPException) as exc:
                        if endpoint==r.update_scenario:await endpoint(1,'foreign',N(json=AsyncMock(return_value={'expected_behavior':'changed'})),auth)
                        else:await endpoint(1,'foreign',auth)
                    self.assertEqual(exc.exception.status_code,404)
                    svc.update_scenario.assert_not_called();svc.delete_scenario.assert_not_called()
                    auth.require_assistant_access.assert_called_once_with(1,level='owner')

    async def test_owner_expected_only_update_passes_only_requested_field(self):
        svc=Mock();svc.get_scenario.return_value={'assistant_id':1}
        with patch.object(r,'TestService',return_value=svc):
            await r.update_scenario(1,'s',N(json=AsyncMock(return_value={'expected_behavior':''})),Mock())
        svc.update_scenario.assert_called_once_with('s',{'expected_behavior':''})

    async def test_liteshell_matches_partial_payload_and_empty_clear(self):
        http=N(put=AsyncMock(return_value={'success':True}));ctx=N(http=http)
        await command_test_update(ctx,['1','s'],{'expected':''})
        http.put.assert_awaited_once_with('/creator/assistant/1/tests/scenarios/s',json={'expected_behavior':''})

    def test_missing_fields_rejected_before_confirmation(self):
        with self.assertRaises(ValueError):prepare_command('lamb test update 1 s')

    async def test_update_waits_for_exact_approval_then_executes_once(self):
        from tests.test_aac_legacy import agent, message, tool, turn
        command='lamb test update 1 s --expected "Polite refusal"'
        self.assertEqual(ActionAuthorizer().check('test.update'),'ask')
        for streaming in [False,True]:
            a,p,s=agent([message(tools=[tool(command)]),message('Approve?'),message('Updated')])
            await turn(a,streaming,'Change the expectation')
            s.execute.assert_not_awaited()
            self.assertEqual(a.pending_action['command'],command)
            await a.chat('yes')
            s.execute.assert_awaited_once_with(command)
