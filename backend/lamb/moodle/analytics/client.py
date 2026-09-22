"""Pinned-client extension for one reviewed optional read endpoint.

Does not modify the upstream process-wide allowlist or disable read-only mode.
All other functions retain the upstream client's policy and transport behavior.
"""
import json
import httpx
from moodle_cli.client.http import MoodleHTTPClient, flatten_params
from moodle_cli.client.exceptions import ConnectionError, MoodleAPIError

EVENT_FUNCTION = 'local_lambanalytics_resource_events'
MAX_EVENT_BYTES = 256 * 1024
EVENT_PARAMETERS = frozenset({'courseid', 'since', 'until', 'groupid', 'afterid', 'throughid', 'limit'})


class AnalyticsHTTPClient(MoodleHTTPClient):
    def call(self, wsfunction, **params):
        if wsfunction != EVENT_FUNCTION:
            return super().call(wsfunction, **params)
        if set(params) - EVENT_PARAMETERS or not {'courseid', 'since', 'until'} <= params.keys():
            raise ValueError('Invalid resource-event parameters')
        if any(type(value) is not int for value in params.values()):
            raise ValueError('Resource-event parameters must be integers')
        form = flatten_params(params)
        form.update(wstoken=self.token, wsfunction=EVENT_FUNCTION, moodlewsrestformat='json')
        try:
            with self._client.stream('POST', self.rest_url, data=form) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_bytes():
                    if len(payload) + len(chunk) > MAX_EVENT_BYTES:
                        raise ValueError('Resource-event response exceeds its byte budget')
                    payload.extend(chunk)
        except httpx.HTTPError:
            raise ConnectionError('Resource-event transport failed') from None
        try:
            data = json.loads(payload)
        except (ValueError, UnicodeError):
            raise ValueError('Invalid resource-event response') from None
        if not isinstance(data, dict):
            raise ValueError('Invalid resource-event response')
        if 'exception' in data:
            # Do not propagate arbitrary plugin debug details or server paths.
            raise MoodleAPIError('Resource-event source rejected the request', error_code=data.get('errorcode'))
        return data
