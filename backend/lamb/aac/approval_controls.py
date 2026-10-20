"""Owner/session/turn-bound decisions for the currently prepared action."""
import hashlib
import json


LABELS = {
    'en': ('Approve', 'Create', 'Create and import', 'Edit proposal', 'Cancel', 'Describe what you want to change.'),
    'es': ('Aprobar', 'Crear', 'Crear e importar', 'Editar propuesta', 'Cancelar', 'Describe qué quieres cambiar.'),
    'ca': ('Aprovar', 'Crear', 'Crear i importar', 'Editar proposta', 'Cancel·lar', 'Descriu què vols canviar.'),
    'eu': ('Onartu', 'Sortu', 'Sortu eta inportatu', 'Proposamena editatu', 'Utzi', 'Azaldu zer aldatu nahi duzun.'),
}


def action_id(action):
    # New proposals carry a nonce. The content digest also invalidates a card if
    # its command/review changes. Older saved proposals remain usable.
    return hashlib.sha256(json.dumps([action.get('nonce'), action.get('tool_call_id'),
        action['command'], action.get('moodle_review')], sort_keys=True).encode()).hexdigest()


def card(action, state=None):
    if not action:
        return None
    state = state or {}
    language = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))
    labels = LABELS.get(language, LABELS['en'])
    destination = (action.get('moodle_review') or {}).get('destination', {})
    index = 2 if destination.get('new_kb') else 1 if (action.get('action_key') or '').endswith('.create') else 0
    return {'action_id': action_id(action), 'approve_label': labels[index], 'edit_label': labels[3],
            'cancel_label': labels[4], 'edit_hint': labels[5]}


def validate_decision(session, body):
    """Called under the session turn lock, before allocating an agent/client."""
    from fastapi import HTTPException
    decision = body.get('approval')
    if decision is None:
        return None
    if (not isinstance(decision, dict) or set(decision) != {'action_id', 'decision'}
            or decision.get('decision') not in {'approve', 'reject', 'edit'}):
        raise HTTPException(400, 'Invalid approval decision')
    action = session.get('pending_action')
    if not action or decision['action_id'] != action_id(action):
        raise HTTPException(409, 'This proposal has changed or was already handled. Reload the conversation before deciding.')
    return decision['decision']
