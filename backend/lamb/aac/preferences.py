"""Organization-owned agent policy. Session language never follows later UI changes."""
from lamb.aac.language import LANGUAGES


def language_code(value):
    if not isinstance(value, str) or value not in LANGUAGES:
        raise ValueError('Language must be en, es, ca or eu')
    return value


def agent_settings(config):
    if not isinstance(config, dict):
        return {}
    settings = config.get('setups', {}).get('default', {}).get('aac', {})
    if settings is None:
        return {}
    if not isinstance(settings, dict):
        raise ValueError('Invalid organization agent settings; ask the administrator to correct them')
    return settings


def validate_settings(settings, providers):
    allowed = {'provider', 'model', 'language_fallbacks', 'pack_channel', 'pack_version', 'utility_provider', 'utility_model'}
    if not isinstance(settings, dict) or set(settings) - allowed:
        raise ValueError('Unknown LAMB AGENT setting')
    result = {}
    for prefix in ('', 'utility_'):
        provider, model = settings.get(prefix+'provider', ''), settings.get(prefix+'model', '')
        if not isinstance(provider, str) or not isinstance(model, str):
            raise ValueError('Provider and model must be strings')
        provider, model = provider.strip(), model.strip()
        if bool(provider) != bool(model):
            raise ValueError('Choose both provider and model, or leave both empty')
        if provider:
            if provider not in {'openai', 'ollama'}:
                raise ValueError('LAMB AGENT supports OpenAI-compatible and Ollama providers')
            config = providers.get(provider, {})
            if not config or config.get('enabled') is False:
                raise ValueError('The selected provider is not enabled in this organization')
            models = config.get('models') or []
            if models and model not in models and model != config.get('default_model'):
                raise ValueError('Choose a model configured for this organization')
        result[prefix+'provider'], result[prefix+'model'] = provider, model
    fallbacks = settings.get('language_fallbacks', {})
    if not isinstance(fallbacks, dict):
        raise ValueError('Language fallbacks must be a mapping')
    for source, target in fallbacks.items():
        if source not in LANGUAGES or not isinstance(target, str) or target not in LANGUAGES:
            raise ValueError('Language fallbacks must use en, es, ca or eu')
        if source == target or target in fallbacks:
            raise ValueError('Fallbacks must point directly to a supported language; no chains or cycles')
    result['language_fallbacks'] = dict(fallbacks)
    channel, version = settings.get('pack_channel', 'stable'), settings.get('pack_version', '')
    if channel not in ('stable', 'rc', 'beta') or not isinstance(version, str):
        raise ValueError('Choose stable, rc or beta, or a released pack version')
    result.update(pack_channel=channel, pack_version=version)
    # The pack loader validates availability and installed-engine compatibility.
    if version:
        import re
        if not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError('Pack version must be major.minor.patch')
    return result


def response_policy(resolver, requested):
    requested = language_code(requested)
    config = resolver.organization.get('config', {})
    settings = agent_settings(config)
    providers = config.get('setups', {}).get('default', {}).get('providers', {})
    checked = validate_settings(settings, providers)
    effective = checked['language_fallbacks'].get(requested, requested)
    model = checked if checked['provider'] else resolver.get_global_default_model_config()
    return {'requested_language': requested, 'effective_language': effective,
            'fallback_applied': requested != effective,
            'provider': model.get('provider', ''), 'model': model.get('model', '')}


def apply_policy(agent, policy):
    state = agent.skill_state
    state.setdefault('context', {})['language'] = LANGUAGES[policy['effective_language']]
    if state.get('applied_response_policy') == policy:
        return
    effective = LANGUAGES[policy['effective_language']]
    requested = LANGUAGES[policy['requested_language']]
    agent.conversation.append({'role': 'system', 'content': (
        '[Application agent policy]\n'
        f'This session started in {requested}. The organization response policy selects {effective}. '
        f'Use {effective} for explanations and confirmations. Keep commands and resource names unchanged. '
        'Explicitly requested foreign-language content may use its requested language. '
        'This policy supersedes older response-language instructions; later frontend changes do not change the session language.'
    )})
    state['response_language_policy'] = dict(policy)
    state['applied_response_policy'] = dict(policy)
    if policy['fallback_applied']:
        notices = {
            'en': f'This session uses {effective}: your organization administrator configured that fallback for {requested}.',
            'es': f'Esta sesión usa {effective}: la administración de tu organización ha configurado esa alternativa para {requested}.',
            'ca': f'Aquesta sessió utilitza {effective}: l’administració de la teva organització ha configurat aquesta alternativa per a {requested}.',
            'eu': f'Saio honek {effective} erabiltzen du: erakundeko administratzaileak ordezko hizkuntza hori ezarri du {requested} hizkuntzarako.',
        }
        agent.conversation.append({'role':'assistant', 'content':notices[policy['effective_language']]})
