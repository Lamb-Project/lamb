from typing import Dict, Any, List
from lamb.completions.orchestrators.base import BaseOrchestrator, OrchestrationResult, ToolConfig
from lamb.completions.tool_registry import tool_registry
from lamb.lamb_classes import Assistant
import logging
import re

logger = logging.getLogger(__name__)


class SequentialOrchestrator(BaseOrchestrator):
    """
    Execute tools one after another in order defined in metadata.

    KEY FEATURE: Each tool sees the prompt with PREVIOUS placeholders already replaced.
    This enables chained context where later tools can see earlier tool outputs.
    """

    @classmethod
    def get_name(cls) -> str:
        return "sequential"

    @classmethod
    def get_description(cls) -> str:
        return "Execute tools in order; each tool sees previous outputs (chained context)"

    def execute(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        verbose: bool = False,
        stream_callback: callable = None
    ) -> OrchestrationResult:
        """
        Execute tools sequentially with chained context.

        For each tool:
        1. Build current context (template with previous placeholders filled)
        2. Execute tool with this context visible
        3. Replace this tool's placeholder
        4. Move to next tool
        """

        tool_results = {}
        all_sources = []

        # Start with the original template
        current_template = assistant.prompt_template or ""
        user_input = self._extract_user_text(
            request.get('messages', [{}])[-1].get('content', '')
        )

        for tool_config in tool_configs:
            if not tool_config.enabled:
                continue

            try:
                tool = tool_registry.get_tool(tool_config.plugin)
                if not tool:
                    logger.warning(f"Tool plugin '{tool_config.plugin}' not found")
                    continue

                module = tool["module"]

                # Stream progress: tool starting
                if stream_callback:
                    stream_callback(f"🔄 Executing tool: {tool_config.plugin} → {tool_config.placeholder}")

                # CHAINED CONTEXT: Pass current template state to tool
                # Tool can see previous placeholders already filled
                augmented_request = {
                    **request,
                    "_current_context": current_template,  # Template with previous fills
                    "_accumulated_results": tool_results.copy()
                }

                result = module.tool_processor(
                    augmented_request, assistant, tool_config.config or {}
                )

                placeholder = tool_config.placeholder  # e.g., "2_context"
                content = result.get("content", "")
                tool_results[placeholder] = content

                # Stream progress: tool completed
                if stream_callback:
                    content_length = len(content) if content else 0
                    stream_callback(f"✅ Tool completed: {tool_config.plugin} → {content_length} chars to {placeholder}")

                # Replace THIS tool's placeholder in the running template
                placeholder_tag = "{" + placeholder + "}"
                if placeholder_tag in current_template:
                    current_template = current_template.replace(
                        placeholder_tag,
                        "\n\n" + content + "\n\n" if content else ""
                    )

                if result.get("sources"):
                    all_sources.extend(result["sources"])

            except Exception as e:
                logger.error(f"Tool {tool_config.plugin} failed: {e}")
                if stream_callback:
                    stream_callback(f"❌ Tool failed: {tool_config.plugin} - {str(e)}")
                # Continue with other tools rather than failing completely

        # Final step: replace {user_input} and clean up
        current_template = current_template.replace(
            "{user_input}", "\n\n" + user_input + "\n\n"
        )
        current_template = re.sub(r'\{[a-z0-9_]+\}', '', current_template)  # Clean unused

        # Build final messages
        processed_messages = self._build_final_messages(
            assistant, request.get('messages', []), current_template
        )

        # Generate verbose report if requested
        verbose_report = None
        if verbose:
            verbose_report = self._generate_verbose_report(
                request, assistant, tool_configs, tool_results, all_sources, processed_messages
            )

        return OrchestrationResult(
            processed_messages=processed_messages,
            sources=all_sources,
            tool_results=tool_results,
            verbose_report=verbose_report
        )

    def _build_final_messages(
        self,
        assistant: Assistant,
        messages: List[Dict],
        final_content: str
    ) -> List[Dict[str, str]]:
        """Build messages with the fully processed template."""

        processed = []

        # Add system prompt
        if assistant.system_prompt:
            processed.append({
                "role": "system",
                "content": assistant.system_prompt
            })

        # Add conversation history (all but last)
        if len(messages) > 1:
            processed.extend(messages[:-1])

        # Add final processed message
        if messages:
            processed.append({
                "role": messages[-1].get("role", "user"),
                "content": final_content
            })

        return processed

    def _extract_user_text(self, content) -> str:
        """Extract text from potentially multimodal message."""
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            return " ".join(texts)
        return str(content)


def get_orchestrator():
    return SequentialOrchestrator()


def get_name():
    return SequentialOrchestrator.get_name()


def get_description():
    return SequentialOrchestrator.get_description()