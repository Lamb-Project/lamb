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
    state = agent.skill_state or {}
    code = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language'))
    if code in TURN_INSTRUCTIONS:
        agent.conversation.append({'role': 'user', 'content':
            '[System: Frontend response language]\n' + TURN_INSTRUCTIONS[code] +
            ' Keep resource names and commands unchanged. Explicitly requested foreign-language content may use its requested language.'})


def confirmation_fallback(agent):
    """A provider ignoring disabled tools must still expose the saved approval."""
    state = agent.skill_state or {}
    code = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))
    messages = {
        'en': ('This action is awaiting your approval and has not been executed:', 'Approve this action? Reply yes or no.'),
        'es': ('Esta acción está pendiente de tu aprobación y no se ha ejecutado:', '¿Apruebas esta acción? Responde sí o no.'),
        'ca': ('Aquesta acció està pendent de la teva aprovació i no s’ha executat:', 'Aproves aquesta acció? Respon sí o no.'),
        'eu': ('Ekintza hau zure onarpenaren zain dago; ez da exekutatu:', 'Ekintza onartzen duzu? Erantzun bai edo ez.'),
    }
    intro, question = messages.get(code, messages['en'])
    from lamb.aac.approvals import render_details
    details = render_details(agent.pending_action, code, getattr(agent, 'approval_preferences', {}).get('advanced_mode') is True)
    if getattr(agent, 'interactive_approvals', False):
        return f'{intro}\n\n{details}'
    return f'{intro}\n\n{details}\n\n{question}'


def translation_confirmation(agent):
    """Render the interpretation independently of provider compliance.

    Translation is untrusted text. A literal block prevents its Markdown from
    hiding the actual interpretation or impersonating an approval control.
    """
    interpretations = (agent.pending_action or {}).get('machine_translation_interpretations', [])
    if not interpretations:
        return ''
    state = agent.skill_state or {}
    code = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))
    labels = {
        'en': ('Machine translation used for this proposed action', 'Original', 'Interpretation', 'Check this interpretation before approving.'),
        'es': ('Traducción automática usada para esta acción propuesta', 'Original', 'Interpretación', 'Comprueba esta interpretación antes de aprobar.'),
        'ca': ('Traducció automàtica usada per a aquesta acció proposada', 'Original', 'Interpretació', 'Comprova aquesta interpretació abans d’aprovar.'),
        'eu': ('Proposatutako ekintzarako erabilitako itzulpen automatikoa', 'Jatorrizkoa', 'Interpretazioa', 'Egiaztatu interpretazio hau onartu aurretik.'),
    }
    title, source_label, output_label, warning = labels.get(code, labels['en'])
    blocks = []
    for item in interpretations:
        content = f"{source_label}: {item['source']}\n{output_label}: {item['translation']}"
        fence = '`' * max(3, max((len(part) for part in re.findall(r'`+', content)), default=0) + 1)
        blocks.append(f'{fence}text\n{content}\n{fence}')
    return '\n\n' + title + '\n\n' + '\n\n'.join(blocks) + '\n\n' + warning


def documentation_fallback_notice(agent):
    """Expose English-source fallback even if the model omits the tool's notice."""
    state = agent.skill_state or {}
    notices = state.pop('documentation_notices', {})
    if not notices:
        return ''
    code = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))
    messages = {
        'en': 'These documentation sections are available only in English; English source material was used:',
        'es': 'Estas secciones de la documentación solo están disponibles en inglés; se ha consultado el original en inglés:',
        'ca': 'Aquestes seccions de la documentació només estan disponibles en anglès; s’ha consultat l’original en anglès:',
        'eu': 'Dokumentazio-atal hauek ingelesez bakarrik daude eskuragarri; ingelesezko jatorrizkoa erabili da:',
    }
    references = [f'`{topic}#{anchor}`' for topic, anchors in sorted(notices.items()) for anchor in anchors]
    return '\n\n' + messages.get(code, messages['en']) + ' ' + ', '.join(references)
