from unittest.mock import Mock
import pytest
from lamb_cli.commands.assistant import _fetch_capabilities, _fetch_defaults
from lamb_cli.errors import AuthenticationError, NotFoundError

@pytest.mark.parametrize('fetch', [_fetch_capabilities, _fetch_defaults])
def test_auth_failure_is_not_an_empty_configuration(fetch):
    client=Mock();client.get.side_effect=AuthenticationError('Invalid token')
    with pytest.raises(AuthenticationError): fetch(client)

@pytest.mark.parametrize('fetch', [_fetch_capabilities, _fetch_defaults])
def test_legacy_missing_endpoint_compatibility(fetch):
    client=Mock();client.get.side_effect=NotFoundError('Not supported')
    assert fetch(client)=={}
