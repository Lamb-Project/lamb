"""
LTI 1.1 grade passback to Moodle.

OAuth 1.0a signature generation + IMS LTI XML format ported **verbatim** from
LAMBA ``lti_service.py``. Only the credential source changed: LAMB uses
``LtiActivityManager.get_lti_credentials()`` instead of env vars.
"""
import hashlib
import hmac
import base64
import time as _time
import urllib.parse
import uuid
import requests
from xml.sax.saxutils import escape
from typing import Dict, Any
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")


class LTIGradePassback:
    """Send grades to Moodle via LTI 1.1 Outcome Service."""

    # ── OAuth helpers (spec-critical, do not modify) ──────────────────────

    @staticmethod
    def oauth_escape(s: str) -> str:
        return urllib.parse.quote(str(s), safe="~-._")

    @staticmethod
    def normalize_url_for_oauth(url: str) -> str:
        p = urllib.parse.urlparse(url)
        scheme = p.scheme.lower()
        netloc = p.hostname.lower() if p.hostname else ""
        port = p.port
        if port:
            if (scheme == "http" and port != 80) or (scheme == "https" and port != 443):
                netloc = f"{netloc}:{port}"
        path = p.path or "/"
        return f"{scheme}://{netloc}{path}"

    @staticmethod
    def generate_oauth_signature(method: str, url: str, params: dict, consumer_secret: str) -> str:
        encoded_params = []
        for key, value in params.items():
            ek = LTIGradePassback.oauth_escape(key)
            ev = LTIGradePassback.oauth_escape(value)
            encoded_params.append((ek, ev))
        encoded_params.sort()
        normalized_params = "&".join(f"{k}={v}" for k, v in encoded_params)

        normalized_url = LTIGradePassback.normalize_url_for_oauth(url)
        base_string = "&".join([
            method.upper(),
            LTIGradePassback.oauth_escape(normalized_url),
            LTIGradePassback.oauth_escape(normalized_params),
        ])

        signing_key = f"{LTIGradePassback.oauth_escape(consumer_secret)}&"
        hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
        return base64.b64encode(hashed.digest()).decode()

    # ── XML payload (IMS LTI 1.1 spec) ───────────────────────────────────

    @staticmethod
    def create_outcome_xml(sourcedid: str, score: float, comment: str) -> str:
        message_id = str(uuid.uuid4())
        normalized_score = max(0.0, min(1.0, float(score) / 10.0))
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<imsx_POXEnvelopeRequest xmlns="http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">
    <imsx_POXHeader>
        <imsx_POXRequestHeaderInfo>
            <imsx_version>V1.0</imsx_version>
            <imsx_messageIdentifier>{escape(message_id)}</imsx_messageIdentifier>
        </imsx_POXRequestHeaderInfo>
    </imsx_POXHeader>
    <imsx_POXBody>
        <replaceResultRequest>
            <resultRecord>
                <sourcedGUID>
                    <sourcedId>{escape(sourcedid)}</sourcedId>
                </sourcedGUID>
                <result>
                    <resultScore>
                        <language>en</language>
                        <textString>{normalized_score}</textString>
                    </resultScore>
                    <resultData>
                        <text>{escape(comment)}</text>
                    </resultData>
                </result>
            </resultRecord>
        </replaceResultRequest>
    </imsx_POXBody>
</imsx_POXEnvelopeRequest>"""

    # ── Send single grade ─────────────────────────────────────────────────

    @staticmethod
    def send_grade_to_moodle(
        lis_result_sourcedid: str,
        lis_outcome_service_url: str,
        consumer_key: str,
        consumer_secret: str,
        score: float,
        comment: str = "Grade sent automatically",
    ) -> Dict[str, Any]:
        try:
            xml_payload = LTIGradePassback.create_outcome_xml(lis_result_sourcedid, score, comment)

            body_hash = hashlib.sha1(xml_payload.encode()).digest()
            oauth_body_hash = base64.b64encode(body_hash).decode()

            oauth_params = {
                "oauth_consumer_key": consumer_key,
                "oauth_nonce": str(uuid.uuid4()).replace("-", ""),
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": str(int(_time.time())),
                "oauth_version": "1.0",
                "oauth_body_hash": oauth_body_hash,
            }

            signature = LTIGradePassback.generate_oauth_signature(
                "POST", lis_outcome_service_url, oauth_params, consumer_secret,
            )
            oauth_params["oauth_signature"] = signature

            auth_parts = [f'{k}="{LTIGradePassback.oauth_escape(v)}"' for k, v in sorted(oauth_params.items())]
            auth_header = "OAuth " + ", ".join(auth_parts)

            headers = {
                "Authorization": auth_header,
                "Content-Type": "application/xml",
                "Content-Length": str(len(xml_payload.encode())),
            }

            resp = requests.post(lis_outcome_service_url, data=xml_payload.encode(), headers=headers, timeout=30)

            success = False
            error_message = None
            if resp.status_code == 200:
                if "imsx_codemajor>success" in resp.text.lower():
                    success = True
                else:
                    error_message = "Moodle returned failure in XML body"
            else:
                error_message = f"HTTP {resp.status_code}"

            return {"success": success, "status_code": resp.status_code, "error_message": error_message}

        except requests.exceptions.RequestException as exc:
            return {"success": False, "status_code": None, "error_message": f"Connection error: {exc}"}
        except Exception as exc:
            return {"success": False, "status_code": None, "error_message": f"Unexpected error: {exc}"}

    # ── Bulk send for an activity ─────────────────────────────────────────

    @staticmethod
    def send_activity_grades(activity_id: int) -> Dict[str, Any]:
        """Send all finalised grades for *activity_id* to Moodle."""
        from lamb.database_manager import LambDatabaseManager
        from lamb.lti_activity_manager import LtiActivityManager

        db = LambDatabaseManager()
        manager = LtiActivityManager()
        consumer_key, consumer_secret = manager.get_lti_credentials()

        if not consumer_key or not consumer_secret:
            return {"success": False, "error": "LTI credentials not configured", "sent": 0, "failed": 0}

        conn = db.get_connection()
        if not conn:
            return {"success": False, "error": "No DB connection", "sent": 0, "failed": 0}

        try:
            conn.row_factory = lambda c, r: {col[0]: r[i] for i, col in enumerate(c.description)}

            pfx = db.table_prefix
            activity = conn.execute(
                f"SELECT * FROM {pfx}lti_activities WHERE id = ?", (activity_id,)
            ).fetchone()
            if not activity:
                return {"success": False, "error": "Activity not found", "sent": 0, "failed": 0}

            lis_outcome_url = activity.get("lis_outcome_service_url")
            if not lis_outcome_url:
                return {"success": False, "error": "No lis_outcome_service_url on activity", "sent": 0, "failed": 0}

            rows = conn.execute("""
                SELECT ss.id AS ss_id, ss.lis_result_sourcedid, ss.student_id,
                       g.score, g.comment
                  FROM mod_file_eval_student_submissions ss
                  JOIN mod_file_eval_submissions fs ON ss.file_submission_id = fs.id
                  JOIN mod_file_eval_grades g ON fs.id = g.file_submission_id
                 WHERE ss.activity_id = ?
                   AND ss.lis_result_sourcedid IS NOT NULL
                   AND g.score IS NOT NULL
            """, (activity_id,)).fetchall()

            if not rows:
                return {"success": False, "error": "No graded submissions with sourcedid", "sent": 0, "failed": 0}

            sent, failed, results = 0, 0, []
            now = int(_time.time())
            for row in rows:
                res = LTIGradePassback.send_grade_to_moodle(
                    lis_result_sourcedid=row["lis_result_sourcedid"],
                    lis_outcome_service_url=lis_outcome_url,
                    consumer_key=consumer_key,
                    consumer_secret=consumer_secret,
                    score=row["score"],
                    comment=row["comment"] or "Grade sent automatically",
                )
                results.append({"student_id": row["student_id"], "success": res["success"], "error": res.get("error_message")})
                if res["success"]:
                    conn.execute(
                        "UPDATE mod_file_eval_student_submissions SET sent_to_moodle = 1, sent_to_moodle_at = ? WHERE id = ?",
                        (now, row["ss_id"]),
                    )
                    sent += 1
                else:
                    failed += 1

            conn.commit()
            return {"success": sent > 0 and failed == 0, "sent": sent, "failed": failed, "results": results}

        finally:
            conn.close()
