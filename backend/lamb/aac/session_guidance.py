"""Explicit instruction compatibility, independent of deploy/build timestamps."""
# Bump only for a deliberate instruction-policy change, not each deployment.
POLICY_VERSION = 3


def refresh_guidance(agent, state, session, skills_dir):
    previous = state.get('system_prompt')
    refresh = not previous or (state.get('policy_version') != POLICY_VERSION and not session.get('pending_action'))
    if not refresh:
        return None
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
            (m.get('role') == 'user' and not m['content'].startswith(('[System:', '[Application workflow instructions]'))))]
    state = session.get('skill_info') or {}
    result['skill_info'] = {k: state[k] for k in ('skill_id', 'context', 'ui_language', 'language_pinned', 'started', 'policy_version') if k in state}
    result['skill_info']['snapshots_count'] = len(state.get('snapshots', {}))
    result['tool_audit_count'] = len(session.get('tool_audit') or [])
    result.pop('tool_audit', None)
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
