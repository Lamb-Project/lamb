"""Current administrative reminders, independent of saved conversations and packs."""
from urllib.parse import urlencode

from lamb.lti_access import organization_url


def admin_reminders(auth):
    organization = auth.organization
    if (not (auth.is_org_admin or auth.is_system_admin) or not organization
            or organization.get('is_system') or organization.get('status', 'active') != 'active'
            or organization_url(organization)):
        return []
    query = {'view': 'settings', 'section': 'lti-creator'}
    if auth.is_system_admin:
        query['org'] = organization['slug']
    return [{'id': 'lms_origin_unset', 'organization_id': organization['id'],
             'settings_path': '/org-admin?' + urlencode(query)}]


def reminder_context(auth):
    if not admin_reminders(auth):
        return ''
    return ('\n\nCurrent organization setup: the LMS origin has not been configured. '
            'The LEGATUS panel already reminds this administrator to set the Moodle URL in '
            'Organization settings > LTI Creator. LTI access continues without the organization '
            'origin check until it is set; any global LMS whitelist still applies. '
            'If asked, explain this and guide them to that setting. Do not repeat the reminder '
            'in unrelated answers, guess an origin, or change settings without a request. '
            'This is current application context, not a user request to start work.')
