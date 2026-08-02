"""AAC agent loop.

Two implementations behind one factory: the legacy double loop (`AgentLoop`)
and the tau-engine loop (`TauAgentLoop`, Phase 3 of the AAC refactoring).
Selection is by the AAC_LOOP environment variable: "tau" or "legacy"
(default legacy until the tau soak completes). Both classes share the
constructor signature and public surface the router uses.
"""

import os

from lamb.aac.agent.loop import AgentLoop


def create_agent_loop(**kwargs):
    """Instantiate the configured agent-loop implementation."""
    if os.environ.get("AAC_LOOP", "legacy").strip().lower() == "tau":
        from lamb.aac.agent.tau_loop import TauAgentLoop
        return TauAgentLoop(**kwargs)
    return AgentLoop(**kwargs)


__all__ = ["AgentLoop", "create_agent_loop"]
