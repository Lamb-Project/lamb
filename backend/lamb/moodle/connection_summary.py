"""Connection-page overview from standard Moodle services; only the owner's courses."""
from .connection import public_connection
from .policy import canonical_base_url
from .runtime import MoodleRuntime


def connection_summary(store):
    runtime = MoodleRuntime(store)
    binding = runtime.result_binding()
    info = runtime.execute('site.info', {})
    if (int(info.get('userid', 0)) != binding['moodle_user_id']
            or canonical_base_url(info.get('siteurl', '')) != binding['base_url']):
        raise PermissionError('Moodle identity changed; reconnect your account')
    courses = runtime.execute('course.list', {})
    snap = runtime.snapshot()
    if runtime.result_binding() != binding:
        raise PermissionError('Moodle connection changed; reload the page')
    # Never return tokens, site functions, other profile fields or course contents.
    return {
        'connection': public_connection(snap['record']),
        'release': str(info.get('release') or '')[:120],
        'courses': [{
            'id': c['id'], 'fullname': c.get('fullname', ''), 'shortname': c.get('shortname', ''),
            'my_roles': c.get('my_roles'), 'my_roles_status': c.get('my_roles_status', 'unavailable'),
        } for c in courses],
    }
