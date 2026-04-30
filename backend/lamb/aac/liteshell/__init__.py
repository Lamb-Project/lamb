"""Liteshell: CLI-shaped tool interface for the AAC agent.

Parses command strings and routes them to LAMB service functions directly.
No HTTP, no subprocess — pure Python dispatch.
"""

from lamb.aac.liteshell.shell import LiteShell

__all__ = ["LiteShell"]
