"""Tests for the per-org HMAC permalink signing used by public citation links."""

from creator_interface.permalink_signing import sign, verify


class TestSignVerify:
    def test_roundtrip(self):
        sig = sign("3", "3/lib-1/item-1/view")
        assert verify("3", "3/lib-1/item-1/view", sig) is True

    def test_rejects_tampered_resource(self):
        sig = sign("3", "3/lib-1/item-1/view")
        assert verify("3", "3/lib-1/item-2/view", sig) is False

    def test_rejects_empty_signature(self):
        assert verify("3", "3/lib-1/item-1/view", "") is False
        assert verify("3", "3/lib-1/item-1/view", None) is False

    def test_rejects_garbage_signature(self):
        assert verify("3", "3/lib-1/item-1/view", "deadbeef") is False

    def test_per_org_isolation(self):
        # A signature minted for org 3 must not validate for org 7, even for an
        # identical resource path — the signing key is org-derived.
        sig_org3 = sign("3", "3/lib-1/item-1/view")
        assert verify("7", "3/lib-1/item-1/view", sig_org3) is False
        # And the two orgs produce different signatures for the same resource.
        assert sign("3", "x/y/z/view") != sign("7", "x/y/z/view")

    def test_org_id_int_or_str_consistent(self):
        # Callers may pass org_id as int or str; signing normalizes to str.
        assert sign(3, "3/lib/item/view") == sign("3", "3/lib/item/view")

    def test_original_download_resource_distinct_from_view(self):
        view = sign("3", "3/lib/item/view")
        original = sign("3", "3/lib/item/original/cv.pdf")
        assert view != original
        assert verify("3", "3/lib/item/original/cv.pdf", original) is True
        assert verify("3", "3/lib/item/original/cv.pdf", view) is False
