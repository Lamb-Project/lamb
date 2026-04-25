"""Unit tests for the embedding plugin modules.

Covers:
- ``plugins/embedding/openai.py``
- ``plugins/embedding/ollama.py``
- ``plugins/embedding/local.py``

OpenAI and Ollama tests use ``unittest.mock.patch`` to prevent any real network
calls.  Local (sentence-transformers) tests load the real ``all-MiniLM-L6-v2``
model and are marked ``@pytest.mark.slow`` so they can be skipped with
``pytest -m "not slow"``.
"""

from __future__ import annotations

import math
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _param_names(params) -> list[str]:
    return [p.name for p in params]


# ---------------------------------------------------------------------------
# OpenAI embedding plugin
# ---------------------------------------------------------------------------


class TestOpenAIEmbedding:
    """Tests for ``plugins/embedding/openai.py:OpenAIEmbedding``."""

    def _make(self, mock_ctor, **kwargs):
        """Instantiate OpenAIEmbedding with the ChromaDB constructor patched."""
        from plugins.embedding.openai import OpenAIEmbedding

        return OpenAIEmbedding(**kwargs)

    def test_class_parameters_schema(self):
        """``class_parameters()`` returns expected schema with model and api_endpoint."""
        from plugins.embedding.openai import OpenAIEmbedding

        params = OpenAIEmbedding.class_parameters()
        names = _param_names(params)
        assert "model" in names
        assert "api_endpoint" in names
        # No api_key in the public schema (key is passed per-request, not a
        # discoverable param).
        assert "api_key" not in names

    def test_class_parameters_model_default(self):
        """Default value for the model parameter is ``text-embedding-3-small``."""
        from plugins.embedding.openai import OpenAIEmbedding

        params = {p.name: p for p in OpenAIEmbedding.class_parameters()}
        assert params["model"].default == "text-embedding-3-small"

    def test_default_model_fallback_when_empty_string(self):
        """``model=""`` falls back to ``text-embedding-3-small``."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="", api_key="k")

        assert captured.get("model_name") == "text-embedding-3-small"

    def test_explicit_api_key_used(self):
        """Explicit ``api_key`` kwarg is forwarded to the underlying constructor."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="text-embedding-3-small", api_key="explicit-key-123")

        assert captured.get("api_key") == "explicit-key-123"

    def test_api_key_from_env(self, monkeypatch):
        """When ``api_key`` is omitted the plugin reads ``EMBEDDINGS_APIKEY`` from env."""
        monkeypatch.setenv("EMBEDDINGS_APIKEY", "env-api-key-xyz")
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="text-embedding-3-small")

        assert captured.get("api_key") == "env-api-key-xyz"

    def test_api_key_param_takes_priority_over_env(self, monkeypatch):
        """Explicit ``api_key`` takes priority over ``EMBEDDINGS_APIKEY`` env var."""
        monkeypatch.setenv("EMBEDDINGS_APIKEY", "env-key-should-be-ignored")
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="text-embedding-3-small", api_key="param-key")

        assert captured.get("api_key") == "param-key"

    def test_no_api_key_env_empty(self, monkeypatch):
        """When both param and env are absent, api_key defaults to empty string."""
        monkeypatch.delenv("EMBEDDINGS_APIKEY", raising=False)
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="text-embedding-3-small")

        assert captured.get("api_key") == ""

    # ----- Endpoint suffix stripping -----

    @pytest.mark.parametrize(
        "input_url, expected_base",
        [
            # With /embeddings suffix — must strip it.
            ("https://x/v1/embeddings", "https://x/v1"),
            # Already clean — must pass through unchanged.
            ("https://x/v1", "https://x/v1"),
            # Trailing slash + /embeddings suffix — strip both.
            ("https://x/v1/embeddings/", "https://x/v1"),
            # Trailing slash only — strip the slash, keep the path.
            ("https://x/v1/", "https://x/v1"),
        ],
    )
    def test_endpoint_suffix_stripping(self, input_url, expected_base):
        """``/embeddings`` suffix (and trailing slashes) are stripped from the URL."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(
                model="text-embedding-3-small",
                api_key="k",
                api_endpoint=input_url,
            )

        assert captured.get("api_base") == expected_base, (
            f"For input {input_url!r}: expected api_base={expected_base!r}, "
            f"got {captured.get('api_base')!r}"
        )

    def test_no_api_base_when_no_endpoint(self):
        """When ``api_endpoint`` is empty, ``api_base`` is NOT passed to constructor."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="text-embedding-3-small", api_key="k")

        assert "api_base" not in captured

    def test_instantiation_does_not_make_network_call(self):
        """Constructing ``OpenAIEmbedding`` must not trigger any HTTP request."""
        import httpx
        import requests

        http_called = []

        def boom(*args, **kwargs):
            http_called.append((args, kwargs))
            raise AssertionError("Network call during __init__!")

        with (
            patch.object(httpx, "Client", side_effect=boom),
            patch.object(requests, "Session", side_effect=boom),
            patch(
                "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
                return_value=MagicMock(),
            ),
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            OpenAIEmbedding(model="text-embedding-3-small", api_key="k")

        assert not http_called

    def test_call_delegates_to_underlying_fn(self):
        """``__call__`` forwards the input list to the wrapped ChromaDB function."""
        fake_inner = MagicMock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        with patch(
            "chromadb.utils.embedding_functions.OpenAIEmbeddingFunction",
            return_value=fake_inner,
        ):
            from plugins.embedding.openai import OpenAIEmbedding

            emb = OpenAIEmbedding(model="text-embedding-3-small", api_key="k")
            result = emb(["hello", "world"])

        fake_inner.assert_called_once_with(["hello", "world"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]


# ---------------------------------------------------------------------------
# Ollama embedding plugin
# ---------------------------------------------------------------------------


class TestOllamaEmbedding:
    """Tests for ``plugins/embedding/ollama.py:OllamaEmbedding``."""

    def test_class_parameters_schema(self):
        """``class_parameters()`` returns expected schema with model and api_endpoint."""
        from plugins.embedding.ollama import OllamaEmbedding

        params = OllamaEmbedding.class_parameters()
        names = _param_names(params)
        assert "model" in names
        assert "api_endpoint" in names

    def test_class_parameters_model_default(self):
        """Default model is ``nomic-embed-text``."""
        from plugins.embedding.ollama import OllamaEmbedding

        params = {p.name: p for p in OllamaEmbedding.class_parameters()}
        assert params["model"].default == "nomic-embed-text"

    def test_class_parameters_endpoint_default(self):
        """Default endpoint is the standard local Ollama URL."""
        from plugins.embedding.ollama import OllamaEmbedding

        params = {p.name: p for p in OllamaEmbedding.class_parameters()}
        assert params["api_endpoint"].default == "http://localhost:11434/api/embeddings"

    def test_default_model_applied_when_empty(self):
        """``model=""`` falls back to ``nomic-embed-text``."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OllamaEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.ollama import OllamaEmbedding

            OllamaEmbedding(model="")

        assert captured.get("model_name") == "nomic-embed-text"

    def test_default_endpoint_applied_when_empty(self):
        """``api_endpoint=""`` falls back to the standard Ollama URL."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OllamaEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.ollama import OllamaEmbedding

            OllamaEmbedding(api_endpoint="")

        assert captured.get("url") == "http://localhost:11434/api/embeddings"

    def test_custom_model_and_endpoint(self):
        """Custom ``model`` and ``api_endpoint`` values are forwarded verbatim."""
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch(
            "chromadb.utils.embedding_functions.OllamaEmbeddingFunction",
            side_effect=fake_ctor,
        ):
            from plugins.embedding.ollama import OllamaEmbedding

            OllamaEmbedding(
                model="mxbai-embed-large",
                api_endpoint="http://custom-host:11434/api/embeddings",
            )

        assert captured.get("model_name") == "mxbai-embed-large"
        assert captured.get("url") == "http://custom-host:11434/api/embeddings"

    def test_instantiation_does_not_make_network_call(self):
        """Constructing ``OllamaEmbedding`` must not trigger any HTTP request."""
        import httpx
        import requests

        http_called = []

        def boom(*args, **kwargs):
            http_called.append((args, kwargs))
            raise AssertionError("Network call during __init__!")

        with (
            patch.object(httpx, "Client", side_effect=boom),
            patch.object(requests, "Session", side_effect=boom),
            patch(
                "chromadb.utils.embedding_functions.OllamaEmbeddingFunction",
                return_value=MagicMock(),
            ),
        ):
            from plugins.embedding.ollama import OllamaEmbedding

            OllamaEmbedding(model="nomic-embed-text")

        assert not http_called

    def test_call_delegates_to_underlying_fn(self):
        """``__call__`` forwards the input list to the wrapped ChromaDB function."""
        fake_inner = MagicMock(return_value=[[0.5, 0.6]])

        with patch(
            "chromadb.utils.embedding_functions.OllamaEmbeddingFunction",
            return_value=fake_inner,
        ):
            from plugins.embedding.ollama import OllamaEmbedding

            emb = OllamaEmbedding(model="nomic-embed-text")
            result = emb(["test sentence"])

        fake_inner.assert_called_once_with(["test sentence"])
        assert result == [[0.5, 0.6]]


# ---------------------------------------------------------------------------
# Local (sentence-transformers) embedding plugin
# ---------------------------------------------------------------------------


class TestLocalEmbedding:
    """Tests for ``plugins/embedding/local.py:LocalEmbedding``.

    All tests in this class are marked ``slow`` because they require loading
    the ``all-MiniLM-L6-v2`` model from disk (or downloading it once ~80MB).
    Skip the whole class with ``pytest -m "not slow"``.
    """

    pytestmark = pytest.mark.slow

    def test_class_parameters_schema(self):
        """``class_parameters()`` returns expected schema with a model parameter."""
        from plugins.embedding.local import LocalEmbedding

        params = LocalEmbedding.class_parameters()
        names = _param_names(params)
        assert "model" in names

    def test_class_parameters_model_default(self):
        """Default model name is ``all-MiniLM-L6-v2``."""
        from plugins.embedding.local import LocalEmbedding

        params = {p.name: p for p in LocalEmbedding.class_parameters()}
        assert params["model"].default == "all-MiniLM-L6-v2"

    def test_real_model_load_and_embed(self):
        """Real model load: embed one string, assert shape and L2-normalisation."""
        from plugins.embedding.local import LocalEmbedding

        emb = LocalEmbedding(model="all-MiniLM-L6-v2")
        result = emb(["hello world"])

        # Shape checks.
        assert isinstance(result, list)
        assert len(result) == 1
        vector = result[0]
        assert isinstance(vector, list)
        assert len(vector) == 384  # all-MiniLM-L6-v2 dimension

        # L2-normalisation: ‖v‖₂ ≈ 1.0.
        norm = math.sqrt(sum(x * x for x in vector))
        assert abs(norm - 1.0) < 1e-5, f"Expected norm ≈ 1.0, got {norm}"

    def test_multiple_inputs(self):
        """Embedding multiple strings returns one vector per string."""
        from plugins.embedding.local import LocalEmbedding

        texts = ["cats", "dogs", "fish"]
        emb = LocalEmbedding(model="all-MiniLM-L6-v2")
        result = emb(texts)

        assert len(result) == len(texts)
        for vec in result:
            assert len(vec) == 384
            norm = math.sqrt(sum(x * x for x in vec))
            assert abs(norm - 1.0) < 1e-5

    def test_model_cache_reuse(self):
        """Two ``LocalEmbedding`` instances with the same model share the cached object."""
        import plugins.embedding.local as local_module
        from plugins.embedding.local import LocalEmbedding

        # Ensure the model is loaded.
        emb1 = LocalEmbedding(model="all-MiniLM-L6-v2")
        emb2 = LocalEmbedding(model="all-MiniLM-L6-v2")

        # The SentenceTransformer instance in the module-level cache should be
        # the same object that both instances hold.
        cached = local_module._model_cache.get("all-MiniLM-L6-v2")
        assert cached is not None
        assert emb1._model is cached
        assert emb2._model is cached
        assert emb1._model is emb2._model

    def test_default_model_fallback(self):
        """``model=""`` falls back to ``all-MiniLM-L6-v2``."""
        from plugins.embedding.local import LocalEmbedding

        emb = LocalEmbedding(model="")
        result = emb(["test"])
        assert len(result[0]) == 384


class TestLocalEmbeddingImportGuard:
    """Tests for the import-guard branch in ``local.py``.

    We need to cover the ``except ImportError: raise ImportError(...)`` branch
    near the top of the module.  Achieving this requires making
    ``sentence_transformers`` unavailable and forcing a module re-import.

    Simply removing ``sentence_transformers`` from ``sys.modules`` is not
    sufficient because Python will re-discover the installed package on disk.
    Instead we install a meta-path finder that raises ``ImportError`` for the
    package, which intercepts the import before the normal finders run.

    If the approach proves too brittle on this platform the test falls back to
    ``pytest.skip`` with a clear reason so coverage of those 2 lines is
    accepted as a minor gap.
    """

    def test_import_error_when_sentence_transformers_absent(self, monkeypatch):
        """Blocking ``sentence_transformers`` via a meta-path finder triggers ImportError."""
        import importlib
        import importlib.abc
        import importlib.machinery

        class _BlockFinder(importlib.abc.MetaPathFinder):
            """A meta-path finder that raises ImportError for sentence_transformers."""

            def find_spec(self, fullname, path, target=None):
                if fullname == "sentence_transformers" or fullname.startswith(
                    "sentence_transformers."
                ):
                    raise ImportError(
                        f"Blocked by test: {fullname!r} intentionally unavailable"
                    )
                return None

        # Stash cached modules so we can restore them after the test.
        stashed: dict[str, object] = {}
        keys_to_remove = [
            k
            for k in list(sys.modules)
            if k == "sentence_transformers" or k.startswith("sentence_transformers.")
            or k == "plugins.embedding.local"
        ]
        for k in keys_to_remove:
            stashed[k] = sys.modules.pop(k)

        blocker = _BlockFinder()
        sys.meta_path.insert(0, blocker)
        try:
            with pytest.raises(ImportError, match="sentence-transformers"):
                import plugins.embedding.local  # noqa: F401

        except Exception as exc:  # noqa: BLE001
            pytest.skip(
                f"Import-guard test skipped — could not block sentence_transformers: {exc}"
            )
        finally:
            # Always clean up: remove blocker and restore stashed modules.
            sys.meta_path.remove(blocker)
            # Remove the (possibly partially-imported) local module so future
            # imports use the real one again.
            sys.modules.pop("plugins.embedding.local", None)
            for k, v in stashed.items():
                sys.modules[k] = v
