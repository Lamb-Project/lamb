import pytest
from cryptography.fernet import Fernet
from lamb.moodle.policy import MoodlePolicy, MoodleConfigurationError, canonical_base_url
from lamb.moodle.secrets import TokenCipher


def test_policy_matrix():
    assert not MoodlePolicy.from_config({}).enabled
    for mode, groups, grade in [('readonly', [], False), ('full', ['forum'], False), ('full', ['forum'], True)]:
        policy = MoodlePolicy.from_config({'moodle': {'enabled': True, 'base_url': 'https://moodle.test/', 'mode': mode, 'write_groups': groups, 'allow_grade_write': grade}})
        policy.require_connection_url('https://MOODLE.test:443')
        for group, allowed in [('forum', mode == 'full'), ('grade', grade), ('roles', False)]:
            if allowed: policy.require_write(group)
            else:
                with pytest.raises(PermissionError): policy.require_write(group)
        with pytest.raises(PermissionError): policy.require_connection_url('https://other.test')
    with pytest.raises(PermissionError): MoodlePolicy().require_connection_url('https://moodle.test')


@pytest.mark.parametrize('url', ['https://x.test?token=secret', 'https://u:p@x.test', 'https://x.test/#part', 'file:///etc/passwd', 'https://x.test/%2e%2e/private', 'https://x.test/../private', 'https://x.test//other', ' https://x.test', 'https://x.test:bad', 'https://x.test\\@other'])
def test_ambiguous_connection_urls_rejected(url):
    with pytest.raises(MoodleConfigurationError): canonical_base_url(url)


def test_cipher_owner_binding_and_key_failure(monkeypatch):
    monkeypatch.delenv('LAMB_MOODLE_ENCRYPTION_KEY', raising=False)
    with pytest.raises(MoodleConfigurationError): TokenCipher()
    cipher = TokenCipher(Fernet.generate_key())
    scope = dict(organization_id=1, owner_id=7, base_url='https://moodle.test')
    ciphertext = cipher.encrypt('fixture-token', **scope)
    assert 'fixture-token' not in ciphertext
    assert cipher.decrypt(ciphertext, **scope) == 'fixture-token'
    for change in [dict(owner_id=8), dict(organization_id=2), dict(base_url='https://other.test')]:
        with pytest.raises(MoodleConfigurationError): cipher.decrypt(ciphertext, **{**scope, **change})
    with pytest.raises(MoodleConfigurationError): TokenCipher(Fernet.generate_key()).decrypt(ciphertext, **scope)
    with pytest.raises(MoodleConfigurationError): cipher.decrypt('tampered', **scope)


@pytest.mark.parametrize('settings', [{'enabled':'true'}, {'enabled':True}, {'mode':'anything'}, {'write_groups':['roles']}, {'allow_grade_write':'false'}])
def test_invalid_admin_configuration_fails_closed(settings):
    with pytest.raises(MoodleConfigurationError): MoodlePolicy.from_config({'moodle': settings})
