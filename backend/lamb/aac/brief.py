"""Session situation and installation capabilities. Facts come from trusted registries."""
import importlib
import json


def role_axes(auth):
    creator_kind = 'lti_creator' if auth.user.get('auth_provider') == 'lti_creator' else 'creator'
    administration = 'admin' if auth.is_system_admin else ('org_admin' if auth.is_org_admin else 'none')
    layers = ['creator']
    if creator_kind == 'lti_creator':
        layers.append('lti')
    if administration in ('org_admin', 'admin'):
        layers.append('org_admin')
    if administration == 'admin':
        layers.append('admin')
    return {'creator_kind': creator_kind, 'administration': administration, 'layers': layers}


def processor_registry():
    from lamb.completions.main import load_plugins
    result = {}
    for category, plugin_type in [('rag_processors','rag'),('prompt_processors','pps'),('connectors','connectors')]:
        result[category] = []
        for name in sorted(load_plugins(plugin_type)):
            module = importlib.import_module(f'lamb.completions.{plugin_type}.{name}')
            description = getattr(module, 'AAC_DESCRIPTION', None)
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f'Missing capability description: {plugin_type}/{name}')
            result[category].append({'id':name, 'description':description})
    return result


def route_paths(routes):
    for route in routes:
        yield getattr(route, 'path', '')
        app = getattr(route, 'app', None)
        if hasattr(app, 'routes'):
            yield from route_paths(app.routes)


async def capability_map(auth, routes=()):
    result = processor_registry()
    providers = (auth.organization.get('config') or {}).get('setups', {}).get('default', {}).get('providers', {})
    for item in result['connectors']:
        item['configured'] = bool(providers.get(item['id'])) and providers[item['id']].get('enabled') is not False
    # The KB's own plugin registry is authoritative, including module-owned descriptions.
    from creator_interface.knowledges_router import kb_server_manager
    try:
        plugins = await kb_server_manager.get_ingestion_plugins()
        if isinstance(plugins, dict):
            plugins = plugins.get('plugins', [])
        result['ingestion_plugins'] = {'status':'available', 'items':[
            {'id':item['name'], 'description':item.get('description', '')}
            for item in plugins if isinstance(item, dict) and item.get('name')]}
    except Exception:
        result['ingestion_plugins'] = {'status':'unavailable', 'items':[]}
    result['lti'] = {'available':any('lti' in path.lower() for path in route_paths(routes))}
    return result


def session_brief(auth, language, capabilities, documentation_coverage, pack):
    axes = role_axes(auth)
    glossary = pack.data(f'glossary/{language}.yaml')
    return {'schema_version':1, **axes,
            'user':{'id':auth.user['id'], 'email':auth.user['email']},
            'organization':{key:auth.organization.get(key) for key in ('id','name','slug')},
            'session_language':language, 'documentation_coverage':documentation_coverage,
            'capabilities':capabilities, 'pack_version':pack.version, 'pack_hash':pack.fingerprint,
            'glossary':glossary}


def render_brief(brief):
    return '# Session brief (trusted application facts)\n' + json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n\n'
