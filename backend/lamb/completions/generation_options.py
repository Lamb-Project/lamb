"""Options for LAMB's small, direct Chat Completions generators."""

import re
from urllib.parse import urlparse


def generation_options(model, *, base_url=None, max_tokens=None, temperature=None):
    """Keep legacy/local sampling while avoiding reasoning-model rejections.

    These callers leave reasoning effort at the model default, so omit sampling
    for GPT-5/6 and o-series models, including dated and fine-tuned variants.
    Custom endpoints keep their legacy token field unless the model is one of
    those reasoning families. No provider or model fallback is introduced.
    """
    name = model.split(":", 2)[1] if model.startswith("ft:") else model
    reasoning = bool(re.match(r"^(?:gpt-[56](?:[.\-]|$)|o[134](?:-|$))", name))
    official = not base_url or urlparse(str(base_url)).hostname == "api.openai.com"
    options = {}
    if max_tokens is not None:
        field = "max_completion_tokens" if official or reasoning else "max_tokens"
        options[field] = max_tokens
    if temperature is not None and not reasoning:
        options["temperature"] = temperature
    return options
