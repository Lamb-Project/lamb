"""Authenticated token encryption bound to the LAMB owner and organization.

The deployment key is mandatory and must be backed up outside the database.
No fallback to application passwords, signing keys or plaintext storage.
"""
import json
import os
from cryptography.fernet import Fernet, InvalidToken
from .policy import MoodleConfigurationError, canonical_base_url


class TokenCipher:
    def __init__(self, key=None):
        try:
            self.cipher = Fernet(key if key is not None else os.environ['LAMB_MOODLE_ENCRYPTION_KEY'])
        except (KeyError, ValueError, TypeError):
            raise MoodleConfigurationError('The administrator must configure LAMB_MOODLE_ENCRYPTION_KEY') from None

    def encrypt(self, token, *, organization_id, owner_id, base_url):
        if not isinstance(token, str) or not token.strip():
            raise ValueError('A Moodle token is required')
        payload = {'version': 1, 'organization_id': int(organization_id), 'owner_id': int(owner_id),
                   'base_url': canonical_base_url(base_url), 'token': token}
        return self.cipher.encrypt(json.dumps(payload, separators=(',', ':')).encode()).decode()

    def decrypt(self, ciphertext, *, organization_id, owner_id, base_url):
        try:
            payload = json.loads(self.cipher.decrypt(ciphertext.encode()))
            expected = (1, int(organization_id), int(owner_id), canonical_base_url(base_url))
            actual = tuple(payload.get(k) for k in ('version', 'organization_id', 'owner_id', 'base_url'))
            if actual != expected or not isinstance(payload.get('token'), str) or not payload['token']:
                raise ValueError()
            return payload['token']
        except (InvalidToken, ValueError, TypeError, AttributeError):
            raise MoodleConfigurationError('Stored Moodle connection cannot be decrypted; reconnect Moodle') from None
