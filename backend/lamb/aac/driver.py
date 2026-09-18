"""Resolve the effective AAC destination without allocating an HTTP client."""
from fastapi import HTTPException


def resolve_driver(resolver):
    from lamb.aac.preferences import agent_settings
    try:
        settings = agent_settings(resolver.organization.get('config', {}))
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    explicit = bool(settings.get('provider') or settings.get('model'))
    default = settings if explicit else resolver.get_global_default_model_config()
    if explicit and (not settings.get('model') or settings.get('provider') not in {'openai', 'ollama'}):
        raise HTTPException(503, 'Invalid LAMB AGENT model configuration; ask the organization administrator to correct it')
    provider = default.get("provider") or "openai"
    if provider not in {"openai", "ollama"}:
        try:
            default = resolver.resolve_model_for_completion(
                default.get("model"), provider, available_providers={"openai", "ollama"})
            provider = default["provider"]
        except ValueError:
            raise HTTPException(503, "AAC needs an enabled OpenAI-compatible or Ollama provider in this organization")
    config = resolver.get_provider_config(provider)
    if not config or config.get("enabled") is False:
        raise HTTPException(status_code=503, detail=f"No enabled {provider} provider configured for this organization")
    model = default.get("model") or config.get("default_model")
    base_url = config.get("base_url")
    if provider == "ollama":
        if not base_url or not model:
            raise HTTPException(status_code=503, detail="AAC requires an Ollama base URL and default model")
        # Ollama's compatible endpoint accepts tools through the existing legacy loop.
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        api_key = config.get("api_key") or "ollama"
    else:
        api_key = config.get("api_key")
        if not api_key:
            raise HTTPException(status_code=503, detail="No OpenAI API key configured for this organization")
        if not model:
            raise HTTPException(503, "AAC requires a configured default model; ask the organization administrator")
    return {'provider': provider, 'model': model, 'base_url': base_url, 'api_key': api_key}


def public_driver(target):
    # Never disclose credentials or a proxy URL that may contain credentials.
    return {key: target[key] for key in ('provider', 'model')}
