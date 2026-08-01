# Vendored-tau test suite (adopted from huggingface/tau v0.1.5, MIT).
# Pins the anyio backend so @pytest.mark.anyio tests run on asyncio only.
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
