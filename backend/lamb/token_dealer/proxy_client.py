"""Client for the proxy's admin API (LiteLLM v1.102.1, open-source endpoints only).

Fails closed: any connection problem raises ProxyUnavailable, any non-2xx answer ProxyError.
Callers decide what to do; issuance refuses, the worker retries on its next cycle.
Verified against the real proxy in the token-dealer swarm rig (workshop, 2026-10-11).
"""
from datetime import datetime, timezone

import httpx


class ProxyError(Exception):
    def __init__(self, status, detail):
        super().__init__(f'proxy answered {status}: {detail}')
        self.status, self.detail = status, detail


class ProxyUnavailable(ProxyError):
    def __init__(self, detail):
        super().__init__(0, detail)


def _ts(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


class ProxyClient:
    def __init__(self, base_url, admin_key, timeout=10.0, transport=None):
        self.base = base_url.rstrip('/')
        self._http = httpx.Client(base_url=self.base, timeout=timeout, transport=transport,
                                  headers={'Authorization': f'Bearer {admin_key}'})

    def close(self):
        self._http.close()

    def _call(self, method, path, json=None, params=None):
        try:
            r = self._http.request(method, path, json=json, params=params)
        except httpx.HTTPError as e:
            raise ProxyUnavailable(f'{type(e).__name__}: {e}') from e
        if r.status_code >= 300:
            raise ProxyError(r.status_code, r.text[:300])
        return r.json() if r.content else None

    def ready(self):
        try:
            return self._call('GET', '/health/readiness') is not None
        except ProxyError:
            return False

    def list_models(self):
        """Public model names the proxy serves (for the org-admin screen)."""
        return sorted({m['id'] for m in (self._call('GET', '/v1/models') or {}).get('data', [])})

    # teams: one per activity, carries the activity pool
    def create_team(self, alias, models, max_budget=None, metadata=None):
        body = {'team_alias': alias, 'models': models, 'metadata': metadata or {}}
        if max_budget is not None:
            body['max_budget'] = max_budget
        return self._call('POST', '/team/new', body)['team_id']

    def update_team(self, team_id, **fields):
        return self._call('POST', '/team/update', {'team_id': team_id, **fields})

    def delete_team(self, team_id):
        return self._call('POST', '/team/delete', {'team_ids': [team_id]})

    def team_info(self, team_id):
        return (self._call('GET', '/team/info', params={'team_id': team_id}) or {}).get('team_info', {})

    # keys: one per (student, activity)
    def generate_key(self, models, user_id, team_id, alias, metadata=None, max_budget=None, slot_budget=None,
                     slot_duration='10m', duration=None):
        body = {'models': models, 'user_id': user_id, 'team_id': team_id, 'key_alias': alias, 'metadata': metadata or {}}
        if max_budget is not None:
            body['max_budget'] = max_budget
        if slot_budget is not None:
            body['budget_limits'] = [{'budget_duration': slot_duration, 'max_budget': slot_budget}]
        if duration:
            body['duration'] = duration
        r = self._call('POST', '/key/generate', body)
        return {'key': r['key'], 'token': r['token']}

    def update_key(self, token, **fields):
        return self._call('POST', '/key/update', {'key': token, **fields})

    def block_key(self, token):
        return self._call('POST', '/key/block', {'key': token})

    def unblock_key(self, token):
        return self._call('POST', '/key/unblock', {'key': token})

    def delete_keys(self, tokens):
        return self._call('POST', '/key/delete', {'keys': list(tokens)})

    def key_info(self, token):
        return (self._call('GET', '/key/info', params={'key': token}) or {}).get('info', {})

    # usage
    def spend_logs(self, start, end, page=1, page_size=1000):
        """One page of /spend/logs/v2 between two epoch times (UTC). Refused requests are included."""
        return self._call('GET', '/spend/logs/v2', params={'start_date': _ts(start), 'end_date': _ts(end),
                                                           'page': page, 'page_size': page_size})

    def iter_spend_logs(self, start, end, page_size=1000):
        page = 1
        while True:
            r = self.spend_logs(start, end, page, page_size) or {}
            yield from r.get('data', [])
            if page >= (r.get('total_pages') or 1):
                return
            page += 1
