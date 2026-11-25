"""Commands that ran without a guide, read from the private session traces (issue #567).

Each `unguided_command` event holds a command name, why no guide was read, the pack and
the outcome. It holds no argument and no content, so this summary needs neither.
The commands that recur and succeed are the candidates for the next guides.

Usage: python -m lamb.aac.unguided [--days N] [--json]
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from lamb.aac.session_logger import _get_log_dir

OUTCOMES = ('succeeded', 'failed', 'awaiting_approval')


def summarize(log_dir=None, since=None):
    """Rows of {command, reason, pack_version, attempts, succeeded, failed, awaiting_approval,
    sessions, users}, most attempted first. `since` is a naive UTC datetime."""
    root = Path(log_dir or _get_log_dir())
    rows = defaultdict(lambda: {'attempts': 0, **{o: 0 for o in OUTCOMES}, 'sessions': set(), 'users': set()})
    if root.is_dir():
        for path in sorted(root.rglob('*.jsonl')):
            try:
                lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
            except OSError:
                continue
            for line in lines:
                if '"unguided_command"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                    data = entry['data']
                    moment = datetime.fromisoformat(entry['ts'].rstrip('Z'))
                except (ValueError, KeyError, TypeError):
                    continue
                if entry.get('event') != 'unguided_command' or (since and moment < since):
                    continue
                row = rows[(data.get('command'), data.get('reason'), data.get('pack_version'))]
                row['attempts'] += 1
                if data.get('outcome') in OUTCOMES:
                    row[data['outcome']] += 1
                row['sessions'].add(entry.get('session_id'))
                row['users'].add(path.parent.name)
    result = [{'command': command, 'reason': reason, 'pack_version': pack, **{k: v for k, v in row.items() if k not in ('sessions', 'users')},
               'sessions': len(row['sessions']), 'users': len(row['users'])}
              for (command, reason, pack), row in rows.items()]
    return sorted(result, key=lambda r: (-r['attempts'], str(r['command'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--days', type=int, help='only the last N days')
    parser.add_argument('--json', action='store_true')
    options = parser.parse_args()
    found = summarize(since=datetime.utcnow() - timedelta(days=options.days) if options.days else None)
    if options.json:
        print(json.dumps(found, indent=2))
    else:
        print(f"{'command':34} {'why':18} {'pack':12} {'tried':>5} {'ok':>4} {'failed':>6} {'asked':>5} {'sessions':>8} {'users':>5}")
        for r in found:
            print(f"{str(r['command']):34} {str(r['reason']):18} {str(r['pack_version']):12} {r['attempts']:>5} {r['succeeded']:>4} "
                  f"{r['failed']:>6} {r['awaiting_approval']:>5} {r['sessions']:>8} {r['users']:>5}")
        if not found:
            print('No command ran without a guide in these traces.')
