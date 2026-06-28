import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from lamb.completions import main as main_module
from lamb.completions.main import load_and_validate_plugins


class TestCompatibleRagValidation:
    def _make_plugin_config(self, pps="simple_augment", rag="no_rag", doc_rag=""):
        return {
            "prompt_processor": pps,
            "connector": "openai",
            "llm": "gpt-4",
            "rag_processor": rag,
            "document_rag": doc_rag,
        }

    @patch.object(main_module, "load_plugins")
    @patch("importlib.import_module")
    def test_compatible_rag_passes_when_rag_in_list(self, mock_import, mock_load):
        mock_pps_module = MagicMock()
        mock_pps_module.COMPATIBLE_RAG = ["simple_rag", "no_rag"]
        mock_import.return_value = mock_pps_module

        mock_load.side_effect = lambda t: (
            {"simple_augment": MagicMock()} if t == "pps"
            else {"simple_rag": MagicMock(), "no_rag": MagicMock()} if t == "rag"
            else {"openai": MagicMock()}
        )

        config = self._make_plugin_config(pps="simple_augment", rag="simple_rag")
        pps, connectors, rag_processors = load_and_validate_plugins(config)

        assert "simple_augment" in pps

    @patch.object(main_module, "load_plugins")
    @patch("importlib.import_module")
    def test_compatible_rag_rejects_incompatible_rag(self, mock_import, mock_load):
        mock_pps_module = MagicMock()
        mock_pps_module.COMPATIBLE_RAG = ["library_file_rag", "no_rag"]
        mock_import.return_value = mock_pps_module

        mock_load.side_effect = lambda t: (
            {"kvcache_augment": MagicMock()} if t == "pps"
            else {"simple_rag": MagicMock(), "no_rag": MagicMock(), "library_file_rag": MagicMock()} if t == "rag"
            else {"openai": MagicMock()}
        )

        config = self._make_plugin_config(pps="kvcache_augment", rag="simple_rag")

        with pytest.raises(HTTPException) as exc_info:
            load_and_validate_plugins(config)
        assert exc_info.value.status_code == 400
        assert "not compatible" in str(exc_info.value.detail)

    @patch.object(main_module, "load_plugins")
    @patch("importlib.import_module")
    def test_compatible_rag_validates_document_rag(self, mock_import, mock_load):
        mock_pps_module = MagicMock()
        mock_pps_module.COMPATIBLE_RAG = ["library_file_rag", "no_rag"]
        mock_import.return_value = mock_pps_module

        mock_load.side_effect = lambda t: (
            {"kvcache_augment": MagicMock()} if t == "pps"
            else {"no_rag": MagicMock(), "library_file_rag": MagicMock(), "single_file_rag": MagicMock()} if t == "rag"
            else {"openai": MagicMock()}
        )

        config = self._make_plugin_config(
            pps="kvcache_augment", rag="no_rag", doc_rag="single_file_rag"
        )

        with pytest.raises(HTTPException) as exc_info:
            load_and_validate_plugins(config)
        assert exc_info.value.status_code == 400
        assert "document_rag" in str(exc_info.value.detail)

    @patch.object(main_module, "load_plugins")
    @patch("importlib.import_module")
    def test_no_compatible_rag_skips_validation(self, mock_import, mock_load):
        mock_pps_module = MagicMock(spec=[])
        mock_import.return_value = mock_pps_module

        mock_load.side_effect = lambda t: (
            {"some_pps": MagicMock()} if t == "pps"
            else {"no_rag": MagicMock()} if t == "rag"
            else {"openai": MagicMock()}
        )

        config = self._make_plugin_config(pps="some_pps", rag="no_rag")
        pps, connectors, rag_processors = load_and_validate_plugins(config)

        assert "some_pps" in pps
