"""HTTP regression: optional authentication must never downgrade bad credentials."""
import unittest
from unittest.mock import patch
import jwt, time
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from lamb.auth_context import AuthContext, get_optional_auth_context

class DiscoveryAuth(unittest.TestCase):
    def setUp(self):
        app=FastAPI()
        @app.get('/discovery')
        async def discovery(auth=Depends(get_optional_auth_context)):
            return {'organization':auth.organization['id'] if auth else None}
        self.client=TestClient(app)

    def test_anonymous_compatibility(self):
        with patch('lamb.auth_context._build_auth_context') as build:
            r=self.client.get('/discovery')
            self.assertEqual(r.status_code,200)
            self.assertIsNone(r.json()['organization'])
            build.assert_not_called()

    def test_invalid_and_malformed_credentials_are_not_anonymous(self):
        for header in ['', 'Basic abc', 'Bearer', 'Bearer ', 'Bearer invalid', 'Bearer expired', 'Bearer foreign']:
            with self.subTest(header=header), patch('lamb.auth_context._build_auth_context',return_value=None):
                r=self.client.get('/discovery',headers={'Authorization':header})
                self.assertEqual(r.status_code,401)
                self.assertEqual(r.headers.get('www-authenticate'),'Bearer')

    def test_valid_context_keeps_organization(self):
        for org_id in [2,3]:
            auth=AuthContext(user={'email':'user@example.test'},token_payload={},organization={'id':org_id})
            with patch('lamb.auth_context._build_auth_context',return_value=auth):
                r=self.client.get('/discovery',headers={'Authorization':'Bearer valid'})
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.json()['organization'],org_id)

    def test_disabled_or_deleted_denial_is_preserved(self):
        with patch('lamb.auth_context._build_auth_context',side_effect=HTTPException(403,'Account disabled')):
            r=self.client.get('/discovery',headers={'Authorization':'Bearer disabled'})
            self.assertEqual(r.status_code,403)

    def test_duplicate_authorization_is_rejected(self):
        with patch('lamb.auth_context._build_auth_context',return_value=None):
            r=self.client.get('/discovery',headers=[('Authorization','Bearer one'),('Authorization','Bearer two')])
            self.assertEqual(r.status_code,401)

    def test_native_jwt_and_legacy_owi_paths(self):
        for legacy in [False, True]:
            with self.subTest(legacy=legacy), patch('lamb.auth._get_jwt_secret',return_value='test-signing-secret-long-enough-472'), patch('lamb.auth_context._db') as db, patch('lamb.owi_bridge.owi_users.OwiUserManager') as owi:
                user={'id':7,'email':'test@example.test','organization_id':2}
                db.get_creator_user_by_email.return_value=user
                db.get_organization_by_id.return_value={'id':2,'config':{}}
                db.get_user_organization_role.return_value='member'
                token='legacy-token' if legacy else jwt.encode({'email':user['email'],'exp':time.time()+60},'test-signing-secret-long-enough-472',algorithm='HS256')
                owi.return_value.get_user_auth.return_value={'email':user['email'],'role':'user'}
                r=self.client.get('/discovery',headers={'Authorization':'Bearer '+token})
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.json()['organization'],2)
                if legacy: owi.return_value.get_user_auth.assert_called_once_with(token)
                else: owi.assert_not_called()

    def test_expired_and_foreign_signed_tokens(self):
        for secret,expiration in [('test-signing-secret-long-enough-472',time.time()-60),('foreign-signing-secret-long-enough',time.time()+60)]:
            token=jwt.encode({'email':'test@example.test','exp':expiration},secret,algorithm='HS256')
            with patch('lamb.auth._get_jwt_secret',return_value='test-signing-secret-long-enough-472'), patch('lamb.owi_bridge.owi_users.OwiUserManager') as owi:
                owi.return_value.get_user_auth.return_value=None
                r=self.client.get('/discovery',headers={'Authorization':'Bearer '+token})
                self.assertEqual(r.status_code,401)

if __name__=='__main__':unittest.main()
