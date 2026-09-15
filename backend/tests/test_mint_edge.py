"""Mint a session and emit a browser-ready check URL (full, unbroken)."""
import json
import sys
import time
from datetime import timedelta

from lamb import auth as lamb_auth
from lamb.database_manager import LambDatabaseManager

db = LambDatabaseManager()
org_id = 1
rl = f"edge-{int(time.time())}"
activity_id = db.create_lti_activity(
    resource_link_id=rl, organization_id=org_id,
    owi_group_id="g-" + rl, owi_group_name="Edge E2E Group",
    configured_by_email="teacher@test.com", configured_by_name="Teacher",
    context_title="Test Course", activity_name="Edge E2E Workshop")
email = "edge-e2e@lamb-lti.local"
activity_user_id = db.create_lti_activity_user(
    activity_id=activity_id, user_email=email,
    user_name="edge", user_display_name="Edge E2E Student",
    lms_user_id="LMS-EDGE", owi_user_id="owi-edge")
session = db.get_or_create_workshop_session(
    activity_id=activity_id, activity_user_id=activity_user_id, owi_user_id="owi-edge")
session_id = session["id"]
principal = {
    "scope": "workshop_student", "type": "workshop_student",
    "session_id": session_id, "activity_id": activity_id,
    "activity_user_id": activity_user_id, "owi_user_id": "owi-edge",
    "email": email, "organization_id": org_id,
}
token = lamb_auth.create_token(principal, expires_delta=timedelta(seconds=7200))
print(f"SESSION={session_id}")
print(f"URL=http://localhost:5173/m/workshop/{activity_id}?token={token}")