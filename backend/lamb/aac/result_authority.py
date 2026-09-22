"""Conservative current-resource authority for immutable AAC snapshots.

An unrecognized command is not evidence of public/owner-only source data. Its
historical snapshot is withheld until a resource-specific authority is defined;
the caller gets a recovery instruction, never an automatic replay of a write.
"""

SAFE_LOCAL = frozenset({'help', 'docs.index', 'docs.read', 'skill.list', 'skill.load'})
ASSISTANT_READS = frozenset({'assistant.get', 'assistant.export'})
KB_READS = frozenset({'kb.get', 'kb.query', 'kb.jobs', 'kb.status'})


def authority(key, args, payload):
    if key in SAFE_LOCAL:
        return {'version': 1, 'resources': []}
    kind = 'assistant' if key in ASSISTANT_READS else 'kb' if key in KB_READS else None
    if kind and args:
        identity = str(args[0])
        if kind == 'assistant' and not identity.isdigit():
            data = payload.get('data')
            identity = str(data.get('id', '')) if isinstance(data, dict) else ''
        if identity.isdigit() and int(identity) > 0:
            return {'version': 1, 'resources': [{'kind': kind, 'id': int(identity)}]}
    return None


def require_current_authority(auth, origin):
    key = origin['command']
    proof = origin.get('authority')
    if not isinstance(proof, dict) or proof.get('version') != 1:
        raise PermissionError('Saved result lacks current-resource authority. Run a fresh read for current details; never repeat a write to recover a result.')
    resources = proof.get('resources')
    if not isinstance(resources, list) or len(resources) > 100:
        raise PermissionError('Saved result authority is unavailable')
    if key in SAFE_LOCAL and not resources:
        return
    expected = 'assistant' if key in ASSISTANT_READS else 'kb' if key in KB_READS else None
    if expected is None or len(resources) != 1:
        raise PermissionError('Saved result requires a fresh resource-authorized read; do not repeat a write')
    for resource in resources:
        if resource.get('kind') != expected or type(resource.get('id')) is not int or resource['id'] <= 0:
            raise PermissionError('Saved result authority is unavailable')
        access = (auth.can_access_assistant(resource['id']) if expected == 'assistant'
                  else auth.can_access_kb(str(resource['id'])))
        if access not in {'owner', 'shared', 'org_admin'}:
            raise PermissionError('Result unavailable for your current resource permissions')
