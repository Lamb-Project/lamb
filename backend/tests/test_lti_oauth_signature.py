"""LTI 1.1 OAuth signatures must match RFC 5849 for any consumer secret (#318).

Expected values were produced by oauthlib 3.3.1 (rfc5849.signature), an independent
implementation, so these tests do not restate LAMB's own algorithm.
"""
import pytest

from lamb.lti_activity_manager import LtiActivityManager
from lamb.lti_creator_router import generate_oauth_signature
from lamb.lti_oauth import signing_key
from lamb.lti_users_router import generate_signature

URL = 'https://lamb.example.org/lamb/v1/lti_users/lti'
PARAMS = {
    'oauth_consumer_key': 'lamb', 'oauth_nonce': 'abc123', 'oauth_timestamp': '1790000000',
    'oauth_signature_method': 'HMAC-SHA1', 'oauth_version': '1.0', 'user_id': '42', 'roles': 'Learner',
    'resource_link_id': '7', 'launch_presentation_return_url': 'https://moodle.example.org/mod/lti/return.php?course=2&id=5',
    'lis_person_name_full': 'Núria Pérez',
}
VECTORS = [
    ('s3cret', 'Y+f1aZtGkI0U/cCGM9aMYow5XdE='),
    ('h%>%U4=v8HiV]$j', 'PWr6UvzlCxuS9SwyTtYs9Lf77lQ='),
    ('a&b+c d~_.-', 'uImSKCT4TERuq3b9AxzaV7m56OU='),
]


@pytest.mark.parametrize('secret,expected', VECTORS)
def test_creator_launch_signature_matches_reference(secret, expected):
    assert generate_oauth_signature(PARAMS, 'POST', URL, secret) == expected


@pytest.mark.parametrize('secret,expected', VECTORS)
def test_student_launch_signature_matches_reference(secret, expected):
    assert generate_signature(PARAMS, 'POST', URL, secret)[0] == expected


@pytest.mark.parametrize('secret,expected', VECTORS)
def test_activity_launch_signature_matches_reference(secret, expected):
    assert LtiActivityManager._compute_oauth_signature(PARAMS, 'POST', URL, secret) == expected


def test_signing_key_percent_encodes_both_secrets():
    assert signing_key('s3cret') == 's3cret&'
    assert signing_key('h%>%U4=v8HiV]$j') == 'h%25%3E%25U4%3Dv8HiV%5D%24j&'
    assert signing_key('a b', 'x/y') == 'a%20b&x%2Fy'
    assert signing_key('~_.-') == '~_.-&'


def test_existing_oauth_signature_field_is_ignored():
    signed = dict(PARAMS, oauth_signature='anything')
    assert generate_oauth_signature(signed, 'POST', URL, 's3cret') == VECTORS[0][1]
