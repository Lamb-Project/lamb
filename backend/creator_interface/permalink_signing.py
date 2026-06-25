"""HMAC signing for public citation permalinks.

When a learning assistant cites a source in chat, the student clicking the
citation arrives as an unauthenticated, cross-origin browser navigation that
carries no LAMB credential. So the link must authorize itself: it embeds an
HMAC signature that a public serving route verifies.

Design (decided with the project lead):
- **Per-organization isolation.** The signing key is derived from the master
  secret AND the org id, so a signature minted for one org's item can never be
  reused to forge another org's link. Rotating one org's effective key (by
  rotating the master secret) is the kill-switch.
- **No expiry.** Links live as long as the chat history that contains them, so
  old conversations stay consistent. Revocation is coarse by design: rotate
  ``LAMB_PERMALINK_SIGNING_SECRET`` (revokes everything) or delete the library
  item (its link then 404s at the proxy).
- **Capability semantics.** Within an org, anyone holding a specific link can
  open that one item — there is no identity to check on the click. This is the
  accepted trade-off for letting students reach cited sources without a login.
"""

from __future__ import annotations

import hashlib
import hmac

from config import LAMB_PERMALINK_SIGNING_SECRET

_MASTER = (LAMB_PERMALINK_SIGNING_SECRET or "").encode("utf-8")


def _org_key(org_id: str) -> bytes:
    """Derive a per-organization signing key from the master secret."""
    return hmac.new(_MASTER, f"perm:{org_id}".encode(), hashlib.sha256).digest()


def sign(org_id: str, resource: str) -> str:
    """Return the hex HMAC signature for ``resource`` scoped to ``org_id``.

    ``resource`` is a canonical, slash-joined string identifying exactly what
    may be served, e.g. ``"3/lib-uuid/item-uuid/view"`` or
    ``"3/lib-uuid/item-uuid/original/cv.pdf"``.
    """
    return hmac.new(_org_key(str(org_id)), resource.encode("utf-8"), hashlib.sha256).hexdigest()


def verify(org_id: str, resource: str, signature: str) -> bool:
    """Constant-time check that ``signature`` is valid for ``(org_id, resource)``."""
    if not signature:
        return False
    expected = sign(org_id, resource)
    return hmac.compare_digest(expected, signature)
