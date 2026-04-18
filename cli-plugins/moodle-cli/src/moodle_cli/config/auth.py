"""Secure token storage using the OS keyring."""

from __future__ import annotations

import keyring

SERVICE_NAME = "moodle-cli"


class TokenStore:
    """Store and retrieve Moodle tokens in the OS keyring."""

    def __init__(self, service: str = SERVICE_NAME) -> None:
        self.service = service

    def _key(self, profile: str) -> str:
        return f"{self.service}:{profile}"

    def store(self, profile: str, token: str) -> None:
        keyring.set_password(self.service, self._key(profile), token)

    def get(self, profile: str) -> str | None:
        return keyring.get_password(self.service, self._key(profile))

    def delete(self, profile: str) -> None:
        try:
            keyring.delete_password(self.service, self._key(profile))
        except keyring.errors.PasswordDeleteError:
            pass
