"""Reviewed analytics reads with streaming byte budgets.

Does not modify the upstream process-wide allowlist or disable read-only mode.
All other functions retain the upstream client's policy and transport behavior.
"""
import json
import httpx
from moodle_cli.client.http import MoodleHTTPClient, flatten_params
from moodle_cli.client.exceptions import ConnectionError, MoodleAPIError, ReadOnlyViolation
from moodle_cli.client.readonly import READ_ALLOWLIST

EVENT_FUNCTION = 'local_lambanalytics_resource_events'
SCOPE_FUNCTION = 'local_lambanalytics_resource_scope'
GRADE_SCOPE_FUNCTION = 'local_lambanalytics_grade_scope'
COMPLETION_SCOPE_FUNCTION = 'local_lambanalytics_completion_scope'
DEFAULT_DATES_FUNCTION = 'local_lambanalytics_default_dates'
QUIZ_SCOPE_FUNCTION = 'local_lambanalytics_quiz_scope'
MAX_EVENT_BYTES = 256 * 1024
GRADE_FUNCTION = 'mod_assign_get_grades'
MAX_GRADE_BYTES = 1024 * 1024
COMPLETION_FUNCTION = 'core_completion_get_activities_completion_status'
MAX_COMPLETION_BYTES = 256 * 1024
EVENT_PARAMETERS = frozenset({'courseid', 'since', 'until', 'groupid', 'afterid', 'throughid', 'limit'})


class AnalyticsHTTPClient(MoodleHTTPClient):
    def call(self, wsfunction, **params):
        if wsfunction == QUIZ_SCOPE_FUNCTION:
            if (set(params)-{'courseid','quizid','groupid'} or not {'courseid','quizid'}<=params.keys()
                    or any(type(value) is not int for value in params.values())
                    or params['courseid']<1 or params['quizid']<1 or params.get('groupid',0)<0):
                raise ValueError('Invalid quiz-scope parameters')
            return self._bounded_read(wsfunction,params,4096,'Quiz-scope')
        if wsfunction == DEFAULT_DATES_FUNCTION:
            ids=params.get('cmids')
            if (set(params)-{'courseid','cmids','scopeonly'} or type(params.get('courseid')) is not int
                    or params['courseid']<1 or not isinstance(ids,list) or not 1<=len(ids)<=100
                    or any(type(value) is not int or value<1 for value in ids) or len(set(ids))!=len(ids)
                    or type(params.get('scopeonly',0)) is not int or params.get('scopeonly',0) not in (0,1)):
                raise ValueError('Invalid default-date parameters')
            return self._bounded_read(wsfunction,params,MAX_EVENT_BYTES,'Default-date')
        if wsfunction == COMPLETION_FUNCTION:
            if self.readonly and wsfunction not in READ_ALLOWLIST:
                raise ReadOnlyViolation('Activity-completion source is outside the upstream read allowlist')
            if (set(params)-{'courseid','userid'} or type(params.get('courseid')) is not int or
                    params['courseid'] < 1 or type(params.get('userid',0)) is not int or params.get('userid',0)<0):
                raise ValueError('Invalid activity-completion parameters')
            return self._bounded_read(wsfunction, params, MAX_COMPLETION_BYTES, 'Activity-completion')
        if wsfunction == GRADE_FUNCTION:
            # Preserve upstream read-only authority; do not extend its allowlist.
            if self.readonly and wsfunction not in READ_ALLOWLIST:
                raise ReadOnlyViolation('Assignment-grade source is outside the upstream read allowlist')
            ids = params.get('assignmentids')
            if (set(params)-{'assignmentids','since'} or not isinstance(ids,(list,tuple)) or
                    not 1 <= len(ids) <= 100 or any(type(v) is not int or v < 1 for v in ids) or
                    len(set(ids)) != len(ids) or type(params.get('since',0)) is not int or params.get('since',0)<0):
                raise ValueError('Invalid assignment-grade parameters')
            return self._bounded_read(wsfunction, params, MAX_GRADE_BYTES, 'Assignment-grade')
        if wsfunction not in {EVENT_FUNCTION, SCOPE_FUNCTION, GRADE_SCOPE_FUNCTION, COMPLETION_SCOPE_FUNCTION}:
            return super().call(wsfunction, **params)
        allowed = EVENT_PARAMETERS if wsfunction == EVENT_FUNCTION else {'courseid','groupid','cmids'}
        required = {'courseid','since','until'} if wsfunction == EVENT_FUNCTION else {'courseid'}
        if wsfunction == GRADE_SCOPE_FUNCTION:
            allowed = required = {'courseid','assignmentid'}
        if wsfunction == COMPLETION_SCOPE_FUNCTION:
            allowed = required = {'courseid','cmids'}
        if set(params) - allowed or not required <= params.keys():
            raise ValueError('Invalid resource-event parameters')
        if any(type(value) is not int for key,value in params.items() if key != 'cmids'):
            raise ValueError('Resource-event parameters must be integers')
        if 'cmids' in params and (not isinstance(params['cmids'],list) or len(params['cmids']) > 100 or
                any(type(value) is not int or value < 1 for value in params['cmids']) or len(set(params['cmids'])) != len(params['cmids'])):
            raise ValueError('Invalid resource module IDs')
        return self._bounded_read(wsfunction, params, MAX_EVENT_BYTES, 'Resource-event')

    def _bounded_read(self, wsfunction, params, byte_budget, label):
        form = flatten_params(params)
        form.update(wstoken=self.token, wsfunction=wsfunction, moodlewsrestformat='json')
        try:
            with self._client.stream('POST', self.rest_url, data=form) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_bytes(chunk_size=16 * 1024):
                    if len(payload) + len(chunk) > byte_budget:
                        raise ValueError(f'{label} response exceeds its byte budget')
                    payload.extend(chunk)
        except httpx.HTTPError:
            raise ConnectionError(f'{label} transport failed') from None
        try:
            data = json.loads(payload)
        except (ValueError, UnicodeError):
            raise ValueError(f'Invalid {label} response') from None
        if not isinstance(data, dict):
            raise ValueError(f'Invalid {label} response')
        if 'exception' in data:
            # Do not propagate arbitrary plugin debug details or server paths.
            raise MoodleAPIError(f'{label} source rejected the request', error_code=data.get('errorcode'))
        return data
