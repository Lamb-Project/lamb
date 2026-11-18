"""Current administrative reminders, independent of saved conversations and packs."""
from urllib.parse import urlencode

from lamb import lti_access


def _database():
    from lamb.database_manager import LambDatabaseManager
    return LambDatabaseManager()


def admin_reminders(auth, db=None):
    """One reminder: the organization accepts LTI 1.1 launches from any installation that
    holds the credentials, and its administrator can lock it to the ones it is used from.
    Only when there is something to lock to: the administrator's own LMS session, or an
    installation already seen. The lock is optional; the reminder goes once it is set."""
    organization = auth.organization
    if (not (auth.is_org_admin or auth.is_system_admin) or not organization
            or organization.get('is_system') or organization.get('status', 'active') != 'active'
            or lti_access.locked_instances(organization)):
        return []
    if not lti_access.session_instance(getattr(auth, 'token_payload', None)):
        try:
            if not lti_access.seen_instances(db or _database(), organization['id']):
                return []
        except Exception:
            return []
    query = {'view': 'settings', 'section': 'lti-creator'}
    if auth.is_system_admin:
        query['org'] = organization['slug']
    return [{'id': 'lms_origin_unset', 'organization_id': organization['id'],
             'settings_path': '/org-admin?' + urlencode(query)}]


def reminder_context(auth, db=None):
    if not admin_reminders(auth, db):
        return ''
    return ('\n\nCurrent organization setup: this organization is not locked to its LMS. '
            'The LEGATUS panel already reminds this administrator that they can lock it in '
            'Organization settings > LTI Creator, by choosing the LMS installation they use. '
            'The lock is optional: without it LTI launches keep working from any installation '
            'that holds the LTI credentials; any system whitelist still applies. '
            'If asked, explain this and guide them to that setting. Do not repeat the reminder '
            'in unrelated answers, guess an installation, or change settings without a request. '
            'This is current application context, not a user request to start work.')
