import unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch,AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lamb import uploaded_files as files
from lamb.document_static import DocumentAwareStaticFiles
from lamb.completions.rag.single_file_rag import rag_processor

class Documents(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);public=self.root/'public';(public/'7').mkdir(parents=True);(public/'8').mkdir()
        (public/'7'/'own.txt').write_text('OWNER_SECRET');(public/'8'/'other.txt').write_text('OTHER_SECRET')
        (public/'7'/'img').mkdir();(public/'7'/'img'/'image.txt').write_text('image')
        patcher=patch.object(files,'ROOT',public);patcher.start();self.addCleanup(patcher.stop)
    def test_reference_ownership_and_symlinks(self):
        self.assertEqual(files.owned_document('7/own.txt',7).read_text(),'OWNER_SECRET')
        (files.ROOT/'7'/'link.txt').symlink_to(files.ROOT/'8'/'other.txt')
        for path in ['8/other.txt','7/link.txt','7/../8/other.txt','/etc/passwd','7\\own.txt']:
            with self.subTest(path=path),self.assertRaises(ValueError):files.owned_document(path,7)
    def test_static_requires_owner_without_breaking_generated_images(self):
        app=FastAPI();app.mount('/static',DocumentAwareStaticFiles(directory=self.root))
        c=TestClient(app)
        self.assertEqual(c.get('/static/public/7/own.txt').status_code,401)
        self.assertEqual(c.get('/static/public/7/img/image.txt').status_code,200)
        with patch('lamb.document_static.get_auth_context',AsyncMock(return_value=N(user={'id':7}))):
            own=c.get('/static/public/7/own.txt',headers={'Authorization':'Bearer own'})
            self.assertEqual(own.text,'OWNER_SECRET');self.assertEqual(own.headers['cache-control'],'private, no-store')
            self.assertEqual(c.get('/static/public/8/other.txt',headers={'Authorization':'Bearer own'}).status_code,404)
    def test_case_variants_cannot_bypass_document_authentication(self):
        # Separate directories also exercise this on case-sensitive Linux CI.
        for spelling in ('public', 'Public', 'PUBLIC'):
            directory = self.root / spelling / '7'
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'own.txt').write_text('OWNER_SECRET')
        app = FastAPI()
        app.mount('/static', DocumentAwareStaticFiles(directory=self.root))
        client = TestClient(app)
        for spelling in ('public', 'Public', 'PUBLIC', '%50ublic'):
            for method in (client.get, client.head):
                with self.subTest(spelling=spelling, method=method.__name__):
                    url = f'/static/{spelling}/7/own.txt'
                    self.assertEqual(method(url).status_code, 401)
                    with patch('lamb.document_static.get_auth_context', AsyncMock(return_value=N(user={'id':8}))):
                        self.assertEqual(method(url, headers={'Authorization':'Bearer other'}).status_code, 404)
                    with patch('lamb.document_static.get_auth_context', AsyncMock(return_value=N(user={'id':7}))):
                        response = method(url, headers={'Authorization':'Bearer own'})
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.headers['cache-control'], 'private, no-store')

    def test_existing_rag_record_cannot_read_other_owner(self):
        with patch('lamb.database_manager.LambDatabaseManager') as db:
            db.return_value.get_creator_user_by_email.return_value={'id':7}
            for reference,expected in [('7/own.txt','OWNER_SECRET'),('8/other.txt','')]:
                assistant=N(id=1,owner='owner@example.test',metadata=json.dumps({'file_path':reference}))
                result=rag_processor([],assistant)
                if expected:self.assertEqual(result['context'],expected)
                else:self.assertNotIn('OTHER_SECRET',result['context']);self.assertEqual(result['sources'],[])

class FileMutation(unittest.IsolatedAsyncioTestCase):
 async def test_upload_rejects_path_components_before_write(self):
  from creator_interface.main import upload_file
  from fastapi import HTTPException,UploadFile
  import io
  for name in ['../8/other.txt','/tmp/other.txt','8/other.txt','8\\other.txt']:
   with self.subTest(name=name),self.assertRaises(HTTPException) as error:
    await upload_file(N(),UploadFile(filename=name,file=io.BytesIO(b'x')),N(user={'id':7}))
   self.assertEqual(error.exception.status_code,400)
 async def test_delete_resolves_owner_before_unlink(self):
  from creator_interface.main import delete_file
  from fastapi import HTTPException
  with patch('lamb.uploaded_files.owned_document',side_effect=ValueError('foreign')) as owned:
   with self.assertRaises(HTTPException) as error:
    await delete_file(N(),'../8/other.txt',N(user={'id':7}))
   self.assertEqual(error.exception.status_code,404)
   owned.assert_called_once_with('../8/other.txt',7)
