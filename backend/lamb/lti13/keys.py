"""Persistent RSA signing keys. Rotate atomically; keep retired public keys for one day."""
import fcntl
import json
import os
import secrets
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class KeyRing:
    def __init__(self, directory=None):
        if directory is None:
            import config
            directory = os.getenv('LTI13_KEY_DIR') or str(Path(config.LAMB_DB_PATH) / 'lti13-keys')
        self.directory = Path(directory)

    @contextmanager
    def locked(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.directory / '.lock'
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _read(self):
        path = self.directory / 'keyring.json'
        return json.loads(path.read_text()) if path.exists() else []

    def _write(self, keys):
        fd, path = tempfile.mkstemp(dir=self.directory, prefix='.keyring-')
        with os.fdopen(fd, 'w') as stream:
            json.dump(keys, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.directory / 'keyring.json')

    def _rotate(self, keys):
        now = int(time.time())
        for key in keys:
            if key.get('retired_at') is None:
                key['retired_at'] = now
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        kid = secrets.token_urlsafe(18)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
        public.update(kid=kid, alg='RS256', use='sig')
        keys.append({'kid': kid, 'created_at': now, 'retired_at': None, 'public': public,
                     'private': private.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()})
        self._write(keys)
        return keys

    def keys(self):
        with self.locked():
            keys = self._read()
            return keys or self._rotate([])

    def rotate(self):
        with self.locked():
            return self._rotate(self._read())[-1]['kid']

    def public(self):
        return {'keys': [k['public'] for k in self.keys()
                         if k['retired_at'] is None or k['retired_at'] > time.time() - 86400]}

    def sign(self, claims):
        key = next(k for k in self.keys() if k['retired_at'] is None)
        return jwt.encode(claims, key['private'], algorithm='RS256', headers={'kid': key['kid']})
