"""Owner-scoped uploaded document references, shared by API writes and RAG reads."""
import json
from pathlib import Path
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent.parent / 'static' / 'public'

def owned_document(reference, owner_id):
    if not isinstance(reference, str) or not reference or '\\' in reference:
        raise ValueError('Invalid uploaded document reference')
    relative=Path(reference)
    if relative.is_absolute() or len(relative.parts)!=2 or '..' in relative.parts or relative.parts[0]!=str(owner_id):
        raise ValueError('Uploaded document must belong to the assistant owner')
    path=ROOT / relative
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.resolve().parent != (ROOT / str(owner_id)).resolve():
        raise ValueError('Owned uploaded document not found')
    return path

def document_for_owner(reference, owner_email):
    from lamb.database_manager import LambDatabaseManager
    user=LambDatabaseManager().get_creator_user_by_email(owner_email)
    if not user:
        raise ValueError('Assistant owner not found')
    return owned_document(reference,user['id'])

def validate_file_binding(metadata, owner_email):
    value=json.loads(metadata) if isinstance(metadata,str) else metadata
    if isinstance(value,dict) and value.get('rag_processor')=='single_file_rag':
        try:
            document_for_owner(value.get('file_path'),owner_email)
        except ValueError as error:
            raise HTTPException(400,str(error))
