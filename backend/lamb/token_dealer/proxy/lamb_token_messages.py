"""LiteLLM proxy plugin: word budget refusals in tokens, not dollars.

LAMB prices every model at one millionth of a unit per token, so the proxy's own
refusal ("ExceededBudget: Key over 10m budget. Spend=$0.0031, Limit=$0.00") reads
as money. This plugin rewrites the three refusals LAMB causes (slot limit, total
allowance, activity pool) into tokens. Anything else passes through unchanged.

Load it from the proxy config, with this file next to config.yaml:
    litellm_settings:
      callbacks: lamb_token_messages.proxy_handler_instance
The formatting below has no LiteLLM dependency so LAMB's tests can check it.
"""
import re

TOKEN_UNIT = 1e-6   # must match lamb.token_dealer.units.TOKEN_UNIT
_UNITS = {'s': 'second', 'm': 'minute', 'h': 'hour', 'd': 'day'}


def _tokens(units):
    return int(round(float(units) / TOKEN_UNIT))


def _window(duration):
    m = re.fullmatch(r'(\d+)\s*([smhd])', duration or '')
    return f"{m.group(1)}-{_UNITS[m.group(2)]}" if m else duration


def token_message(entity_type, message, current_cost, max_budget):
    """The refusal in tokens, or None to keep the proxy's own message."""
    try:
        used, limit = _tokens(current_cost), _tokens(max_budget)
    except (TypeError, ValueError):
        return None
    if entity_type == 'key':
        slot = re.search(r'Key over (\S+) budget', message or '')
        if slot:
            return (f"Token limit for this time slot reached: {used:,} of {limit:,} tokens used in the "
                    f"current {_window(slot.group(1))} slot. Your key works again when the next slot starts.")
        return (f"Your token allowance for this activity is used up: {used:,} of {limit:,} tokens. "
                f"Ask your teacher if you need more.")
    if entity_type == 'team':
        return (f"This activity's shared token pool is used up: {used:,} of {limit:,} tokens. "
                f"Ask your teacher.")
    return None


try:   # only inside the proxy
    import litellm
    from fastapi import HTTPException
    from litellm.integrations.custom_logger import CustomLogger

    class LambTokenMessages(CustomLogger):
        async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict,
                                               traceback_str=None):
            e = original_exception
            if not isinstance(e, litellm.BudgetExceededError):
                return None
            text = token_message(getattr(e, 'entity_type', None), getattr(e, 'message', ''),
                                 getattr(e, 'current_cost', None), getattr(e, 'max_budget', None))
            return HTTPException(status_code=429, detail=text) if text else None

    proxy_handler_instance = LambTokenMessages()
except ImportError:
    pass
