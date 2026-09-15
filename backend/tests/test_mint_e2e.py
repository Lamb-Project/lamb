"""Create a fresh workshop activity + session + token for the E2E browser test.

Prints a ready-to-visit URL for localhost:5173.
"""
import json
import time
from datetime import timedelta

from lamb import auth as lamb_auth
from lamb.database_manager import LambDatabaseManager

db = LambDatabaseManager()
org_id = 1

rl = f"p4e2e-{int(time.time())}"
activity_id = db.create_lti_activity(
    resource_link_id=rl, organization_id=org_id,
    owi_group_id="g-" + rl, owi_group_name="P4 E2E Group",
    configured_by_email="teacher@test.com", configured_by_name="Teacher",
    context_title="Test Course", activity_name="P4 E2E Workshop")
email = "p4e2e@lamb-lti.local"
activity_user_id = db.create_lti_activity_user(
    activity_id=activity_id, user_email=email,
    user_name="p4e2e", user_display_name="P4 E2E Student",
    lms_user_id="LMS-P4", owi_user_id="owi-p4e2e")
session = db.get_or_create_workshop_session(
    activity_id=activity_id, activity_user_id=activity_user_id, owi_user_id="owi-p4e2e")
session_id = session["id"]

principal = {
    "scope": "workshop_student", "type": "workshop_student",
    "session_id": session_id, "activity_id": activity_id,
    "activity_user_id": activity_user_id, "owi_user_id": "owi-p4e2e",
    "email": email, "organization_id": org_id,
}
token = lamb_auth.create_token(principal, expires_delta=timedelta(seconds=7200))

print(json.dumps({
    "activity_id": activity_id,
    "session_id": session_id,
    "token": token,
    "url": f"http://localhost:5173/m/workshop/{activity_id}?token={token}",
}, indent=2))