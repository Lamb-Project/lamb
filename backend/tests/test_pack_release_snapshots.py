"""A conversation with a pending approval stays pinned to the instruction pack it started with,
so every pack a LAMB release shipped as its live pack must remain installed as a snapshot."""
import pytest

from lamb.aac.pack_loader import load_pack


# 1.11.17 was the live pack of the 0.7 release and had no snapshot of its own: conversations
# pinned to it answered "pack 1.11.17 is not installed" after an upgrade.
@pytest.mark.parametrize('version', ['1.11.16', '1.11.17', '1.11.18'])
def test_packs_of_released_versions_stay_loadable(version):
    assert load_pack(version=version).manifest['version'] == version
