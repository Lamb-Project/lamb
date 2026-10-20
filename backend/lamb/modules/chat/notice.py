"""One-time notice for chat activities whose teachers can read the transcripts.

lamb-0.8: when an activity has "Allow instructors to review chat transcripts" on, a student's
first launch shows what the teacher can see before the chat opens. Entering the chat is the
acceptance (Marc, 2026-10-16); it is recorded in lti_activity_users.consent_given_at and later
launches go straight in. The notice page hands a short-lived signed token to the enter route,
which never trusts form fields for identity.
"""
import os
from datetime import timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lamb import auth as lamb_auth
from lamb.logging_config import get_logger
from lamb.modules.base import module_public_base

logger = get_logger(__name__, component="CHAT_MODULE")
router = APIRouter()
templates = Jinja2Templates(directory=[os.path.abspath("lamb/templates")])

SCOPE = 'chat'
PREFIX = '/lamb/v1/modules/chat'
TOKEN_TTL = 1800


def needs_notice(db_manager, activity, student_email) -> bool:
    """True when the teacher can read transcripts and this student has not entered yet."""
    if not activity.get('chat_visibility_enabled'):
        return False
    row = db_manager.get_activity_user(activity['id'], student_email)
    return not (row and row.get('consent_given_at'))


def make_token(activity, ctx) -> str:
    return lamb_auth.create_token({
        'scope': SCOPE, 'type': 'transcript_notice',
        'activity_id': activity['id'], 'resource_link_id': activity['resource_link_id'],
        'username': ctx.username, 'display_name': ctx.display_name, 'lms_user_id': ctx.lms_user_id,
    }, expires_delta=timedelta(seconds=TOKEN_TTL))


def read_token(token):
    data = lamb_auth.decode_token(token) if token else None
    if not data or data.get('scope') != SCOPE or data.get('type') != 'transcript_notice':
        return None
    return data


def notice_page(activity, ctx) -> HTMLResponse:
    # Rendered from module dispatch, without a request at hand.
    return HTMLResponse(templates.get_template('chat_transcript_notice.html').render(
        title=activity.get('activity_name') or ctx.context_title or 'this activity',
        action=f'{module_public_base()}{PREFIX}/enter',
        token=make_token(activity, ctx),
    ))


@router.post('/enter')
async def enter(request: Request, token: str = Form('')):
    data = read_token(token)
    if not data:
        return HTMLResponse('<h2>Session expired.</h2><p>Open the activity from your course again.</p>',
                            status_code=403)
    from lamb.modules.chat import ChatModule
    module = ChatModule()
    activity = module.db_manager.get_lti_activity_by_resource_link(data['resource_link_id'])
    if not activity or activity['id'] != data['activity_id']:
        return HTMLResponse('<h2>Activity not found.</h2>', status_code=404)
    redirect_url = module.launch_user(
        activity=activity, username=data['username'], display_name=data['display_name'],
        lms_user_id=data.get('lms_user_id'),
    )
    if not redirect_url:
        return HTMLResponse('<h2>Error</h2><p>Failed to open the chat. Please try again.</p>', status_code=500)
    email = module.service.generate_student_email(data['username'], activity['resource_link_id'])
    if not module.db_manager.record_student_consent(activity['id'], email):
        logger.error(f"Could not record transcript notice acceptance for {email} in activity {activity['id']}")
    return RedirectResponse(url=redirect_url, status_code=303)
