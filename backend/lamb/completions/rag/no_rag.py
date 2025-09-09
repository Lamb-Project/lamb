from typing import Dict, Any, List
from lamb.lamb_classes import Assistant

def rag_processor(messages: List[Dict[str, Any]], assistant: Assistant = None) -> Dict[str, Any]:
    """
    A RAG processor that returns an empty context.
    This is useful when you want to explicitly specify no RAG processing.
    """
    return {
        "context": "",
        "sources": []
    } 