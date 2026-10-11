"""The proxy budgets in cost. token-dealer prices every model at one unit per token, so a
proxy budget of 0.004 is 4,000 tokens. Real money is computed in LAMB from the usage ledger."""

TOKEN_UNIT = 1e-6   # proxy "cost" of one token, input, output and cached alike


def tokens_to_units(tokens):
    return None if tokens is None else round(int(tokens) * TOKEN_UNIT, 9)


def units_to_tokens(units):
    return None if units is None else int(round(float(units) / TOKEN_UNIT))
