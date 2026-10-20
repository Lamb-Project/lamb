import copy
import unittest
from types import SimpleNamespace as N
from unittest.mock import Mock,patch
from fastapi import HTTPException
from creator_interface import organization_router as r
from tests.aac_knowledge_fixtures import CONFIG

class OrganizationPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_settings_are_served_under_the_real_admin_mount(self):
        import httpx
        from main import app
        auth, db, _ = self.fixture(True)
        with patch.object(r, '_build_auth_context', return_value=auth), patch.object(r, 'db_manager', db):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.get('/creator/admin/org-admin/settings/aac', headers={'Authorization':'Bearer fixture'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('ollama', response.json()['models'])

    async def test_malformed_stored_settings_remain_repairable_by_admin(self):
        auth, db, req = self.fixture(True)
        auth.organization['config']['setups']['default']['aac'] = ['invalid stored data']
        with patch.object(r, '_build_auth_context', return_value=auth), patch.object(r, 'db_manager', db):
            result = await r.get_agent_settings(req)
            self.assertEqual(result['settings'], {})
            self.assertTrue(result['warnings'])
            self.assertIn('ollama', result['models'])
            repaired = await r.update_agent_settings(req, {'provider':'ollama', 'model':'fixture'})
        self.assertEqual(repaired['settings']['model'], 'fixture')
        db.update_organization_config.assert_called_once()

    def fixture(self, admin=False, system=False):
        config=copy.deepcopy(CONFIG);config['untouched']={'secret':'fixture-only'}
        org={'id':7,'slug':'own','config':config}
        auth=N(user={'id':2,'email':'owner@test'},organization=org,is_org_admin=admin,is_system_admin=system,organization_role='admin' if admin else 'member')
        db=Mock();db.get_organization_by_slug.side_effect=lambda slug:org if slug=='own' else {'id':8,'slug':'other','config':config}
        db.get_organization_by_id.return_value=org;db.update_organization_config.return_value=True
        return auth,db,N(headers={'Authorization':'Bearer fixture'})

    async def test_creator_denied_and_org_admin_cross_org_denied(self):
        for admin,target in [(False,None),(True,'other')]:
            auth,db,req=self.fixture(admin)
            with patch.object(r,'_build_auth_context',return_value=auth),patch.object(r,'db_manager',db):
                for call in [r.get_agent_settings(req,target),r.update_agent_settings(req,{},target)]:
                    with self.assertRaises(HTTPException) as err:await call
                    self.assertEqual(err.exception.status_code,403)
                db.update_organization_config.assert_not_called()

    async def test_admin_writes_only_target_and_preserves_other_config(self):
        auth,db,req=self.fixture(True)
        with patch.object(r,'_build_auth_context',return_value=auth),patch.object(r,'db_manager',db):
            result=await r.update_agent_settings(req,{'provider':'ollama','model':'fixture','language_fallbacks':{'eu':'es'},'pack_channel':'stable'},'own')
        org_id,saved=db.update_organization_config.call_args.args
        self.assertEqual(org_id,7);self.assertEqual(saved['untouched'],auth.organization['config']['untouched'])
        self.assertEqual(result['settings']['language_fallbacks'],{'eu':'es'})
        self.assertNotIn('aac',auth.organization['config']['setups']['default'])

    async def test_bad_configuration_never_writes_and_get_has_no_keys(self):
        auth,db,req=self.fixture(True)
        with patch.object(r,'_build_auth_context',return_value=auth),patch.object(r,'db_manager',db):
            data=await r.get_agent_settings(req)
            self.assertNotIn('secret',str(data))
            for settings in [{'provider':'google','model':'x'},{'pack_version':'99.0.0'},{'language_fallbacks':{'eu':'es','es':'eu'}}]:
                with self.assertRaises(HTTPException) as err:await r.update_agent_settings(req,settings)
                self.assertEqual(err.exception.status_code,400)
            db.update_organization_config.assert_not_called()
