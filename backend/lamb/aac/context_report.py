"""Content-free report: python -m lamb.aac.context_report /path/to/aac_logs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def distribution(values):
    values = sorted(values)
    if not values:
        return {'count': 0, 'median': None, 'p95': None, 'max': None}
    return {'count': len(values), 'median': values[(len(values)-1)//2],
            'p95': values[math.ceil(len(values)*.95)-1], 'max': values[-1]}


def summarize(paths):
    requests, responses, turns, tools = {}, {}, {}, {}
    all_sessions, measured_sessions = set(), set()
    malformed = 0
    for path in paths:
        with open(path, encoding='utf-8') as file:
            for line in file:
                try:
                    entry = json.loads(line)
                    sid, event, data = entry['session_id'], entry['event'], entry.get('data', {})
                    if not isinstance(data, dict):
                        raise ValueError('invalid data')
                    all_sessions.add(sid)
                    if event == 'context_request' and data.get('measurement_version') == 1:
                        requests[(sid, data['request_id'])] = data
                        measured_sessions.add(sid)
                        for result in data['tool_results']:
                            key = (sid, result['message_index'])
                            if result['content_bytes'] >= tools.get(key, {}).get('content_bytes', -1):
                                tools[key] = result
                    elif event == 'context_response':
                        responses[(sid, data['request_id'])] = data
                    elif event == 'context_turn':
                        turns[(sid, data['turn_id'])] = data
                except (ValueError, KeyError, TypeError):
                    malformed += 1
    commands = defaultdict(list)
    for tool in tools.values():
        commands[tool['command']].append(tool['content_bytes'])
    sessions = {}
    providers = defaultdict(list)
    for key, request in requests.items():
        sid = key[0]
        row = sessions.setdefault(sid, {'session_id': sid, 'requests': 0, 'peak_request_json_bytes': 0,
                                      'peak_prompt_tokens': None, 'size_rejections': 0})
        row['requests'] += 1
        row['peak_request_json_bytes'] = max(row['peak_request_json_bytes'], request['request_json_bytes'])
        response = responses.get(key, {})
        tokens = (response.get('usage') or {}).get('prompt_tokens')
        if tokens is not None:
            row['peak_prompt_tokens'] = max(row['peak_prompt_tokens'] or 0, tokens)
            providers[request['model']].append(tokens)
        row['size_rejections'] += response.get('outcome') == 'context_rejected'
    return {
        'measurement_version': 1, 'sessions_seen': len(all_sessions),
        'sessions_measured': len(measured_sessions), 'sessions_without_measurements': len(all_sessions-measured_sessions),
        'malformed_lines': malformed, 'requests': len(requests),
        'requests_without_response_observation': len(set(requests)-set(responses)),
        'requests_without_prompt_usage': sum((responses.get(k, {}).get('usage') or {}).get('prompt_tokens') is None for k in requests),
        'request_json_bytes': distribution([r['request_json_bytes'] for r in requests.values()]),
        'system_prompt_bytes': distribution([r['system_prompt_bytes'] for r in requests.values()]),
        'tool_schema_json_bytes': distribution([r['tool_schema_json_bytes'] for r in requests.values()]),
        'prompt_tokens_by_model': {m: distribution(v) for m,v in sorted(providers.items())},
        'outcomes': dict(Counter(r['outcome'] for k,r in responses.items() if k in requests)),
        'turns': len(turns), 'round_limit_turns': [dict(session_id=k[0], **r) for k,r in turns.items() if r['round_limit_reached']],
        'tool_result_content_bytes_by_command': {k: dict(distribution(v), total=sum(v)) for k,v in sorted(commands.items(), key=lambda pair: sum(pair[1]), reverse=True)},
        'sessions_by_peak_size': sorted(sessions.values(), key=lambda r:r['peak_request_json_bytes'], reverse=True),
        'notes': ['Bytes are UTF-8 compact JSON sizes, not tokens or a context-window estimate.',
                  'Tool results deduplicate by session and message position, retaining the largest observed size.',
                  'Historical uninstrumented requests cannot be reconstructed from truncated session logs.',
                  'Missing provider usage remains unknown, including interrupted streams.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, help='Session JSONL file or private log directory')
    args = parser.parse_args()
    paths = sorted(args.path.rglob('*.jsonl')) if args.path.is_dir() else [args.path]
    print(json.dumps(summarize(paths), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
