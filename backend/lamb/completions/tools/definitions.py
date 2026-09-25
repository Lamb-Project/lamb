"""
Tool JSON schema definitions for Workshop assistants.

Each definition follows the OpenAI function-calling format
so it can be passed directly as `tools` in the API request.
"""

# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
CALCULATOR_DEF = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports +, -, *, /, **, % and parentheses.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g. (3 + 5) * 2",
                }
            },
            "required": ["expression"],
        },
    },
}

# ---------------------------------------------------------------------------
# KB Query
# ---------------------------------------------------------------------------
KB_QUERY_DEF = {
    "type": "function",
    "function": {
        "name": "kb_query",
        "description": "Search the knowledge base for relevant information on a topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up in the knowledge base",
                }
            },
            "required": ["query"],
        },
    },
}

# ---------------------------------------------------------------------------
# Sandbox Exec (default disabled — controlled by feature flag)
# ---------------------------------------------------------------------------
SANDBOX_EXEC_DEF = {
    "type": "function",
    "function": {
        "name": "sandbox_exec",
        "description": "Execute Python code in a secure sandbox. Only available when enabled by organization.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                }
            },
            "required": ["code"],
        },
    },
}

# Convenience: all workshop tools
WORKSHOP_TOOLS = {
    "calculator": CALCULATOR_DEF,
    "kb_query": KB_QUERY_DEF,
    "sandbox_exec": SANDBOX_EXEC_DEF,
}

DEFAULT_WORKSHOP_TOOLS = [CALCULATOR_DEF, KB_QUERY_DEF]