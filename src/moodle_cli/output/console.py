"""Shared Rich console instance."""

from rich.console import Console

console = Console()
error_console = Console(stderr=True)
