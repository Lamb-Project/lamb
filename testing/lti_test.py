#!/usr/bin/env python3
"""
LAMB LTI Integration Test Script
=================================
Simulates Moodle LTI 1.1 launches against the LAMB backend without needing
a real Moodle instance.  Generates valid OAuth 1.0 HMAC-SHA1 signatures and
POSTs them to the three LTI endpoints:

  1. /lamb/v1/lti/launch          – Unified activity flow     (--mode unified)
  2. /lamb/v1/lti_users/lti       – Legacy student flow       (--mode student)
  3. /lamb/v1/lti_creator/launch  – Educator creator flow     (--mode creator)

Usage examples
--------------
  # Unified – student role (default)
  python testing/lti_test.py

  # Unified – instructor role
  python testing/lti_test.py --mode unified --role instructor

  # Legacy student launch
  python testing/lti_test.py --mode student --consumer-key my_assistant_key --secret my_secret

  # Creator launch
  python testing/lti_test.py --mode creator --consumer-key myorg_creator --secret myorg_secret

Required packages
-----------------
  pip install requests
  (all other dependencies are Python stdlib)

Configuration
-------------
Defaults match backend/.env.example.  Override with CLI flags or env vars:
  LAMB_BASE_URL           Backend URL (default: http://localhost:9099)
  LTI_GLOBAL_CONSUMER_KEY Unified LTI consumer key (default: lamb)
  LTI_GLOBAL_SECRET       Unified LTI secret
  LTI_SECRET              Legacy student LTI secret
"""

import argparse
import base64
import hashlib
import hmac
import os
import secrets
import sys
import time
import urllib.parse

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' is not installed. Run: pip install requests")


# ---------------------------------------------------------------------------
# OAuth 1.0 HMAC-SHA1 helpers
# ---------------------------------------------------------------------------

def _compute_oauth_signature(params: dict, http_method: str,
                              base_url: str, consumer_secret: str,
                              token_secret: str = "") -> str:
    """Compute an OAuth 1.0 HMAC-SHA1 signature identical to what LAMB expects."""
    params_copy = {k: v for k, v in params.items() if k != "oauth_signature"}
    sorted_params = sorted(params_copy.items())
    encoded_params = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

    base_string = "&".join([
        http_method.upper(),
        urllib.parse.quote(base_url, safe=""),
        urllib.parse.quote(encoded_params, safe=""),
    ])

    # The backend does NOT percent-encode the signing key components —
    # match that behaviour exactly so signatures agree for any secret value.
    signing_key = f"{consumer_secret}&{token_secret}"
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    return base64.b64encode(hashed.digest()).decode()


def build_lti_params(consumer_key: str, consumer_secret: str,
                     base_url: str, extra_params: dict) -> dict:
    """
    Return a complete set of LTI 1.1 POST params including a valid OAuth
    signature ready to be submitted as form data.
    """
    params = {
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "oauth_consumer_key": consumer_key,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": secrets.token_hex(16),
        "oauth_version": "1.0",
        **extra_params,
    }
    params["oauth_signature"] = _compute_oauth_signature(
        params, "POST", base_url, consumer_secret
    )
    return params


# ---------------------------------------------------------------------------
# Endpoint launchers
# ---------------------------------------------------------------------------

def launch_unified(base_url: str, consumer_key: str, consumer_secret: str,
                   user_id: str, role: str, resource_link_id: str,
                   context_id: str, context_title: str,
                   display_name: str, email: str, username: str) -> None:
    """POST to /lamb/v1/lti/launch (unified activity flow)."""

    endpoint = f"{base_url}/lamb/v1/lti/launch"

    if role == "instructor":
        roles_str = "Instructor"
    else:
        roles_str = "Student"

    extra = {
        "resource_link_id": resource_link_id,
        "user_id": user_id,
        "roles": roles_str,
        "lis_person_contact_email_primary": email,
        "lis_person_name_full": display_name,
        "ext_user_username": username,
        "context_id": context_id,
        "context_title": context_title,
    }

    params = build_lti_params(consumer_key, consumer_secret, endpoint, extra)
    _post_and_report(endpoint, params, follow_redirects=False)


def launch_student(base_url: str, consumer_key: str, consumer_secret: str,
                   user_id: str, username: str) -> None:
    """POST to /lamb/v1/lti_users/lti (legacy student flow)."""

    endpoint = f"{base_url}/lamb/v1/lti_users/lti"

    extra = {
        "user_id": user_id,
        "ext_user_username": username,
    }

    params = build_lti_params(consumer_key, consumer_secret, endpoint, extra)
    _post_and_report(endpoint, params, follow_redirects=False)


def launch_creator(base_url: str, consumer_key: str, consumer_secret: str,
                   user_id: str, username: str, display_name: str) -> None:
    """POST to /lamb/v1/lti_creator/launch (creator / educator flow)."""

    endpoint = f"{base_url}/lamb/v1/lti_creator/launch"

    extra = {
        "user_id": user_id,
        "ext_user_username": username,
        "lis_person_name_full": display_name,
    }

    params = build_lti_params(consumer_key, consumer_secret, endpoint, extra)
    _post_and_report(endpoint, params, follow_redirects=False)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _post_and_report(endpoint: str, params: dict, follow_redirects: bool) -> None:
    """POST *params* as form data to *endpoint* and print a human-readable report."""
    print("\n" + "=" * 72)
    print(f"POST  {endpoint}")
    print("-" * 72)
    print("Form params sent:")
    for k, v in sorted(params.items()):
        display_v = v if k != "oauth_signature" else f"{v[:20]}…"
        print(f"  {k:<40} {display_v}")
    print("-" * 72)

    try:
        resp = requests.post(
            endpoint,
            data=params,
            allow_redirects=follow_redirects,
            timeout=15,
        )
    except requests.exceptions.ConnectionError as exc:
        print(f"[ERROR] Could not connect to backend: {exc}")
        print("  Make sure LAMB is running (e.g. `uvicorn main:app --port 9099`)")
        return

    print(f"HTTP status : {resp.status_code}")

    # Show redirect destination without following it
    location = resp.headers.get("location") or resp.headers.get("Location")
    if location:
        print(f"Redirect to : {location}")
        _annotate_redirect(location)
    else:
        # For non-redirect responses, show a snippet of the body
        body = resp.text
        if len(body) > 800:
            body = body[:800] + "\n…(truncated)"
        print(f"Response body:\n{body}")


def _annotate_redirect(location: str) -> None:
    """Print a friendly interpretation of the redirect URL."""
    if "/api/v1/auths/complete" in location:
        print("  ✓ Student auto-login redirect into Open WebUI chat")
    elif "/lamb/v1/lti/dashboard" in location:
        print("  ✓ Instructor redirected to LTI activity dashboard")
    elif "/lamb/v1/lti/setup" in location:
        print("  ✓ Instructor redirected to activity setup page")
    elif "/lamb/v1/lti/consent" in location:
        print("  ✓ Student sent to consent page")
    elif "/assistants" in location:
        print("  ✓ Creator/educator redirected to LAMB Creator Interface")
    else:
        print("  (redirect destination not recognised — check URL above)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate Moodle LTI 1.1 launches against a local LAMB backend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        choices=["unified", "student", "creator"],
        default="unified",
        help="Which LTI flow to test (default: unified)",
    )
    parser.add_argument(
        "--backend",
        default=os.getenv("LAMB_BASE_URL", "http://localhost:9099"),
        help="LAMB backend base URL (default: http://localhost:9099 or $LAMB_BASE_URL)",
    )

    # Credentials
    parser.add_argument(
        "--consumer-key",
        default=None,
        help="OAuth consumer key. Defaults: unified→$LTI_GLOBAL_CONSUMER_KEY or 'lamb'; "
             "student→$LTI_SECRET or 'lamb-lti-secret-key-2024' (key=secret for legacy); "
             "creator→must be provided",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="OAuth consumer secret. Defaults: unified→$LTI_GLOBAL_SECRET; "
             "student→$LTI_SECRET; creator→must be provided",
    )

    # User identity
    parser.add_argument("--user-id", default="test_moodle_user_42",
                        help="Stable LMS user identifier (default: test_moodle_user_42)")
    parser.add_argument("--username", default="testuser",
                        help="ext_user_username value (default: testuser)")
    parser.add_argument("--display-name", default="Test User",
                        help="lis_person_name_full value (default: 'Test User')")
    parser.add_argument("--email", default="testuser@example.com",
                        help="lis_person_contact_email_primary (unified only)")

    # Unified-specific
    parser.add_argument(
        "--role",
        choices=["student", "instructor"],
        default="student",
        help="LTI role for unified flow (default: student)",
    )
    parser.add_argument("--resource-link-id", default="moodle_activity_99",
                        help="Moodle resource_link_id (unified only, default: moodle_activity_99)")
    parser.add_argument("--context-id", default="course_101",
                        help="Moodle course context_id (unified only, default: course_101)")
    parser.add_argument("--context-title", default="Test Course",
                        help="Moodle course title (unified only, default: 'Test Course')")

    args = parser.parse_args()

    # ── Resolve credentials per mode ──
    if args.mode == "unified":
        key = (args.consumer_key
               or os.getenv("LTI_GLOBAL_CONSUMER_KEY", "lamb"))
        secret = (args.secret
                  or os.getenv("LTI_GLOBAL_SECRET")
                  or os.getenv("LTI_SECRET", "lamb-lti-secret-key-2024"))

    elif args.mode == "student":
        # For the legacy route, the "consumer key" is the published assistant's
        # oauth_consumer_name.  The secret is the global LTI_SECRET.
        lti_secret = os.getenv("LTI_SECRET", "lamb-lti-secret-key-2024")
        key = args.consumer_key or lti_secret   # key isn't validated on student route
        secret = args.secret or lti_secret

    else:  # creator
        key = args.consumer_key
        secret = args.secret
        if not key or not secret:
            parser.error(
                "--consumer-key and --secret are required for --mode creator.\n"
                "Use the org's oauth_consumer_key and oauth_consumer_secret from "
                "the LAMB admin LTI Creator settings."
            )

    print(f"\nLAMB LTI Test  •  mode={args.mode}  •  backend={args.backend}")
    print(f"consumer_key={key}  secret={'*' * min(len(secret), 8) + '...'}")

    if args.mode == "unified":
        launch_unified(
            base_url=args.backend,
            consumer_key=key,
            consumer_secret=secret,
            user_id=args.user_id,
            role=args.role,
            resource_link_id=args.resource_link_id,
            context_id=args.context_id,
            context_title=args.context_title,
            display_name=args.display_name,
            email=args.email,
            username=args.username,
        )

    elif args.mode == "student":
        launch_student(
            base_url=args.backend,
            consumer_key=key,
            consumer_secret=secret,
            user_id=args.user_id,
            username=args.username,
        )

    else:  # creator
        launch_creator(
            base_url=args.backend,
            consumer_key=key,
            consumer_secret=secret,
            user_id=args.user_id,
            username=args.username,
            display_name=args.display_name,
        )


if __name__ == "__main__":
    main()