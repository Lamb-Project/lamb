"""Explicit instruction compatibility, independent of deploy/build timestamps."""
# Bump only for a deliberate instruction-policy change, not each deployment.
POLICY_VERSION = 4


def refresh_guidance(agent, state, session, skills_dir):
    previous = state.get('system_prompt')
    pack = getattr(agent, 'pack', None)
    pack_changed = pack and state.get('pack_version') != pack.version
    refresh = not previous or ((state.get('policy_version') != POLICY_VERSION or pack_changed) and not session.get('pending_action'))
    if not refresh:
        if pack and state.get('pack_hash') and state['pack_hash'] != pack.fingerprint:
            raise ValueError('Pinned pack content changed without a new version')
        return None
    if pack and state.get('brief'):
        from lamb.aac.pack_loader import render_prefix
        brief = dict(state['brief'])
        brief.update(pack_version=pack.version, pack_hash=pack.fingerprint,
                     glossary=pack.data(f"glossary/{brief['session_language']}.yaml"))
        state['brief'] = brief
        agent.system_prompt = render_prefix(pack, brief)
        state.update(pack_version=pack.version, pack_hash=pack.fingerprint)
    else:
        agent.load_skills(skills_dir)
    state.update(system_prompt=agent.system_prompt, routing_version=1, policy_version=POLICY_VERSION)
    state.pop('active_snapshot', None)
    if previous:
        return guidance_notice(state, 'updated')
    return None


def browser_session(session):
    """Owner-visible transcript; detailed prompts remain available to diagnostics."""
    result = dict(session)
    result['conversation'] = [dict(m) for m in session.get('conversation', [])
        if isinstance(m.get('content'), str) and (
            (m.get('role') == 'assistant' and not m.get('tool_calls')) or
            (m.get('role') == 'user' and not m['content'].startswith(('[System:', '[Application workflow instructions]', '[Application learning scenario context]'))))]
    state = session.get('skill_info') or {}
    result['skill_info'] = {k: state[k] for k in ('learning_scenario_id', 'skill_id', 'context', 'ui_language', 'language_pinned', 'started', 'policy_version', 'brief', 'pack_version', 'response_language_policy') if k in state}
    result['skill_info']['snapshots_count'] = len(state.get('snapshots', {}))
    result['tool_audit_count'] = len(session.get('tool_audit') or [])
    result['charts'] = [dict(a) for event in session.get('tool_audit', []) if event.get('success')
                        for a in event.get('artifacts', []) if a.get('type') == 'chart']
    result.pop('tool_audit', None)
    from lamb.aac.approval_controls import card
    result['approval'] = card(result.pop('pending_action', None), state)
    return result


def guidance_notice(state, kind):
    messages = {
        'updated': {
            'en': 'Session instructions have been updated. Your conversation and saved actions are preserved.',
            'es': 'Se han actualizado las instrucciones de la sesión. Tu conversación y las acciones guardadas se conservan.',
            'ca': 'S’han actualitzat les instruccions de la sessió. Es conserven la conversa i les accions desades.',
            'eu': 'Saioaren jarraibideak eguneratu dira. Elkarrizketa eta gordetako ekintzak mantendu dira.',
        },
        'unavailable': {
            'en': 'The previous workflow is unavailable. I can continue with general help; your conversation and pending actions are preserved.',
            'es': 'El flujo de trabajo anterior ya no está disponible. Puedo seguir ayudándote de forma general; se conservan tu conversación y las acciones pendientes.',
            'ca': 'El flux de treball anterior ja no està disponible. Puc continuar ajudant-te de manera general; es conserven la conversa i les accions pendents.',
            'eu': 'Aurreko lan-fluxua ez dago erabilgarri. Laguntza orokorra eskaintzen jarrai dezaket; elkarrizketa eta zain dauden ekintzak mantendu dira.',
        },
    }
    return messages[kind].get(state.get('ui_language'), messages[kind]['en'])
