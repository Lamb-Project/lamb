"""Session response language, initialized once without rewriting cached history."""
import re
LANGUAGES = {'en': 'English', 'es': 'Spanish', 'ca': 'Catalan', 'eu': 'Basque'}


def validate_ui_language(body):
    if 'ui_language' in body:
        value = body['ui_language']
        if not isinstance(value, str) or value not in LANGUAGES:
            raise ValueError('ui_language must be en, es, ca or eu')


def apply_ui_language(agent, code):
    state = getattr(agent, "skill_state", None)
    if state is None:
        return
    # Saved language wins across UI changes and reopened sessions. Legacy sessions
    # without one adopt the first supplied locale, once, without rewriting history.
    saved = state.get('ui_language')
    if saved in LANGUAGES:
        code = saved
    elif code is None:
        return
    validate_ui_language({'ui_language': code})
    state.setdefault('context', {})['language'] = LANGUAGES[code]
    if state.get('language_pinned'):
        return
    # Append once for the lifetime of the session. Keep the pinned system prefix and earlier turns intact.
    # A system message gives trusted UI metadata precedence over legacy language rules.
    agent.conversation.append({'role': 'system', 'content': (
        '[Application response language]\n'
        f'The language fixed when this session started is {LANGUAGES[code]} ({code}). '
        f'Use {LANGUAGES[code]} for your replies, explanations, canvas headings and confirmation questions. '
        'This session language takes precedence over matching the user-message language. '
        'Keep commands and resource names unchanged. If the user requests content in another language, '
        'write that requested content in that language, while keeping your surrounding explanation in the frontend language.'
    )})
    state['ui_language'] = code
    state['language_pinned'] = True


TURN_INSTRUCTIONS = {
    'en': 'The session language is English. Reply to the user in English for this turn, even if their message is in another language.',
    'es': 'El idioma de esta sesión es español. Responde al usuario en español en este turno, aunque su mensaje esté en otro idioma. Traduce también los encabezados y opciones: usa «¿Qué hacemos ahora?» en vez de «Next?» y «Otra cosa: dime» en vez de «Other — tell me».',
    'ca': 'La llengua d’aquesta sessió és el català. Respon a l’usuari en català en aquest torn, encara que el seu missatge sigui en una altra llengua. Tradueix també els encapçalaments i les opcions: «Què fem ara?» en lloc de «Next?».',
    'eu': 'The session language is Basque (Euskara). Reply to the user in Basque for this turn, even if their message is in another language.',
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


def confirmation_fallback(agent):
    """A provider ignoring disabled tools must still expose the saved approval."""
    code = (agent.skill_state or {}).get('ui_language', 'en')
    messages = {
        'en': ('This action is awaiting your approval and has not been executed:', 'Approve this action? Reply yes or no.'),
        'es': ('Esta acción está pendiente de tu aprobación y no se ha ejecutado:', '¿Apruebas esta acción? Responde sí o no.'),
        'ca': ('Aquesta acció està pendent de la teva aprovació i no s’ha executat:', 'Aproves aquesta acció? Respon sí o no.'),
        'eu': ('Ekintza hau zure onarpenaren zain dago; ez da exekutatu:', 'Ekintza onartzen duzu? Erantzun bai edo ez.'),
    }
    intro, question = messages.get(code, messages['en'])
    command = agent.pending_action.get('command', '')
    fence = '`' * max(3, max((len(part) for part in re.findall(r'`+', command)), default=0) + 1)
    return f'{intro}\n\n{fence}text\n{command}\n{fence}\n\n{question}'
