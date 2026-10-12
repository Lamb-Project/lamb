"""LLM access: each student gets a personal key for their own coding tools (token-dealer, #533).

The activity module on top of lamb.token_dealer: setup through the shared setup app (no
assistants), launches into the token-dealer pages, dashboard figures from the usage ledger.
The token traffic never passes through LAMB; see lamb/token_dealer/__init__.py.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger
from lamb.modules.base import ActivityModule, LTIContext, SetupField
from lamb.token_dealer import lti as pages
from lamb.token_dealer import wiring
from lamb.token_dealer.proxy_client import ProxyError
from lamb.token_dealer.service import AllocationError
from lamb.token_dealer.settings import SettingsError

logger = get_logger(__name__, component="LLM_ACCESS_MODULE")


def _tokens(value):
    if value in (None, ''):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f'Token limits must be whole numbers, got {value!r}')
    return n


class LlmAccessModule(ActivityModule):
    name = "llm_access"
    display_name = "LLM access"
    description = ("Each student gets a personal key to use a course model in their own coding tools "
                   "(VS Code, Cline, Claude Code), with your timetable and token limits.")
    requires_assistants = False

    def __init__(self):
        self.db_manager = LambDatabaseManager()

    # ── availability and setup ─────────────────────────────────────────
    def enabled_for_org(self, organization_id: int) -> bool:
        try:
            s = wiring.settings_for(organization_id)
        except SettingsError:
            return False
        return s.enabled and bool(s.proxy_url) and bool(s.models)

    def get_migrations(self) -> List[str]:
        return []          # tables come from numbered migration 33

    def get_routers(self):
        return [pages.router]

    def get_setup_fields(self) -> List[SetupField]:
        return [
            SetupField(name="title", label="Activity name (shown to students)", field_type="text"),
            SetupField(name="pool_tokens", label="Activity pool: tokens shared by all students", field_type="number"),
            SetupField(name="slot_tokens", label="Per student: tokens per time slot (10 minutes unless your organization chose otherwise)", field_type="number"),
            SetupField(name="total_tokens", label="Per student: tokens in total", field_type="number"),
        ]

    def on_activity_configured(self, activity_id: int, setup_data: Dict[str, Any]) -> None:
        # The router passes the resource link; the database manager has no lookup by id.
        activity = self.db_manager.get_lti_activity_by_resource_link(setup_data['resource_link_id'])
        org_id = activity['organization_id']
        settings = wiring.settings_for(org_id)
        existing = wiring.store().get_activity_by_resource_link(activity['resource_link_id'])
        schedule = existing['schedule'] if existing else {'mode': 'always', 'timezone': settings.timezone}
        models = existing['models'] if existing else list(settings.models)
        # The allowance follows the teacher's email as the LMS sends it: accounts created through
        # LTI Creator carry a synthetic address the org admin cannot know.
        owner = ((setup_data.get('lms_email') or '').strip().lower() or setup_data.get('configured_by_email')
                 or activity['owner_email'])
        try:
            wiring.service().configure_activity(
                org_id, activity['resource_link_id'], owner,
                models, schedule, pool_tokens=_tokens(setup_data.get('pool_tokens')),
                slot_tokens=_tokens(setup_data.get('slot_tokens')), total_tokens=_tokens(setup_data.get('total_tokens')),
                owner_name=activity.get('owner_name'), context_id=activity.get('context_id'),
                context_title=activity.get('context_title'), activity_name=setup_data.get('activity_name'))
        except (SettingsError, AllocationError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ProxyError as e:
            logger.error(f'LLM gateway refused activity setup: {e}')
            raise HTTPException(status_code=503, detail='The LLM gateway is not reachable. Nothing was created; try again later.')

    def on_activity_reconfigured(self, activity, added_ids, removed_ids) -> None:
        return None        # no assistants; limits change on the management page

    def configured_redirect(self, public_base, activity, lms_user_id, lms_email) -> Optional[str]:
        td = wiring.store().get_activity_by_resource_link(activity['resource_link_id'])
        t = pages.make_token({'type': 'manage', 'activity_id': td['id'], 'lms_user_id': lms_user_id, 'email': lms_email})
        return f'{public_base}{pages.PREFIX}/manage?token={t}'

    # ── launches ───────────────────────────────────────────────────────
    def _td_activity(self, resource_link_id):
        td = wiring.store().get_activity_by_resource_link(resource_link_id)
        if not td or td['status'] != 'active':
            raise HTTPException(status_code=404, detail='This LLM access activity is not configured.')
        return td

    def on_student_launch(self, ctx: LTIContext) -> RedirectResponse:
        td = self._td_activity(ctx.resource_link_id)
        return pages.launch_redirect('', td, False, ctx.lms_user_id, ctx.lms_email, ctx.display_name)

    def on_instructor_launch(self, ctx: LTIContext) -> RedirectResponse:
        td = self._td_activity(ctx.resource_link_id)
        return pages.launch_redirect('', td, True, ctx.lms_user_id, ctx.lms_email, ctx.display_name)

    def launch_user(self, activity, username, display_name, lms_user_id, is_instructor=False,
                    lis_result_sourcedid=None) -> Optional[str]:
        td = wiring.store().get_activity_by_resource_link(activity['resource_link_id'])
        if not td:
            return None
        kind = 'manage' if is_instructor else 'student'
        t = pages.make_token({'type': kind, 'activity_id': td['id'], 'lms_user_id': lms_user_id, 'name': display_name})
        return f'{pages.PREFIX}/{kind}?token={t}'

    # ── dashboard (the shared dashboard asks every module for these) ───
    def get_dashboard_stats(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        td = wiring.store().get_activity_by_resource_link(activity['resource_link_id'])
        if not td:
            return {}
        keys = wiring.store().list_keys(activity_id=td['id'])
        totals = wiring.ledger().totals(activity_id=td['id'])
        return {'students_with_keys': len(keys), 'tokens_used': sum(v['tokens'] for v in totals.values()),
                'requests_served': sum(v['requests_ok'] for v in totals.values()),
                'requests_refused': sum(v['requests_refused'] for v in totals.values())}

    def get_dashboard_chats(self, activity, assistant_id=None, page=1, per_page=20) -> Dict[str, Any]:
        return {'chats': [], 'total': 0, 'page': page, 'per_page': per_page}

    def get_dashboard_chat_detail(self, activity, chat_id) -> Optional[Dict[str, Any]]:
        return None        # the gateway keeps no conversation content

    def get_frontend_build_path(self) -> Optional[str]:
        return None


module = LlmAccessModule()
