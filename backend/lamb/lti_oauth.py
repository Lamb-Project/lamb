"""Shared OAuth 1.0 helpers for LTI 1.1 launch verification."""
import urllib.parse


def signing_key(consumer_secret: str, token_secret: str = "") -> str:
    """HMAC-SHA1 key per RFC 5849 section 3.4.2: both secrets percent-encoded, joined by '&'.

    LTI consumers such as Moodle encode the secret before signing, so a raw secret
    containing characters like '%', '=', ']' or '$' never reproduces their signature (#318).
    """
    return f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"
