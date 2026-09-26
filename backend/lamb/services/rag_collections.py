"""Resolve an assistant's RAG_collections to knowledge-base IDs the owner can use (#517).

RAG processors query the KB server by collection ID. A value that is not an accessible ID
used to be stored as-is and produced an empty context at chat time, with no error.
"""
from typing import Callable, Dict, List


class RagCollectionsError(ValueError):
    """Raised with a user-facing message naming the entry that could not be resolved."""


def resolve_rag_collections(raw: str, accessible: List[Dict]) -> str:
    """Return a comma-separated list of KB IDs.

    Each entry is kept if it is an accessible KB ID; an exact name matching exactly one
    accessible KB becomes that KB's ID. Anything else raises RagCollectionsError.
    `accessible` holds kb_registry rows (kb_id, kb_name) owned by or shared with the owner.
    """
    entries = [e.strip() for e in (raw or '').split(',') if e.strip()]
    by_id = {str(kb['kb_id']): kb for kb in accessible}
    resolved: List[str] = []
    for entry in entries:
        if entry in by_id:
            kb_id = entry
        else:
            named = [str(kb['kb_id']) for kb in accessible if kb.get('kb_name') == entry]
            if len(named) > 1:
                raise RagCollectionsError(
                    f"RAG collection '{entry}' matches several knowledge bases (IDs {', '.join(named)}); use the ID.")
            if not named:
                raise RagCollectionsError(
                    f"RAG collection '{entry}' is not a knowledge base ID or name available to the assistant owner; "
                    "use an ID from 'lamb kb list'.")
            kb_id = named[0]
        if kb_id not in resolved:
            resolved.append(kb_id)
    return ','.join(resolved)


def resolve_for_user(raw: str, user_id: int, organization_id: int,
                     lookup: Callable[[int, int], List[Dict]] = None) -> str:
    """Resolve against the knowledge bases the given user owns or sees shared in the organization."""
    if not (raw or '').strip():
        return ''
    if lookup is None:
        from lamb.database_manager import LambDatabaseManager
        lookup = LambDatabaseManager().get_accessible_kbs
    return resolve_rag_collections(raw, lookup(user_id, organization_id))
