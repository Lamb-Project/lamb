"""The auxiliary model: the organization's small/fast model, else LAMB LEGATUS's own driver.

Used for bounded side work (approval sentences, reading a Moodle document) so the main
conversation never carries the source. Credentials stay here; callers get provider/model only.
"""


def small_fast_target(owner):
    """Endpoint of the configured small/fast model, or ValueError when none is usable."""
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    resolver = OrganizationConfigResolver(owner)
    selected = resolver.get_small_fast_model_config()
    provider, model = selected.get('provider'), selected.get('model')
    config = resolver.get_provider_config(provider) if provider else {}
    if not model or provider not in {'openai', 'ollama'} or not config or config.get('enabled') is False:
        raise ValueError('Small/fast model unavailable')
    base, key = config.get('base_url'), config.get('api_key')
    if provider == 'ollama':
        if not base: raise ValueError('Small/fast model endpoint unavailable')
        base = base.rstrip('/')
        if not base.endswith('/v1'): base += '/v1'
        key = key or 'ollama'
    if not key: raise ValueError('Small/fast model credentials unavailable')
    return {'provider': provider, 'model': model, 'base_url': base, 'api_key': key}


def helper_target(owner):
    """Small/fast model when configured; otherwise the driver already disclosed for LAMB LEGATUS."""
    try:
        return small_fast_target(owner)
    except ValueError:
        pass
    from fastapi import HTTPException
    from lamb.aac.driver import resolve_driver
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    try:
        target = resolve_driver(OrganizationConfigResolver(owner))
    except HTTPException as exc:
        raise ValueError(f'No helper model is configured: {exc.detail}') from None
    return {'provider': target['provider'], 'model': target['model'],
            'base_url': target['base_url'], 'api_key': target['api_key']}


def request_options(model):
    # Same reasoning setting the approval sentence uses for this model family.
    return {'reasoning_effort': 'none'} if model.lower().startswith('gpt-5.6') else {}
