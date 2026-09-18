"""Verify a per-creator Moodle identity through services, never a CLI subprocess."""
from datetime import datetime, timezone

from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.client.qrlogin import parse_moodlemobile_uri, exchange_qr_login
from moodle_cli.services.site import SiteService

from .policy import canonical_base_url


class MoodleConnectionError(ValueError):
    pass


def establish_connection(policy, cipher, *, organization_id, owner_id, token=None, passport=None):
    """Returns an encrypted persistence record only after site and identity verification.

    Caller performs the database update atomically. Blocking service I/O must run
    off the async event loop. No credential is ever included in an error message.
    """
    if bool(token) == bool(passport):
        raise MoodleConnectionError('Provide either a mobile-service token or a fresh QR passport')
    policy.require_connection_url(policy.base_url)
    qr_user = None
    if passport:
        try:
            site, key, qr_user = parse_moodlemobile_uri(passport)
            policy.require_connection_url(site)
            token = exchange_qr_login(policy.base_url, key, qr_user).get('token')
            if not isinstance(token, str) or not token:
                raise ValueError()
        except PermissionError:
            raise
        except Exception:
            raise MoodleConnectionError('QR connection failed. Use a fresh passport from the allowed Moodle site') from None
    try:
        with MoodleHTTPClient(policy.base_url, token, readonly=True) as client:
            info = SiteService(client).get_site_info()
        if canonical_base_url(info.siteurl) != policy.base_url or info.userid <= 0:
            raise ValueError()
        if qr_user is not None and info.userid != int(qr_user):
            raise ValueError()
        ciphertext = cipher.encrypt(token, organization_id=organization_id, owner_id=owner_id, base_url=policy.base_url)
    except Exception:
        raise MoodleConnectionError('Moodle identity verification failed. Reconnect with a valid token from the allowed site') from None
    return {'schema_version': 1, 'base_url': policy.base_url, 'moodle_user_id': info.userid,
            'username': info.username, 'token_encrypted': ciphertext,
            'connected_at': datetime.now(timezone.utc).isoformat()}


def public_connection(record):
    return {key: record[key] for key in ('base_url', 'moodle_user_id', 'username', 'connected_at') if key in record}
