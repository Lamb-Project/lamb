from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from lamb.lamb_classes import Assistant


@dataclass
class OrchestrationResult:
    """Result from orchestrator after all tools executed and placeholders replaced"""
    processed_messages: List[Dict[str, str]]  # Messages ready for LLM
    sources: List[Dict[str, Any]]             # Aggregated sources from all tools
    tool_results: Dict[str, Any]              # Raw results from each tool (for debugging)
    error: Optional[str] = None
    verbose_report: Optional[str] = None      # Detailed markdown report when verbose=True


@dataclass
class ToolConfig:
    """Tool configuration from assistant metadata"""
    plugin: str           # Tool plugin name (e.g., "simple_rag")
    placeholder: str      # Placeholder this tool fills (e.g., "context")
    enabled: bool = True
    config: Dict[str, Any] = None  # Tool-specific configuration


class BaseOrchestrator(ABC):
    """
    Abstract base class for orchestrator strategy plugins.

    Orchestrators are responsible for:
    1. Executing tool plugins (in strategy-specific order)
    2. Collecting results from each tool
    3. Replacing placeholders in the prompt template
    4. Preparing final messages for the LLM connector
    """

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """Return unique identifier for this orchestrator strategy"""
        pass

    @classmethod
    def get_description(cls) -> str:
        """Return human-readable description"""
        return "Base orchestrator strategy"

    @abstractmethod
    def execute(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        verbose: bool = False,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> OrchestrationResult:
        """
        Execute all tools and prepare messages for LLM.

        Args:
            request: The completion request
            assistant: The assistant object
            tool_configs: List of tool configurations
            verbose: If True, return detailed markdown report instead of processed messages
            stream_callback: Optional callback function for streaming progress updates

        This method should:
        1. Execute enabled tools according to the strategy
        2. Collect tool outputs with their placeholders
        3. Replace placeholders in assistant.prompt_template
        4. Return processed messages ready for the connector (or verbose report)
        """
        pass

    def _replace_placeholders(
        self,
        template: str,
        tool_results: Dict[str, str],
        user_input: str
    ) -> str:
        """
        Common placeholder replacement logic.
        Subclasses can override for custom behavior.
        """
        result = template

        # Replace tool placeholders
        for placeholder, content in tool_results.items():
            tag = "{" + placeholder + "}"
            if tag in result:
                result = result.replace(tag, "\n\n" + content + "\n\n" if content else "")

        # Replace user input
        result = result.replace("{user_input}", "\n\n" + user_input + "\n\n")

        # Clean up unreplaced placeholders
        import re
        result = re.sub(r'\{[a-z_]+\}', '', result)

        return result

    def _generate_verbose_report(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        tool_results: Dict[str, Any],
        all_sources: List[Dict[str, Any]],
        final_messages: List[Dict[str, str]]
    ) -> str:
        """Generate a detailed markdown report for verbose mode."""

        import json
        from datetime import datetime

        report_lines = [
            "# Multi-Tool Orchestration Report",
            f"**Timestamp:** {datetime.now().isoformat()}",
            f"**Orchestrator:** {self.get_name()}",
            f"**Assistant:** {assistant.name if hasattr(assistant, 'name') else 'Unknown'}",
            "",
            "## Request Summary",
            f"- **User Message:** {self._extract_user_text(request.get('messages', [{}])[-1].get('content', ''))[:200]}{'...' if len(self._extract_user_text(request.get('messages', [{}])[-1].get('content', ''))) > 200 else ''}",
            f"- **Stream Mode:** {request.get('stream', False)}",
            "",
            "## Tool Configuration",
        ]

        for i, tool_config in enumerate(tool_configs, 1):
            report_lines.extend([
                f"### Tool {i}: {tool_config.plugin}",
                f"- **Placeholder:** `{tool_config.placeholder}`",
                f"- **Enabled:** {tool_config.enabled}",
                f"- **Configuration:**",
                "```json",
                json.dumps(tool_config.config or {}, indent=2),
                "```",
                ""
            ])

        report_lines.extend([
            "## Tool Execution Results",
        ])

        for placeholder, result in tool_results.items():
            tool_name = placeholder.split('_', 1)[1] if '_' in placeholder else placeholder
            report_lines.extend([
                f"### {placeholder} ({tool_name})",
                f"- **Content Length:** {len(result) if result else 0} characters",
                f"- **Has Sources:** {bool(result)}",
                f"- **Content Preview:**",
                "```",
                (result[:500] + "..." if result and len(result) > 500 else result or "No content") if result else "No content",
                "```",
                ""
            ])

        report_lines.extend([
            "## Sources Summary",
            f"- **Total Sources:** {len(all_sources)}",
        ])

        if all_sources:
            for i, source in enumerate(all_sources[:10], 1):  # Show first 10 sources
                report_lines.extend([
                    f"### Source {i}",
                    f"- **Title:** {source.get('title', 'Unknown')}",
                    f"- **URL:** {source.get('url', 'N/A')}",
                    f"- **Similarity:** {source.get('similarity', 'N/A')}",
                    ""
                ])

            if len(all_sources) > 10:
                report_lines.append(f"*... and {len(all_sources) - 10} more sources*\n")

        report_lines.extend([
            "## Final Messages Sent to LLM",
        ])

        for i, msg in enumerate(final_messages):
            role = msg.get('role', 'unknown')
            content_preview = msg.get('content', '')[:300] + ('...' if len(msg.get('content', '')) > 300 else '')
            report_lines.extend([
                f"### Message {i+1} ({role})",
                f"```\n{content_preview}\n```",
                ""
            ])

        return "\n".join(report_lines)

    def _extract_user_text(self, content) -> str:
        """Extract text from potentially multimodal message."""
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            return " ".join(texts)
        return str(content)