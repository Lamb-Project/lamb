"""Private session document references, extracted text and revisioned draft notes."""
import hashlib
import json
import time
import uuid
from pathlib import Path
from lamb.private_storage import data_root, file_lock, atomic_json, read_json

MAX_DOCUMENTS = 64
MAX_TEXT = 1_500_000
MAX_SESSION_BYTES = 16 * 1024 * 1024
PAGE_CHARS = 6000


class Workspace:
    def __init__(self, organization, owner, session, root=None):
        if type(organization) is not int or type(owner) is not int or min(organization, owner) < 1:
            raise PermissionError('Authenticated workspace owner required')
        session = str(uuid.UUID(session))
        self.path = Path(root or data_root() / 'aac_workspaces') / str(organization) / str(owner) / session
        if any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise PermissionError('Unsafe workspace location')

    def read(self):
        with file_lock(self.path):
            return self._read()

    def _read(self):
        file = self.path / 'workspace.json'
        return read_json(file, MAX_SESSION_BYTES) if file.exists() else {'sources': {}, 'documents': {}, 'notes': {}}

    def change(self, fn):
        with file_lock(self.path):
            state = self._read()
            value = fn(state)
            if len(json.dumps(state, ensure_ascii=False).encode()) > MAX_SESSION_BYTES:
                raise ValueError('Session workspace is full; start another session')
            atomic_json(self.path / 'workspace.json', state)
            return value

    def sources(self, sources):
        def save(state):
            output = []
            for source in sources:
                identity = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:32]
                if identity not in state['sources'] and len(state['sources']) >= 512:
                    raise ValueError('Session source limit reached')
                state['sources'][identity] = source
                output.append({'source_ref': identity, 'title': source['title'], 'kind': source['kind'],
                               'filename': source.get('filename'), 'source': source.get('citation', {})})
            return output
        return self.change(save)

    def document(self, source_ref, text, conversion):
        if not text.strip():
            raise ValueError('No readable text; images and scanned pages require a later version with OCR/vision')
        if len(text) > MAX_TEXT:
            raise ValueError('Document exceeds 1.5 million extracted characters')
        def save(state):
            if source_ref not in state['sources']:
                raise PermissionError('Unknown source reference in this session')
            if len(state['documents']) >= MAX_DOCUMENTS:
                raise ValueError('Session document limit reached')
            identity = str(uuid.uuid4())
            state['documents'][identity] = {'source_ref': source_ref, 'text': text, 'conversion': conversion,
                'sha256': hashlib.sha256(text.encode()).hexdigest(), 'created_at': time.time()}
            return {'read_id': identity, 'source_ref': source_ref, 'characters': len(text),
                    'sha256': state['documents'][identity]['sha256'], 'conversion': conversion,
                    'read_command': f'lamb document read {identity}', 'text_in_conversation': False}
        return self.change(save)

    def note(self, name, content, revision, references):
        if not name.strip() or len(name) > 120 or len(content.encode()) > 64 * 1024:
            raise ValueError('Notebook needs a name of 1–120 characters and text up to 64 KiB')
        def save(state):
            previous = state['notes'].get(name)
            if revision != (previous['revision'] if previous else 0):
                raise ValueError('Notebook revision conflict; read the current note before updating')
            if previous is None and len(state['notes']) >= 64:
                raise ValueError('Notebook limit is 64 notes per session')
            # Conservatively retain all documents already opened in this session.
            refs = sorted(set(references) | set(state['documents']) | set((previous or {}).get('references', [])))
            if any(r not in state['documents'] for r in refs):
                raise ValueError('Notebook references must be document read IDs from this session')
            item = {'name': name, 'content': content, 'revision': revision + 1, 'references': refs,
                    'updated_at': time.time(), 'kind': 'working_draft', 'is_source_evidence': False}
            state['notes'][name] = item
            return {k: v for k, v in item.items() if k != 'content'}
        return self.change(save)


def text_page(text, offset=0, find=None):
    if offset < 0 or offset > len(text):
        raise ValueError('Offset is outside the text')
    if find:
        if len(find) < 2 or len(find) > 200:
            raise ValueError('Find text must have 2–200 characters')
        # Exact matching keeps offsets valid for all Unicode text.
        offset = text.find(find, offset)
        if offset < 0:
            return {'text': '', 'next_offset': None, 'match_found': False, 'characters': len(text)}
    end = min(offset + PAGE_CHARS, len(text))
    return {'text': text[offset:end], 'offset': offset, 'next_offset': end if end < len(text) else None,
            'characters': len(text), 'complete': offset == 0 and end == len(text)}
