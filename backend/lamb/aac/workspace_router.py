"""Session-bound text reading and draft notebook API. No model calls or Moodle writes."""
import asyncio
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, ConfigDict
from lamb.auth_context import AuthContext, get_auth_context
from lamb.aac.session_manager import AACSessionManager
from lamb.aac.workspace import Workspace, text_page
from lamb.aac import document_sources

def private_response(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(dependencies=[Depends(private_response)])


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['submission', 'moodle', 'kb', 'assistant', 'upload']
    id: int | None = Field(None, gt=0)
    course: int | None = Field(None, gt=0)
    user: int | None = Field(None, gt=0)
    offset: int = Field(0, ge=0)


class OpenRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_ref: str = Field(min_length=32, max_length=32, pattern=r'^[a-f0-9]+$')


class NoteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(max_length=65536)
    revision: int = Field(ge=0)
    references: list[str] = Field(default_factory=list, max_length=64)


def workspace(auth, session_id):
    session = AACSessionManager().get_session(session_id, auth.user['email'])
    if not session or session['organization_id'] != auth.organization['id']:
        raise HTTPException(404, 'Session not found')
    return Workspace(auth.organization['id'], auth.user['id'], session_id)


def fail(exc):
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, PermissionError):
        raise HTTPException(403, str(exc))
    if isinstance(exc, (ValueError, KeyError, TypeError, FileNotFoundError)):
        raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else 'Document or note is unavailable; list it again')
    raise HTTPException(503, 'Document service is unavailable; retry later')


async def validate_documents(auth, state, ids):
    sources = {state['documents'][identity]['source_ref'] for identity in ids}
    for ref in sources:
        await document_sources.resolve(auth, state['sources'][ref])


@router.post('/sessions/{session_id}/documents/sources')
async def sources(session_id: str, body: SourceRequest, auth: AuthContext = Depends(get_auth_context)):
    try:
        store = workspace(auth, session_id)
        values = await document_sources.list_sources(auth, body.kind, body.id, body.course, body.user)
        page = values[body.offset:body.offset + 20]
        return {'items': store.sources(page), 'total': len(values), 'offset': body.offset,
                'next_offset': body.offset + len(page) if body.offset + len(page) < len(values) else None}
    except Exception as exc:
        fail(exc)


def extract(download):
    from pathlib import Path
    from lamb.moodle.reading import convert
    from lamb.moodle.documents import TEXT_TYPES
    suffix = Path(download.filename).suffix.lower()
    if suffix in TEXT_TYPES - {'.html'}:
        # Preserve the exact text, including whitespace, across page boundaries.
        return download.content.decode('utf-8'), {'notice': 'Text only; embedded images are not read.'}
    if suffix == '.html':
        from lamb.moodle.html_document import convert_html, LOSS_NOTICE
        text, losses = convert_html(download.content.decode('utf-8'), base_url='')
        return text, {**losses, 'notice': LOSS_NOTICE}
    blocks, losses, pages = convert(download)
    text = '\n\n'.join((f'[page {page}]\n' if page else '') + block for page, heading, block in blocks)
    return text, {**losses, 'pages': pages, 'notice': losses.get('notice', 'Text conversion only; no images or OCR.')}


@router.post('/sessions/{session_id}/documents/open')
async def open_document(session_id: str, body: OpenRequest, auth: AuthContext = Depends(get_auth_context)):
    try:
        store = workspace(auth, session_id)
        source = store.read()['sources'][body.source_ref]
        download = await document_sources.resolve(auth, source, download=True)
        text, conversion = await asyncio.to_thread(extract, download)
        await document_sources.resolve(auth, source)  # revalidate after download/conversion
        result = store.document(body.source_ref, text, conversion)
        return {**result, 'title': source['title'], 'source': source.get('citation', {})}
    except Exception as exc:
        fail(exc)


@router.get('/sessions/{session_id}/documents/{read_id}')
async def read_document(session_id: str, read_id: str, offset: int = 0, find: str | None = None,
                        auth: AuthContext = Depends(get_auth_context)):
    try:
        state = workspace(auth, session_id).read()
        item = state['documents'][read_id]
        await validate_documents(auth, state, [read_id])
        source = state['sources'][item['source_ref']]
        return {**text_page(item['text'], offset, find), 'read_id': read_id,
                'source': source.get('citation', {}), 'title': source['title'], 'sha256': item['sha256'],
                'conversion': item['conversion'], 'untrusted_source': True,
                'citation': f'{read_id}:characters', 'evidence_kind': 'extracted_text_snapshot'}
    except Exception as exc:
        fail(exc)


@router.get('/sessions/{session_id}/notebook')
async def list_notes(session_id: str, auth: AuthContext = Depends(get_auth_context)):
    try:
        state = workspace(auth, session_id).read()
        await validate_documents(auth, state, state['documents'])
        return {'notes': [{k: n[k] for k in ('name', 'revision', 'updated_at', 'kind')} for n in state['notes'].values()],
                'kind': 'working_draft', 'is_source_evidence': False}
    except Exception as exc:
        fail(exc)


@router.get('/sessions/{session_id}/notebook/read')
async def read_note(session_id: str, name: str, offset: int = 0, auth: AuthContext = Depends(get_auth_context)):
    try:
        state = workspace(auth, session_id).read()
        note = state['notes'][name]
        await validate_documents(auth, state, note['references'])
        return {**{k: v for k, v in note.items() if k != 'content'}, **text_page(note['content'], offset)}
    except Exception as exc:
        fail(exc)


@router.post('/sessions/{session_id}/notebook')
async def write_note(session_id: str, body: NoteRequest, auth: AuthContext = Depends(get_auth_context)):
    try:
        store = workspace(auth, session_id)
        state = store.read()
        await validate_documents(auth, state, set(state['documents']) | set(body.references))
        return store.note(body.name, body.content, body.revision, body.references)
    except Exception as exc:
        fail(exc)
