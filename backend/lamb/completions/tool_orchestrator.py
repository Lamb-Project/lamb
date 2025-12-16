from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
from lamb.completions.orchestrators.base import OrchestrationResult, ToolConfig
import importlib
import os
import glob
import logging

logger = logging.getLogger(__name__)


class ToolOrchestrator:
    """
    Orchestrator engine that loads and delegates to strategy plugins.

    The orchestrator:
    1. Reads the orchestrator strategy from metadata
    2. Loads the appropriate strategy plugin
    3. Delegates tool execution and placeholder replacement to the plugin
    """

    def __init__(self):
        self._strategy_cache = {}

    def orchestrate(
        self,
        request: Dict[str, Any],
        assistant: Assistant,
        metadata: Dict[str, Any],
        verbose: bool = False,
        stream_callback: callable = None
    ) -> OrchestrationResult:
        """
        Main entry point for multi-tool orchestration.

        Args:
            request: The completion request
            assistant: The assistant object
            metadata: Parsed assistant metadata containing orchestrator and tools config
            verbose: If True, return detailed markdown report instead of processed messages
            stream_callback: Optional callback function for streaming progress updates

        Returns:
            OrchestrationResult with processed messages ready for LLM (or verbose report)
        """
        # Get orchestrator strategy (default: sequential)
        strategy_name = metadata.get("orchestrator", "sequential")

        # Load strategy plugin
        strategy = self._load_strategy(strategy_name)
        if not strategy:
            logger.error(f"Orchestrator strategy '{strategy_name}' not found, falling back to sequential")
            strategy = self._load_strategy("sequential")

        # Parse tool configs from metadata
        tool_configs = self._parse_tool_configs(metadata.get("tools", []))

        # Delegate to strategy plugin
        return strategy.execute(request, assistant, tool_configs, verbose=verbose, stream_callback=stream_callback)

    def _load_strategy(self, strategy_name: str):
        """Load orchestrator strategy plugin from completions/orchestrators/"""
        if strategy_name in self._strategy_cache:
            return self._strategy_cache[strategy_name]

        try:
            module = importlib.import_module(
                f"lamb.completions.orchestrators.{strategy_name}"
            )
            orchestrator = module.get_orchestrator()
            self._strategy_cache[strategy_name] = orchestrator
            return orchestrator
        except ImportError as e:
            logger.error(f"Failed to load orchestrator strategy '{strategy_name}': {e}")
            return None

    def _parse_tool_configs(self, tools_list: List[Dict]) -> List[ToolConfig]:
        """Convert raw tool config dicts to ToolConfig objects."""
        configs = []
        for tool_dict in tools_list:
            configs.append(ToolConfig(
                plugin=tool_dict.get("plugin", tool_dict.get("type", "")),
                placeholder=tool_dict.get("placeholder", "context"),
                enabled=tool_dict.get("enabled", True),
                config=tool_dict.get("config", {})
            ))
        return configs

    @staticmethod
    def get_available_strategies() -> List[Dict[str, str]]:
        """List all available orchestrator strategies (for API/UI)."""
        import os
        import glob

        strategies = []
        orchestrators_dir = os.path.join(
            os.path.dirname(__file__), "orchestrators"
        )

        for filepath in glob.glob(os.path.join(orchestrators_dir, "*.py")):
            filename = os.path.basename(filepath)
            if filename.startswith("__") or filename == "base.py":
                continue

            module_name = filename[:-3]
            try:
                module = importlib.import_module(
                    f"lamb.completions.orchestrators.{module_name}"
                )
                strategies.append({
                    "name": module.get_name(),
                    "description": getattr(module, 'get_description', lambda: "")()
                })
            except Exception as e:
                logger.warning(f"Failed to load orchestrator {module_name}: {e}")

        return strategies


# Global instance
tool_orchestrator = ToolOrchestrator()