"""RAG citation links keep absolute KB metadata URLs intact (#420)."""
from types import SimpleNamespace
from unittest import mock

import pytest

from lamb.completions.rag import simple_rag
from lamb.completions.source_urls import kb_file_url

KB = 'http://kb:9090'
PUBLIC = 'https://kb.example.org/static/8/course_kb/65e5d274.html'


@pytest.mark.parametrize('value,expected', [
    (PUBLIC, PUBLIC),
    ('http://localhost:19090/static/8/k/a.md', 'http://localhost:19090/static/8/k/a.md'),
    ('/static/8/k/a.md', 'http://kb:9090/static/8/k/a.md'),
    ('static/8/k/a.md', 'http://kb:9090/static/8/k/a.md'),
])
def test_kb_file_url(value, expected):
    assert kb_file_url(KB, value) == expected
    assert kb_file_url(KB + '/', value) == expected


def _run(metadata):
    assistant = SimpleNamespace(id=55, name='probe', owner='a1@example.invalid', RAG_collections='9', RAG_Top_k=3)
    resolver = mock.Mock(organization={'name': 'fixture'})
    resolver.get_knowledge_base_config.return_value = {'server_url': KB, 'api_token': 'fixture-only'}
    response = mock.Mock(status_code=200)
    response.json.return_value = {'results': [{'data': 'The station access code is COBALT-742.', 'similarity': 0.71,
                                               'metadata': dict(metadata, chunk_index=0, filename='source.md')}]}
    with mock.patch.object(simple_rag, 'OrganizationConfigResolver', return_value=resolver), \
         mock.patch.object(simple_rag.requests, 'post', return_value=response):
        return simple_rag.rag_processor([{'role': 'user', 'content': 'What is the station access code?'}], assistant=assistant)


def test_simple_rag_keeps_absolute_file_url():
    urls = [s['url'] for s in _run({'file_url': PUBLIC})['sources']]
    assert urls == [PUBLIC]


def test_simple_rag_prefixes_relative_file_url():
    urls = [s['url'] for s in _run({'file_url': '/static/8/course_kb/a.md'})['sources']]
    assert urls == ['http://kb:9090/static/8/course_kb/a.md']


def test_simple_rag_original_file_url_absolute():
    urls = [s['url'] for s in _run({'file_url': '/static/x.md', 'original_file_url': PUBLIC})['sources']]
    assert urls == [PUBLIC]
