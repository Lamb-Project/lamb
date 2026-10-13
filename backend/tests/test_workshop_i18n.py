"""Workshop localization — locale resolution and consent copy parity.

The consent page is server-rendered, so its copy lives in Python rather than in
the SPA's locale bundles. Two things must hold:

* the locale chain (``?lang=`` → activity → ``Accept-Language`` → ``en``)
  resolves the way decision C6 describes, including ``q=0`` refusals;
* all four languages carry the same keys — a missing key would render an empty
  sentence in a page whose whole purpose is disclosure.
"""

import pytest

from lamb.modules.workshop import i18n


class _Request:
    """Minimal stand-in for a Starlette Request (only headers are used)."""

    def __init__(self, accept_language=None):
        self.headers = {}
        if accept_language is not None:
            self.headers["accept-language"] = accept_language


class TestNormalizeLocale:
    @pytest.mark.parametrize("value,expected", [
        ("en", "en"),
        ("ES", "es"),
        ("es-ES", "es"),
        ("ca_ES", "ca"),
        ("eu-FR", "eu"),
        ("pt-BR", None),
        ("", None),
        (None, None),
    ])
    def test_normalizes(self, value, expected):
        assert i18n.normalize_locale(value) == expected


class TestParseAcceptLanguage:
    def test_orders_by_quality(self):
        assert i18n.parse_accept_language("en;q=0.5,es;q=0.9") == ["es", "en"]

    def test_ignores_q_zero(self):
        """``q=0`` is an explicit refusal, not a preference."""
        assert i18n.parse_accept_language("es;q=0,en;q=0.8") == ["en"]
        assert i18n.parse_accept_language("es;q=0") == []

    def test_skips_unsupported_languages(self):
        assert i18n.parse_accept_language("pt-BR,de;q=0.9,ca;q=0.2") == ["ca"]

    def test_empty_header(self):
        assert i18n.parse_accept_language(None) == []
        assert i18n.parse_accept_language("") == []

    def test_stable_for_equal_quality(self):
        assert i18n.parse_accept_language("ca,es") == ["ca", "es"]


class TestResolveLocale:
    def test_url_lang_wins(self):
        assert i18n.resolve_locale(
            _Request("en-US,en;q=0.9"), {"locale": None}, url_lang="eu") == "eu"

    def test_activity_locale_is_second(self):
        assert i18n.resolve_locale(
            _Request("en"), {"locale": "ca"}, url_lang=None) == "ca"

    def test_accept_language_is_third(self):
        assert i18n.resolve_locale(
            _Request("es-ES,es;q=0.9"), {}, url_lang=None) == "es"

    def test_falls_back_to_english(self):
        assert i18n.resolve_locale(_Request("pt-BR"), {}, url_lang=None) == "en"
        assert i18n.resolve_locale(None, None, url_lang=None) == "en"

    def test_unsupported_url_lang_is_ignored(self):
        assert i18n.resolve_locale(_Request("ca"), {}, url_lang="pt") == "ca"


class TestConsentStrings:
    def test_every_language_has_the_same_keys(self):
        reference = set(i18n.CONSENT_STRINGS["en"])
        for locale in i18n.SUPPORTED_LOCALES:
            assert set(i18n.CONSENT_STRINGS[locale]) == reference, locale

    def test_every_language_discloses_the_three_purposes(self):
        """Build / test-chat / model evaluation must be stated in all four."""
        for locale in i18n.SUPPORTED_LOCALES:
            strings = i18n.CONSENT_STRINGS[locale]
            for key in ("purposeBuild", "purposeTest", "purposeEvaluate"):
                assert strings[key].strip(), f"{locale}.{key}"

    def test_model_class_sentences_exist(self):
        for locale in i18n.SUPPORTED_LOCALES:
            strings = i18n.CONSENT_STRINGS[locale]
            for key in ("modelLocal", "modelExternal", "modelUnknown"):
                assert strings[key].strip(), f"{locale}.{key}"
            # The external sentence must name the model it is talking about.
            assert "{model}" in strings["modelExternal"]

    def test_retention_disclosure_exists(self):
        for locale in i18n.SUPPORTED_LOCALES:
            strings = i18n.CONSENT_STRINGS[locale]
            assert strings["retentionBody"].strip()
            assert "{days}" in strings["retentionDays"]

    def test_fallback_for_unknown_locale(self):
        assert i18n.consent_strings("pt") == i18n.CONSENT_STRINGS["en"]
        assert i18n.consent_strings(None) == i18n.CONSENT_STRINGS["en"]

    def test_lang_marker_matches_the_locale(self):
        for locale in i18n.SUPPORTED_LOCALES:
            assert i18n.CONSENT_STRINGS[locale]["lang"] == locale