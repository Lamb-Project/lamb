from lamb.token_dealer.proxy.lamb_token_messages import token_message, TOKEN_UNIT
from lamb.token_dealer import units


def test_unit_matches_lamb():
    assert TOKEN_UNIT == units.TOKEN_UNIT


def test_slot_limit_in_tokens():
    text = token_message('key', 'ExceededBudget: Key over 10m budget. Spend=$0.0031, Limit=$0.00', 0.003213, 0.003)
    assert text.startswith('Token limit for this time slot reached: 3,213 of 3,000 tokens')
    assert '10-minute slot' in text and '$' not in text


def test_total_allowance_in_tokens():
    text = token_message('key', 'Budget has been exceeded! Key=x Current cost: 0.02004, Max budget: 0.02', 0.02004, 0.02)
    assert text == 'Your token allowance for this activity is used up: 20,040 of 20,000 tokens. Ask your teacher if you need more.'


def test_pool_in_tokens():
    assert token_message('team', '', 0.2, 0.2).startswith("This activity's shared token pool is used up: 200,000 of 200,000")


def test_other_refusals_untouched():
    assert token_message('user', 'x', 1, 1) is None
    assert token_message('key', 'x', None, 1) is None
