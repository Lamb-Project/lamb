"""Actual HTTP display, HEAD and unchanged binary files across MIME databases."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from static_files import KnowledgeBaseStaticFiles

class StaticDisplay(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.content='# Héllo\n<script>alert("source only")</script>\n'
        for name in ('notes.md','notes.MD','notes.markdown'):
            (self.root/name).write_text(self.content)
        (self.root/'file.pdf').write_bytes(b'%PDF-test')
        app=FastAPI();app.mount('/static',KnowledgeBaseStaticFiles(directory=self.root))
        self.client=TestClient(app)

    def test_markdown_displays_source_even_when_os_does_not_know_its_type(self):
        with patch('starlette.responses.guess_type',return_value=(None,None)):
            for name in ('notes.md','notes.MD','notes.markdown'):
                response=self.client.get('/static/'+name)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['content-type'],'text/plain; charset=utf-8')
                self.assertEqual(response.headers['x-content-type-options'],'nosniff')
                self.assertEqual(response.text,self.content)
                self.assertNotIn('attachment',response.headers.get('content-disposition',''))

    def test_head_and_conditional_requests(self):
        response=self.client.head('/static/notes.md')
        self.assertEqual(response.status_code,200);self.assertEqual(response.content,b'')
        self.assertEqual(response.headers['content-type'],'text/plain; charset=utf-8')
        cached=self.client.get('/static/notes.md',headers={'If-None-Match':response.headers['etag']})
        self.assertEqual(cached.status_code,304)
        self.assertEqual(self.client.get('/static/missing.md').status_code,404)

    def test_other_file_types_are_unchanged(self):
        response=self.client.get('/static/file.pdf')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['content-type'],'application/pdf')
        self.assertEqual(response.content,b'%PDF-test')

if __name__=='__main__':unittest.main()
