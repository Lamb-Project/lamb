import json,unittest
from unittest.mock import patch
from types import SimpleNamespace as N
from fastapi import FastAPI
from fastapi.testclient import TestClient
from creator_interface import evaluaitor_router as router
from lamb.auth_context import get_auth_context
class RubricMetadata(unittest.TestCase):
 def test_put_preserves_extra_metadata_and_omitted_subject(self):
  app=FastAPI();app.include_router(router.router,prefix='/rubrics')
  app.dependency_overrides[get_auth_context]=lambda:N(user={'email':'owner@example.test'})
  metadata={'subject':'Science','gradeLevel':'10','createdAt':'original','custom':{'keep':True}}
  with patch.object(router.rubric_service,'get_rubric_logic',return_value={'rubric_data':{'metadata':metadata}}),patch.object(router.rubric_service,'update_rubric_logic',return_value={'ok':True}) as update:
   result=TestClient(app).put('/rubrics/r1',data={'title':'Updated','criteria':'[]'})
   self.assertEqual(result.status_code,200)
   self.assertEqual(update.call_args.kwargs['metadata'],metadata)
