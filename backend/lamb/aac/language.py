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


def budget_notice(agent):
    """Execution fact only: reaching a budget does not prove task failure."""
    state = agent.skill_state or {}
    code = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))
    messages = {
        'en': 'This turn reached its tool-round limit ({limit}). No more tools will run this turn. If more investigation is needed, ask me to continue in this conversation.',
        'es': 'Este turno ha alcanzado su límite de rondas de herramientas ({limit}). No se ejecutarán más herramientas en este turno. Si hace falta investigar más, pídeme que continúe en esta conversación.',
        'ca': 'Aquest torn ha arribat al límit de rondes d’eines ({limit}). No s’executaran més eines en aquest torn. Si cal investigar més, demana’m que continuï en aquesta conversa.',
        'eu': 'Txanda hau tresna-txanden mugara iritsi da ({limit}). Ez da tresna gehiago exekutatuko txanda honetan. Gehiago ikertu behar bada, eskatu elkarrizketa honetan jarraitzeko.',
    }
    return messages.get(code, messages['en']).format(limit=agent.max_tool_rounds) + '\n\n'


# What the model reads in place of a stored budget notice. The displayed notice says "no more
# tools will run this turn"; left verbatim in history, models read it as a standing rule and
# refuse later turns ("continue") that have a fresh budget.
BUDGET_MODEL_NOTE = ('[Application note: the tool-round limit ({limit}) was reached at this point. The limit '
                     'counts tool rounds within one user turn and resets with every new user message: any later '
                     'turn, including a request to continue, has tools available again.]')

_BUDGET_NOTICE_PATTERNS = None


def is_budget_notice(text):
    """True for a stored budget notice in any supported language (sessions saved before the model note)."""
    global _BUDGET_NOTICE_PATTERNS
    if _BUDGET_NOTICE_PATTERNS is None:
        import re
        fake = type('A', (), {'max_tool_rounds': 0})
        patterns = []
        for code in ('en', 'es', 'ca', 'eu'):
            fake.skill_state = {'ui_language': code}
            template = budget_notice(fake).strip().replace('(0)', '({limit})')
            patterns.append(re.compile('^' + re.escape(template).replace(re.escape('{limit}'), r'\d+') + '$'))
        _BUDGET_NOTICE_PATTERNS = patterns
    return isinstance(text, str) and any(p.match(text.strip()) for p in _BUDGET_NOTICE_PATTERNS)


def budget_model_note(limit):
    return BUDGET_MODEL_NOTE.format(limit=limit)


_ANNOUNCED_WORK = None


def announces_unfinished_work(text):
    """True when a reply ends by announcing a step it did not take ("Voy a continuar con esa
    comprobación.") and neither asks the user nor offers options. Without a tool call such a reply
    ends the turn, so nothing happens (Marc, 28 Sep)."""
    global _ANNOUNCED_WORK
    import re
    if _ANNOUNCED_WORK is None:
        verbs_es = 'continuar|seguir|comprobar|revisar|obtener|preparar|buscar|leer|consultar|importar|crear|listar|verificar'
        _ANNOUNCED_WORK = re.compile('|'.join([
            rf'\bvoy a (?:{verbs_es})\b', r'\b(?:continuar|seguir|comprobar|revisar|obtendr|preparar|buscar|consultar|verificar)[éeá]\b',
            r'\ba continuaci[oó]n (?:voy|har[ée]|obtendr[ée]|comprobar[ée]|revisar[ée])\b',
            r"\bi(?:'ll| will) (?:now |next |then )?(?:continue|check|look|fetch|retrieve|get|prepare|read|search|proceed|verify|import|create|list)\b",
            r'\blet me (?:now )?(?:continue|check|look|fetch|retrieve|get|read|verify)\b',
            r'\b(?:continuar|comprovar|revisar|obtindr|preparar|cercar|consultar|verificar)[ée]\b',
            r'\b(?:jarraitu|egiaztatu|begiratu|prestatu|lortu|bilatu)ko dut\b']), re.I)
    tail = (text or '').strip()[-400:]
    if not tail or '?' in tail[-200:] or re.search(r'(?m)^\s*1\.\s.+\n\s*2\.\s', tail):
        return False
    last = re.split(r'(?<=[.!])\s+', tail)[-2:]
    return bool(_ANNOUNCED_WORK.search(' '.join(last)))


ANNOUNCED_WORK_NOTE = ('Your last reply announced a next step but called no tool, so the turn would end here and '
                       'nothing would happen. If you can take that step, call the tool now. If something blocks you '
                       '(a missing identifier, a permission, a user decision), tell the user exactly what is missing '
                       'and what you need. Do not announce work without doing it.')


_TEST_CHANGING = {'add', 'update', 'delete-case', 'delete-scenario', 'run', 'evaluate'}


def changed_test_assistant(command):
    """Assistant whose saved test cases or runs a successful `lamb test` command changed, or None.
    The frontend reloads that assistant's open test tab (Marc, 28 Sep)."""
    import shlex
    try:
        words = shlex.split(command or '')
    except ValueError:
        words = (command or '').split()
    if words[:2] != ['lamb', 'test'] or len(words) < 3 or words[2] not in _TEST_CHANGING:
        return None
    if '--assistant' in words:
        i = words.index('--assistant')
        value = words[i + 1] if i + 1 < len(words) else ''
    else:
        value = next((w for w in words[3:] if w.isdigit()), '')
    return int(value) if value.isdigit() else None


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


def _code(agent):
    state = agent.skill_state or {}
    return state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))


def pending_decision_notice(agent):
    """#495: a message that is not a decision never replaces or silently drops the pending proposal."""
    messages = {
        'en': 'A proposal is still waiting for your decision, so nothing else was done in this turn. Approve, reject or edit it; then ask again.',
        'es': 'Hay una propuesta esperando tu decisión, así que en este turno no se ha hecho nada más. Apruébala, recházala o edítala, y luego vuelve a pedirlo.',
        'ca': 'Hi ha una proposta esperant la teva decisió, així que en aquest torn no s’ha fet res més. Aprova-la, rebutja-la o edita-la, i després torna-ho a demanar.',
        'eu': 'Proposamen bat zure erabakiaren zain dago; beraz, txanda honetan ez da beste ezer egin. Onartu, baztertu edo editatu, eta gero eskatu berriro.',
    }
    return messages.get(_code(agent), messages['en']) + '\n\n'


def unqueued_write_notice(agent):
    """#495: a write shown only as text is not awaiting approval; say so instead of implying a button."""
    messages = {
        'en': 'Note: the change above has not been prepared for approval, so no confirmation button is shown and nothing will run. Ask me to prepare it if you want it applied.',
        'es': 'Nota: el cambio anterior no se ha preparado para aprobación; no hay botón de confirmación y no se ejecutará nada. Pídeme que lo prepare si quieres aplicarlo.',
        'ca': 'Nota: el canvi anterior no s’ha preparat per aprovar-lo; no hi ha botó de confirmació i no s’executarà res. Demana’m que el prepari si vols aplicar-lo.',
        'eu': 'Oharra: goiko aldaketa ez da onartzeko prestatu; ez dago berrespen-botoirik eta ez da ezer exekutatuko. Eskatu prestatzeko aplikatu nahi baduzu.',
    }
    return '\n\n' + messages.get(_code(agent), messages['en'])


def budget_empty_answer(agent, reads):
    """#521: the model returned no text after the tool budget; state what was read and how to continue."""
    messages = {
        'en': ('I could not write the answer within this turn. Reads completed: {n}{items}. Say “continue” to finish from this evidence.'),
        'es': ('No he podido redactar la respuesta en este turno. Lecturas completadas: {n}{items}. Di «continúa» para terminar a partir de estos datos.'),
        'ca': ('No he pogut redactar la resposta en aquest torn. Lectures completades: {n}{items}. Digues «continua» per acabar a partir d’aquestes dades.'),
        'eu': ('Ezin izan dut erantzuna idatzi txanda honetan. Amaitutako irakurketak: {n}{items}. Esan «jarraitu» datu hauetatik amaitzeko.'),
    }
    items = (' (' + '; '.join(reads[-6:]) + ')') if reads else ''
    # Every reply ends with the options list (pack 1.11.9), this application text included.
    options = {
        'en': '**Next?**\n1. Continue\n2. Other — tell me',
        'es': '**¿Qué hacemos ahora?**\n1. Continúa\n2. Otra cosa: dime',
        'ca': '**Què fem ara?**\n1. Continua\n2. Una altra cosa: digues-m’ho',
        'eu': '**Zer egingo dugu orain?**\n1. Jarraitu\n2. Beste zerbait: esan iezadazu',
    }
    code = _code(agent) if _code(agent) in messages else 'en'
    return messages[code].format(n=len(reads), items=items) + '\n\n' + options[code]


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
