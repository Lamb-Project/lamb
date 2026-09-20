"""Current authenticated authority for saved result readback, shared by CLI/LiteShell."""
from lamb.aac.result_store import ResultStore, page


def read_result(auth, identity, path='', offset=0):
    from lamb.aac.pack_loader import load_pack, allowed_commands, allowed_skills
    from lamb.aac.preferences import agent_settings
    from lamb.aac.brief import role_axes
    stored = ResultStore(int(auth.organization['id']), int(auth.user['id'])).read(identity)
    pack = load_pack(agent_settings(auth.organization.get('config', {})))
    layers = role_axes(auth)['layers']
    key = stored['origin']['command']
    if key not in allowed_commands(pack,layers) and key != 'unknown' and not key.startswith('moodle.'):
        raise PermissionError('Result unavailable for your current role')
    if stored['origin'].get('skill_id') and stored['origin']['skill_id'] not in allowed_skills(pack,layers):
        raise PermissionError('Workflow result unavailable for your current role')
    binding = stored['origin'].get('moodle')
    if key.startswith('moodle.') and binding is None:
        raise PermissionError('Moodle result lacks a verifiable connection binding')
    if binding:
        from lamb.moodle.runtime import MoodleRuntime
        from lamb.moodle.store import ConnectionStore
        from lamb.moodle.router import database
        runtime = MoodleRuntime(ConnectionStore(database(), auth.organization['id'], auth.user['id']))
        runtime.validate_result_binding(binding,key)
    result = page(stored,path,offset)
    if binding: runtime.validate_result_binding(binding,key)
    return result
