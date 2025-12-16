import asyncio
from typing import Dict, Any, List
from lamb.completions.orchestrators.base import BaseOrchestrator, OrchestrationResult, ToolConfig
from lamb.completions.tool_registry import tool_registry
from lamb.lamb_classes import Assistant
import logging

logger = logging.getLogger(__name__)


class ParallelOrchestrator(BaseOrchestrator):
    """
    Execute all tools in parallel (concurrently).
    Best for independent tools that don't depend on each other.
    """

    @classmethod
    def get_name(cls) -> str:
        return "parallel"

    @classmethod
    def get_description(cls) -> str:
        return "Execute all tools concurrently for maximum speed"

    def execute(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        tool_configs: List[ToolConfig],
        verbose: bool = False,
        stream_callback: callable = None
    ) -> OrchestrationResult:
        """Execute all enabled tools in parallel, then replace placeholders."""

        # Filter enabled tools
        enabled_tools = [t for t in tool_configs if t.enabled]

        if not enabled_tools:
            return OrchestrationResult(
                processed_messages=[{
                    "role": "user",
                    "content": "No tools configured or enabled"
                }],
                sources=[],
                tool_results={}
            )

        # Stream progress: starting parallel execution
        if stream_callback:
            stream_callback(f"🚀 Starting parallel execution of {len(enabled_tools)} tools")

        # Execute all tools concurrently
        tool_results = {}
        all_sources = []

        # Use asyncio.gather for parallel execution
        async def run_all():
            tasks = []
            for tool_config in enabled_tools:
                tasks.append(self._execute_tool_async(request, assistant, tool_config, stream_callback))
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            results = asyncio.run(run_all())
        except RuntimeError:
            # If we're already in an event loop, run sequentially
            results = []
            for tool_config in enabled_tools:
                try:
                    result = self._execute_tool_sync(request, assistant, tool_config, stream_callback)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Tool {tool_config.plugin} failed: {e}")
                    if stream_callback:
                        stream_callback(f"❌ Tool failed: {tool_config.plugin} - {str(e)}")
                    results.append(e)

        # Collect results
        for tool_config, result in zip(enabled_tools, results):
            if isinstance(result, Exception):
                logger.error(f"Tool {tool_config.plugin} failed: {result}")
                continue

            placeholder = tool_config.placeholder  # e.g., "1_context"
            tool_results[placeholder] = result.get("content", "")
            if result.get("sources"):
                all_sources.extend(result["sources"])

        # Build processed messages
        messages = request.get('messages', [])
        processed_messages = self._build_messages(
            assistant, messages, tool_results
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

    async def _execute_tool_async(self, request, assistant, tool_config: ToolConfig, stream_callback: callable = None):
        """Execute a single tool plugin asynchronously."""
        tool = tool_registry.get_tool(tool_config.plugin)
        if not tool:
            raise ValueError(f"Tool plugin '{tool_config.plugin}' not found")

        if stream_callback:
            stream_callback(f"🔄 Starting tool: {tool_config.plugin} → {tool_config.placeholder}")

        module = tool["module"]
        # Run in thread pool to avoid blocking
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: module.tool_processor(request, assistant, tool_config.config or {})
            )

        if stream_callback:
            content_length = len(result.get("content", "")) if result else 0
            stream_callback(f"✅ Completed tool: {tool_config.plugin} → {content_length} chars to {tool_config.placeholder}")

        return result

    def _execute_tool_sync(self, request, assistant, tool_config: ToolConfig, stream_callback: callable = None):
        """Execute a single tool plugin synchronously."""
        tool = tool_registry.get_tool(tool_config.plugin)
        if not tool:
            raise ValueError(f"Tool plugin '{tool_config.plugin}' not found")

        if stream_callback:
            stream_callback(f"🔄 Starting tool: {tool_config.plugin} → {tool_config.placeholder}")

        module = tool["module"]
        result = module.tool_processor(request, assistant, tool_config.config or {})

        if stream_callback:
            content_length = len(result.get("content", "")) if result else 0
            stream_callback(f"✅ Completed tool: {tool_config.plugin} → {content_length} chars to {tool_config.placeholder}")

        return result

    def _build_messages(
        self,
        assistant: Assistant,
        messages: List[Dict],
        tool_results: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Build final messages with placeholders replaced."""

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

        # Process last message with template
        if messages:
            last_message = messages[-1]
            user_input = self._extract_user_text(last_message.get("content", ""))

            if assistant.prompt_template:
                content = self._replace_placeholders(
                    assistant.prompt_template,
                    tool_results,
                    user_input
                )
            else:
                content = user_input

            processed.append({
                "role": last_message.get("role", "user"),
                "content": content
            })

        return processed

    def _extract_user_text(self, content) -> str:
        """Extract text from potentially multimodal message."""
        if isinstance(content, list):
            texts = [p.get("text", "") for p in content if p.get("type") == "text"]
            return " ".join(texts)
        return str(content)


def get_orchestrator():
    return ParallelOrchestrator()


def get_name():
    return ParallelOrchestrator.get_name()


def get_description():
    return ParallelOrchestrator.get_description()