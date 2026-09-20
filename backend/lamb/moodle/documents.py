"""Scoped file references and bounded Moodle downloads, never local paths."""
from dataclasses import dataclass
import hashlib
import json
import io
import uuid
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlsplit, urlunsplit, unquote
import httpx
from moodle_cli.services.base import BaseService

MAX_BYTES = 10 * 1024 * 1024
TEXT_TYPES = {'.txt', '.md', '.json', '.html'}
CONVERT_TYPES = {'.pdf', '.docx', '.pptx', '.xlsx', '.html', '.csv', '.epub'}
KB_TYPES = TEXT_TYPES | CONVERT_TYPES


def session_scope(context):
    return context.setdefault('document_scope', str(uuid.uuid4()))


class FileInventoryService(BaseService):
    def files(self, params):
        data = self.call('core_files_get_files', filename='', **params)
        return data.get('files', [])


def remember_files(files, params, context):
    output=[]
    for item in files:
        item=dict(item)
        # Moodle returns `url`, not the pinned library model's `fileurl`.
        if not item.get('isdir') and item.get('url'):
            identity=json.dumps([session_scope(context), context['course_id'], params, item['url']],sort_keys=True)
            reference='mf_'+hashlib.sha256(identity.encode()).hexdigest()[:24]
            item['file_id']=reference
            context.setdefault('files',{})[reference]={'course_id':context['course_id'],
                'listing':dict(params),'file':dict(item)}
        output.append(item)
    return output


@dataclass
class Download:
    filename: str
    content: bytes
    content_type: str


def validate_archive(content, suffix):
    """Office/EPUB are archives, but general ZIP imports remain unavailable."""
    if suffix not in {'.docx', '.pptx', '.xlsx', '.epub'}:
        return
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if (len(entries) > 5000 or sum(e.file_size for e in entries) > 50 * 1024 * 1024
                    or any(e.flag_bits & 1 for e in entries)):
                raise ValueError('Expanded Moodle document exceeds the conversion limit or is encrypted')
    except zipfile.BadZipFile:
        raise ValueError('Invalid Office/EPUB document') from None


def download_file(base_url, token, item, *, single_file):
    base=urlsplit(base_url);url=urlsplit(item['url'])
    path=unquote(url.path)
    prefix=base.path.rstrip('/')
    if (url.scheme!=base.scheme or url.netloc!=base.netloc or url.query or url.fragment
            or '\\' in path or any(p in {'.','..'} for p in path.split('/'))):
        raise PermissionError('Moodle file URL is outside the configured source')
    if path.startswith(prefix+'/pluginfile.php/'):
        path=prefix+'/webservice'+path[len(prefix):]
    if not path.startswith(prefix+'/webservice/pluginfile.php/'):
        raise PermissionError('Only Moodle course plugin files can be imported')
    name=item['filename']
    if not name or PurePosixPath(name).name!=name or '\\' in name:
        raise ValueError('Invalid Moodle filename')
    suffix=PurePosixPath(name).suffix.lower()
    allowed=TEXT_TYPES if single_file else KB_TYPES
    if suffix not in allowed:
        raise ValueError('Single-file imports accept UTF-8 txt/md/json/html. KB imports also accept pdf/docx/pptx/xlsx/csv/epub; audio, zip and xml are unavailable.')
    if item.get('filesize',0)>MAX_BYTES:
        raise ValueError('Moodle import limit is 10 MiB')
    endpoint=urlunsplit((base.scheme,base.netloc,path,'',''))
    try:
        with httpx.Client(timeout=httpx.Timeout(60,connect=10),follow_redirects=False) as client:
            # Moodle required_param accepts form fields. Never put a credential
            # into a URL (including reverse-proxy and HTTP exception logs).
            with client.stream('POST',endpoint,data={'token':token}) as response:
                if response.status_code!=200:
                    raise ValueError('Moodle file download failed; no document imported')
                content=bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content)>MAX_BYTES: raise ValueError('Moodle import limit is 10 MiB')
                mime=response.headers.get('content-type','application/octet-stream')
    except httpx.HTTPError:
        # HTTP exception URLs may contain the Moodle token.
        raise ValueError('Moodle file download failed; no document imported') from None
    if not content: raise ValueError('Moodle file is empty')
    validate_archive(content, suffix)
    if single_file:
        try: content.decode('utf-8')
        except UnicodeError: raise ValueError('Single-file grounding requires UTF-8 text') from None
    return Download(name,bytes(content),mime)
