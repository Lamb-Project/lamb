"""Small LAMB error boundary around the standard Moodle client.

Function metadata is an optional hint, never an authorization grant. Legacy
connections still call Moodle normally; org policy and approval remain separate.
"""
import re
from moodle_cli.client.http import MoodleHTTPClient as StandardClient
from moodle_cli.client.exceptions import MoodleAPIError
from moodle_cli.client.readonly import READ_ALLOWLIST


def function_names(rows):
    if not isinstance(rows, list) or not rows or len(rows) > 10000:
        return None
    names = [row.get('name') if isinstance(row, dict) else None for row in rows]
    if any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,199}', name) for name in names):
        return None
    return sorted(set(names))


class MoodleHTTPClient(StandardClient):
    def __init__(self, *args, functions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.functions = (set(functions) if isinstance(functions, list) and functions
                          and all(isinstance(name, str) for name in functions) else None)

    def call(self, wsfunction, **params):
        # The library's readonly prohibition takes precedence over optional hints.
        if self.readonly and wsfunction not in READ_ALLOWLIST:
            return super().call(wsfunction, **params)
        if self.functions is not None and wsfunction not in self.functions:
            raise PermissionError('This Moodle connection does not advertise the required API. '
                'The information is unavailable, not empty. Do not retry with different IDs or dates. '
                'If the site service has changed, reconnect to update its function list.')
        try:
            return super().call(wsfunction, **params)
        except MoodleAPIError as error:
            if error.error_code in {'webservicenotavailable', 'servicenotavailable'}:
                raise PermissionError('This Moodle connection cannot provide the requested API. '
                    'The information is unavailable, not empty. Do not retry the same operation '
                    'with different IDs or dates; the site administrator may need to enable the standard service.') from None
            if error.error_code in {'accessexception', 'nopermissions'}:
                raise PermissionError('Moodle denied permission for this operation for the connected account. '
                    'No conclusion about missing activity or data can be drawn. '
                    'Do not retry with guessed IDs or another date range.') from None
            raise
