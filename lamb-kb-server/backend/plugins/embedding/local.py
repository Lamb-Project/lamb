"""Local (sentence-transformers) embedding function plugin.

Uses Hugging Face ``sentence-transformers`` to run embeddings entirely on the
local machine — no external API calls.  If the package is not installed this
module raises ``ImportError`` at import time so
:func:`main._discover_plugins` silently skips registration.

Model weights are cached in a module-level dict keyed by model name so that
repeated ingestion jobs within one server process do not reload the model from
disk each time.
"""

from __future__ import annotations

import logging

# Guard import: if sentence_transformers is missing the module will raise
# ImportError and the plugin will be skipped by the discovery mechanism.
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "sentence-transformers is not installed; "
        "the 'local' embedding plugin will not be available."
    )

from plugins.base import EmbeddingFunction, EmbeddingRegistry, PluginParameter

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"

# Module-level cache: model_name → SentenceTransformer instance
_model_cache: dict[str, SentenceTransformer] = {}


def _get_model(model_name: str) -> SentenceTransformer:
    """Return a cached ``SentenceTransformer`` for *model_name*."""
    if model_name not in _model_cache:
        logger.info("Loading SentenceTransformer model: %s", model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
        logger.info("Model '%s' loaded and cached", model_name)
    return _model_cache[model_name]


@EmbeddingRegistry.register
class LocalEmbedding(EmbeddingFunction):
    """Sentence-Transformers local embedding vendor.

    Embeddings are produced entirely on-device — suitable for air-gapped
    deployments or development without an OpenAI API key.

    The model is loaded once per process and cached in ``_model_cache`` to
    avoid expensive repeated disk reads during batch ingestion.  Vectors are
    L2-normalised (``normalize_embeddings=True``) so cosine similarity can be
    computed as a dot product.
    """

    name = "local"
    description = "Local sentence-transformers embeddings (no external API)"

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        api_key: str = "",
        api_endpoint: str = "",
    ) -> None:
        super().__init__(model=model, api_key=api_key, api_endpoint=api_endpoint)
        resolved_model = model or _DEFAULT_MODEL
        self._model = _get_model(resolved_model)

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed *input* strings and return L2-normalised float vectors."""
        vectors = self._model.encode(
            input,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.tolist()

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter(
                "model",
                "string",
                "Sentence-Transformers model name or local path",
                _DEFAULT_MODEL,
            ),
        ]
