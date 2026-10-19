"""LTI 1.3 adapters for the unified activity integration only."""

PREFIX = 'lti13_'
CLAIM = 'https://purl.imsglobal.org/spec/lti/claim/'
AGS = 'https://purl.imsglobal.org/spec/lti-ags/'
SCORE_SCOPE = AGS + 'scope/score'
LINEITEM_SCOPE = AGS + 'scope/lineitem'


def is_scoped(value):
    return isinstance(value, str) and value.startswith(PREFIX)
