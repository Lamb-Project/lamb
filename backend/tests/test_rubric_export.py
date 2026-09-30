"""Rubric exports accept Unicode titles without corrupting content or headers."""
from types import SimpleNamespace
from urllib.parse import unquote
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from creator_interface import evaluaitor_router as routes
from lamb.auth_context import get_auth_context


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router, prefix='/rubrics')
    app.dependency_overrides[get_auth_context] = lambda: SimpleNamespace(
        user={'email': 'owner@example.test'}
    )
    with TestClient(app) as value:
        yield value


@pytest.mark.parametrize('format,extension', [('json', 'json'), ('markdown', 'md')])
@pytest.mark.parametrize('title', ['plain-title', 'c4-model—rúbrica', '評価-📚', 'a";b\\c\r\nX-Injected: yes'])
def test_export_preserves_content_and_encodes_filename(client, format, extension, title):
    filename = f'{title}.{extension}'
    content = {'title': title, 'criteria': []} if format == 'json' else f'# {title}\n\nRúbrica 評価 📚'
    with patch.object(routes.rubric_service, f'export_rubric_{format}_logic', return_value=(content, filename)) as export:
        response = client.get(f'/rubrics/example/export/{format}')
    assert response.status_code == 200
    export.assert_called_once_with(rubric_id='example', user_email='owner@example.test')
    assert (response.json() if format == 'json' else response.text) == content
    header = response.headers['content-disposition']
    header.encode('ascii')
    assert '\r' not in header and '\n' not in header
    assert 'x-injected' not in response.headers
    encoded = header.split("filename*=UTF-8''", 1)[1].split(';', 1)[0]
    assert unquote(encoded) == filename
    # The existing browser export helper reads the final filename= parameter.
    fallback = header.split('filename=', 1)[1].strip('"')
    assert fallback.endswith('.' + extension)
    assert not any(c in fallback for c in '\r\n"\\;')


@pytest.mark.parametrize('format', ['json', 'markdown'])
def test_export_keeps_access_checks(client, format):
    with patch.object(routes.rubric_service, f'export_rubric_{format}_logic', side_effect=ValueError('Rubric not found or access denied')):
        assert client.get(f'/rubrics/foreign/export/{format}').status_code == 404
    client.app.dependency_overrides.clear()
    assert client.get(f'/rubrics/example/export/{format}').status_code in (401, 403)
