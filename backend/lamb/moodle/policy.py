"""Organization-scoped connector policy, independent of model instructions."""
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, unquote


class MoodleConfigurationError(ValueError):
    """Configuration is invalid; callers should report an administrator-facing 503."""


def canonical_base_url(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise MoodleConfigurationError('Moodle base URL is required')
    try:
        url = urlsplit(value)
        port = url.port
        if (url.scheme not in {'https', 'http'} or not url.hostname or
                url.username is not None or url.password is not None or url.query or url.fragment):
            raise ValueError()
        if any(ord(c) <= 32 for c in value) or '\\' in value:
            raise ValueError()
        path = unquote(url.path)
        if '%' in url.path or any(p in {'.', '..'} for p in path.split('/')) or '//' in path:
            raise ValueError()
        host = url.hostname.encode('idna').decode('ascii').lower()
        if ':' in host:
            host = '[' + host + ']'
        if port is not None and (url.scheme, port) not in {('https', 443), ('http', 80)}:
            host += ':' + str(port)
        return urlunsplit((url.scheme, host, path.rstrip('/'), '', ''))
    except (ValueError, UnicodeError):
        raise MoodleConfigurationError('Use a Moodle base URL without credentials, query or fragment') from None


@dataclass(frozen=True)
class MoodlePolicy:
    enabled: bool = False
    base_url: str = ''
    mode: str = 'readonly'
    write_groups: frozenset = frozenset()
    allow_grade_write: bool = False

    @classmethod
    def from_config(cls, config):
        raw = (config or {}).get('moodle', {})
        if not isinstance(raw, dict):
            raise MoodleConfigurationError('Invalid Moodle organization settings')
        enabled = raw.get('enabled', False)
        grade = raw.get('allow_grade_write', False)
        if type(enabled) is not bool or type(grade) is not bool:
            raise MoodleConfigurationError('Moodle enable and grade flags must be booleans')
        mode = raw.get('mode', 'readonly')
        groups = raw.get('write_groups', [])
        if mode not in {'readonly', 'full'} or not isinstance(groups, list) or any(g != 'forum' for g in groups):
            raise MoodleConfigurationError('Moodle supports readonly or full mode, with forum writes only')
        base = canonical_base_url(raw['base_url']) if raw.get('base_url') else ''
        if enabled and not base:
            raise MoodleConfigurationError('Set the allowed Moodle URL before enabling the connector')
        return cls(enabled, base, mode, frozenset(groups), grade)

    def require_connection_url(self, base_url):
        if not self.enabled:
            raise PermissionError('Moodle connector is disabled for this organization')
        if canonical_base_url(base_url) != self.base_url:
            raise PermissionError('Connect only to the Moodle instance allowed by your organization')

    def require_write(self, group):
        if not self.enabled or self.mode != 'full':
            raise PermissionError('Moodle writes are disabled for this organization')
        allowed = self.allow_grade_write if group == 'grade' else group in self.write_groups
        if not allowed:
            raise PermissionError('This Moodle write group is not enabled by your organization')
