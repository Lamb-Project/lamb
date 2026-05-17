"""LLM extraction backends for KG-RAG concept/relation extraction.

Each backend wraps a vendor's chat-completion endpoint and returns a
parsed JSON object. Backends are enabled/disabled via tri-state env
vars (``LLM_EXTRACTION_OPENAI=DISABLE`` / ``LLM_EXTRACTION_OLLAMA=DISABLE``).
"""
