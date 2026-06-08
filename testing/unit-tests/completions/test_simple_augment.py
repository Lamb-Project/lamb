from lamb.completions.pps.simple_augment import COMPATIBLE_RAG


class TestSimpleAugmentCompatibleRag:
    def test_declares_compatible_rag_list(self):
        assert isinstance(COMPATIBLE_RAG, list)
        assert "simple_rag" in COMPATIBLE_RAG
        assert "context_aware_rag" in COMPATIBLE_RAG
        assert "single_file_rag" in COMPATIBLE_RAG
        assert "no_rag" in COMPATIBLE_RAG

    def test_does_not_include_new_rags(self):
        assert "library_file_rag" not in COMPATIBLE_RAG
