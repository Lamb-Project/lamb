"""Model selection for new-assistant forms and configuration clients."""

def model_configuration(capabilities, form_defaults, global_default):
    connectors = capabilities.get('connectors', {})
    def models(provider):
        return connectors.get(provider, {}).get('available_llms', [])
    provider, model = global_default.get('provider', ''), global_default.get('model', '')
    available = bool(provider and model and model in models(provider))
    if available:
        selected_provider, selected_model = provider, model
    else:
        selected_provider = form_defaults.get('connector', '')
        if not models(selected_provider):
            selected_provider = next((name for name in connectors if name != 'bypass' and models(name)), '')
        preferred = form_defaults.get('llm', '')
        selected_model = preferred if preferred in models(selected_provider) else next(iter(models(selected_provider)), '')
    return {
        'global_default_model': {'provider': provider, 'model': model},
        'global_default_available': available,
        'model_defaults': {'connector': selected_provider, 'llm': selected_model},
    }
