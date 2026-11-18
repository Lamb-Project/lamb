"""Organization activity catalogue and scoped entry into module management (#565)."""
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException

from lamb import activity_access, auth as lamb_auth
from lamb.auth_context import AuthContext, get_auth_context
from lamb.database_manager import LambDatabaseManager

router = APIRouter(tags=['Activities'])
db = LambDatabaseManager()


@router.get('')
def list_activities(auth: AuthContext = Depends(get_auth_context)):
    rows = []
    for activity in db.get_lti_activities_by_org(auth.organization.get('id')):
        relationship = activity_access.relationship(db, activity, auth.user)
        rows.append({**activity_access.context(db, activity),
                     'id': activity['id'], 'activity_type': activity.get('activity_type') or 'chat',
                     'status': activity['status'], 'owner_name': activity.get('owner_name') or activity.get('owner_email'),
                     'relationship': relationship,
                     'can_manage': activity['status'] == 'active' and relationship in ('owner', 'instructor')})
    return {'activities': rows}


@router.post('/{activity_id}/open')
def open_activity(activity_id: int, auth: AuthContext = Depends(get_auth_context)):
    activity = activity_access.activity_by_id(db, activity_id)
    if not activity or activity['organization_id'] != auth.organization.get('id'):
        raise HTTPException(404, 'Activity not found')
    if activity['status'] != 'active' or activity_access.relationship(db, activity, auth.user) not in ('owner', 'instructor'):
        raise HTTPException(403, 'Open this activity as an instructor from your LMS to establish access')
    claims = {'activity_creator_id': auth.user['id'], 'lti_activity_id': activity['id'],
              'lti_resource_link_id': activity['resource_link_id'], 'lti_type': 'dashboard',
              'lti_user_email': auth.user.get('user_email') or auth.user.get('email'),
              'lti_display_name': auth.user.get('user_name') or auth.user.get('name') or '',
              'lti_username': f"creator-{auth.user['id']}", 'lti_lms_user_id': f"creator-{auth.user['id']}",
              'lti_context_id': activity.get('context_id') or '',
              'lti_context_title': activity.get('context_title') or ''}
    activity_type = activity.get('activity_type') or 'chat'
    if activity_type == 'llm_access':
        from lamb.token_dealer import wiring, lti
        td = wiring.store().get_activity_by_resource_link(activity['resource_link_id'])
        if not td:
            raise HTTPException(404, 'LLM access activity not found')
        token = lti.make_token({**claims, 'type': 'manage', 'activity_id': td['id']})
        url = f'{lti.PREFIX}/manage?' + urlencode({'token': token})
    elif activity_type in ('chat', 'file_evaluation'):
        token = lamb_auth.create_token(claims, expires_delta=timedelta(hours=1))
        path = '/m/chat/dashboard' if activity_type == 'chat' else '/m/file-eval/grading'
        url = path + '?' + urlencode({'token': token, 'activity_id': activity_id,
                                     'resource_link_id': activity['resource_link_id']})
    else:
        raise HTTPException(400, 'This activity type has no management interface')
    return {'url': url}
