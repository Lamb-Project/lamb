"""Auto-discovery regression test for lamb-kb-server plugins.

Mirrors the library-manager test of the same name. The KB server has
three plugin categories: ``chunking``, ``vector_db``, ``embedding``.
We drop a synthetic ``.py`` into the chunking and vector_db sub-packages
and assert ``_discover_plugins`` registers them with no other code edits.

Pattern: extend the sub-package's ``__path__`` with a tmpdir, write a
new plugin module into that tmpdir, call the production discovery
helper, assert the plugin's ``name`` is registered, then restore.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from main import _discover_plugins
from plugins.base import ChunkingRegistry, VectorDBRegistry

_CHUNKER_NAME = "test_dropin_chunker_h"
_BACKEND_NAME = "test_dropin_vectordb_h"


_CHUNKER_SOURCE = textwrap.dedent(
    f"""
    from plugins.base import Chunk, ChunkingRegistry, ChunkingStrategy


    @ChunkingRegistry.register
    class TestDropinChunker(ChunkingStrategy):
        name = "{_CHUNKER_NAME}"
        description = "Synthetic chunker for discovery test."

        def chunk(self, document, params=None):
            return [Chunk(text=document.text, metadata={{}})]
    """
).strip()


_VECTORDB_SOURCE = textwrap.dedent(
    f"""
    from plugins.base import VectorDBBackend, VectorDBRegistry


    @VectorDBRegistry.register
    class TestDropinVectorDB(VectorDBBackend):
        name = "{_BACKEND_NAME}"
        description = "Synthetic vector backend for discovery test."

        def create_collection(self, *, collection_id, storage_path, embedding_function):
            return collection_id

        def delete_collection(self, *, collection_id, storage_path):
            return None

        def add_chunks(self, *, collection_id, storage_path, chunks, embedding_function):
            return len(chunks)

        def delete_by_source(self, *, collection_id, storage_path, source_item_id):
            return 0

        def query(self, *, collection_id, storage_path, query_text, top_k, embedding_function):
            return []
    """
).strip()


@pytest.fixture
def isolate_chunking_subpackage(tmp_path: Path):
    """Add a tmpdir onto ``plugins.chunking.__path__`` and snapshot registry."""
    import plugins.chunking as ch_pkg  # noqa: PLC0415

    original_paths = list(ch_pkg.__path__)
    original_registry = dict(ChunkingRegistry._plugins)

    ch_pkg.__path__.insert(0, str(tmp_path))
    yield tmp_path

    ch_pkg.__path__[:] = original_paths
    ChunkingRegistry._plugins.clear()
    ChunkingRegistry._plugins.update(original_registry)
    sys.modules.pop(f"plugins.chunking.{_CHUNKER_NAME}", None)


@pytest.fixture
def isolate_vectordb_subpackage(tmp_path: Path):
    """Same as above but for ``plugins.vector_db``."""
    import plugins.vector_db as vdb_pkg  # noqa: PLC0415

    original_paths = list(vdb_pkg.__path__)
    original_registry = dict(VectorDBRegistry._plugins)

    vdb_pkg.__path__.insert(0, str(tmp_path))
    yield tmp_path

    vdb_pkg.__path__[:] = original_paths
    VectorDBRegistry._plugins.clear()
    VectorDBRegistry._plugins.update(original_registry)
    sys.modules.pop(f"plugins.vector_db.{_BACKEND_NAME}", None)


def test_chunking_plugin_dropin_is_discovered(
    isolate_chunking_subpackage: Path,
) -> None:
    """A .py file in plugins/chunking/ is auto-registered by discovery."""
    plugin_file = isolate_chunking_subpackage / f"{_CHUNKER_NAME}.py"
    plugin_file.write_text(_CHUNKER_SOURCE, encoding="utf-8")

    assert not ChunkingRegistry.is_registered(_CHUNKER_NAME)

    _discover_plugins()

    assert ChunkingRegistry.is_registered(_CHUNKER_NAME), (
        f"Drop-in chunker was not registered. Got: {sorted(ChunkingRegistry._plugins)}"
    )


def test_vector_db_plugin_dropin_is_discovered(
    isolate_vectordb_subpackage: Path,
) -> None:
    """A .py file in plugins/vector_db/ is auto-registered by discovery."""
    plugin_file = isolate_vectordb_subpackage / f"{_BACKEND_NAME}.py"
    plugin_file.write_text(_VECTORDB_SOURCE, encoding="utf-8")

    assert not VectorDBRegistry.is_registered(_BACKEND_NAME)

    _discover_plugins()

    assert VectorDBRegistry.is_registered(_BACKEND_NAME), (
        f"Drop-in vector backend was not registered. Got: {sorted(VectorDBRegistry._plugins)}"
    )


def test_broken_chunker_does_not_block_other_plugins(
    isolate_chunking_subpackage: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One broken chunker file does not abort discovery of other plugins."""
    (isolate_chunking_subpackage / "broken_chunker_h.py").write_text(
        "raise RuntimeError('intentional')\n", encoding="utf-8"
    )
    (isolate_chunking_subpackage / f"{_CHUNKER_NAME}.py").write_text(
        _CHUNKER_SOURCE, encoding="utf-8"
    )

    with caplog.at_level("WARNING"):
        _discover_plugins()

    assert ChunkingRegistry.is_registered(_CHUNKER_NAME)
    assert any("broken_chunker_h" in (rec.getMessage() or "") for rec in caplog.records), (
        "Expected a warning log mentioning the broken plugin file."
    )
