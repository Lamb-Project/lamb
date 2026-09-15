"""Bounded frontend response-language metadata, appended without rewriting history."""
LANGUAGES = {'en': 'English', 'es': 'Spanish', 'ca': 'Catalan', 'eu': 'Basque'}


def validate_ui_language(body):
    if 'ui_language' in body:
        value = body['ui_language']
        if not isinstance(value, str) or value not in LANGUAGES:
            raise ValueError('ui_language must be en, es, ca or eu')


def apply_ui_language(agent, code):
    # Clients without UI metadata keep their existing language behavior.
    if code is None:
        return
    validate_ui_language({'ui_language': code})
    state = agent.skill_state
    state.setdefault('context', {})['language'] = LANGUAGES[code]
    if state.get('ui_language') == code:
        return
    # Only append on changes. Keep the pinned system prefix and earlier turns intact.
    # A system message gives trusted UI metadata precedence over legacy language rules.
    agent.conversation.append({'role': 'system', 'content': (
        '[Application response language]\n'
        f'The frontend-selected language is {LANGUAGES[code]} ({code}). '
        f'Use {LANGUAGES[code]} for your replies, explanations, canvas headings and confirmation questions. '
        'This supersedes earlier language rules, including never switching language or matching user-message language. '
        'Keep commands and resource names unchanged. If the user requests content in another language, '
        'write that requested content in that language, while keeping your surrounding explanation in the frontend language.'
    )})
    state['ui_language'] = code


TURN_INSTRUCTIONS = {
    'en': 'The UI language is English. Reply to the user in English for this turn, even if their message is in another language.',
    'es': 'El idioma de la interfaz es español. Responde al usuario en español en este turno, aunque su mensaje esté en otro idioma.',
    'ca': 'La llengua de la interfície és el català. Respon a l’usuari en català en aquest torn, encara que el seu missatge sigui en una altra llengua.',
    'eu': 'The UI language is Basque (Euskara). Reply to the user in Basque for this turn, even if their message is in another language.',
}


def append_turn_language(agent):
    """Place a compact reminder at the turn tail for models ignoring later system roles.

    Called after confirmation classification and once per turn, not per tool round.
    Earlier conversation bytes remain unchanged, preserving the reusable KV prefix.
    """
    code = (agent.skill_state or {}).get('ui_language')
    if code in TURN_INSTRUCTIONS:
        agent.conversation.append({'role': 'user', 'content':
            '[System: Frontend response language]\n' + TURN_INSTRUCTIONS[code] +
            ' Keep resource names and commands unchanged. Explicitly requested foreign-language content may use its requested language.'})
