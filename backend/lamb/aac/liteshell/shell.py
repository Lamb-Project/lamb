"""Liteshell: parse CLI command strings and route to HTTP endpoints or local handlers.

The LLM sends commands like "lamb assistant get 4" and gets back
structured Python data. HTTP commands call Creator Interface endpoints
via in-process ASGI transport (no TCP, no deadlock). Local commands
(docs, help) read files directly.
"""

from __future__ import annotations

import shlex
import time
from dataclasses import dataclass, field
from typing import Any

from lamb.aac.liteshell.commands import COMMAND_REGISTRY, LOCAL_COMMANDS
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")


# Explicit supported shell surface. Unsupported CLI options fail instead of being ignored.
# key: (minimum positional arguments, maximum, accepted option names)
COMMAND_CONTRACTS = {
    'result.read': (1, 1, 'path offset'),
    'learning-scenario.list': (0, 0, ''),
    'learning-scenario.get': (1, 1, ''),
    'learning-scenario.create': (1, 1, 'content moodle_course_id'),
    'learning-scenario.update': (1, 1, 'revision title content moodle_course_id'),
    'learning-scenario.remove': (1, 1, 'revision'),
    'learning-scenario.duplicate': (1, 1, 'title'),
    'learning-scenario.default': (1, 1, ''),
    'learning-scenario.selected': (1, 1, ''),
    'learning-scenario.select': (2, 2, ''),
    'whoami': (0, 0, ''),
    'glossary': (1, 1, ''),
    'translate': (0, 1, 'reason command blocker topic section'),
    'assistant.export': (1, 1, ''),
    'kb.list-shared': (0, 0, ''),
    'kb.plugins': (0, 0, ''),
    'kb.query-plugins': (0, 0, ''),
    'kb.update': (1, 1, 'name n description d access_control'),
    'kb.delete': (1, 1, ''),
    'kb.delete-file': (2, 2, ''),
    'kb.share': (1, 1, 'enable disable'),
    'kb.ingest': (1, 1, 'plugin p url youtube param'),
    'job.get': (2, 2, ''),
    'job.retry': (2, 2, ''),
    'job.cancel': (2, 2, ''),
    'rubric.delete': (1, 1, ''),
    'rubric.duplicate': (1, 1, ''),
    'rubric.share': (1, 1, 'enable disable'),
    'rubric.generate': (1, 1, 'language lang model m'),
    'template.list-shared': (0, 0, 'limit l offset'),
    'template.create': (1, 1, 'description d system_prompt prompt_template shared'),
    'template.update': (1, 1, 'name n description d system_prompt prompt_template'),
    'template.delete': (1, 1, ''),
    'template.duplicate': (1, 1, 'new_name'),
    'template.share': (1, 1, 'enable disable'),
    'template.export': (1, 1000, ''),
    'test.cases': (1, 1, ''),
    'test.case-detail': (2, 2, ''),
    'test.delete-case': (2, 2, ''),
    'test.scenario-detail': (2, 2, ''),
    'test.delete-scenario': (2, 2, ''),

    "frontend-manage.current": (0, 0, ""), "frontend-manage.open": (1, 2, "tab"),
    "kb.jobs": (1, 1, ""), "kb.status": (1, 1, ""),
    "kb.create": (1, 1, "description d access_control"),
    "kb.query": (2, 2, "plugin p top_k k threshold t"),
    "test.evaluations": (1, 1, ""),
    "rubric.create": (1, 1, "criteria description subject grade_level scoring_type max_score"),
    "rubric.update": (1, 1, "title criteria weights description subject grade_level scoring_type max_score"),
    "assistant.list": (0, 0, "limit l offset"), "assistant.list-shared": (0, 0, ""),
    "assistant.get": (1, 1, ""), "assistant.config": (0, 0, ""),
    "assistant.debug": (1, 1, "message m"),
    "assistant.create": (1, 1, "system_prompt s description d prompt_template rag_top_k rag_collections llm connector prompt_processor rag_processor file_reference rubric_id rubric_format vision no_vision image_generation no_image_generation"),
    "assistant.update": (1, 1, "name n system_prompt s description d prompt_template rag_top_k rag_collections llm connector prompt_processor rag_processor file_reference rubric_id rubric_format vision no_vision image_generation no_image_generation"),
    "assistant.publish": (1, 1, ""), "assistant.unpublish": (1, 1, ""),
    "assistant.delete": (1, 1, ""), "assistant.list-published": (0, 0, ""),
    "assistant.chat": (1, 1, "message m bypass b chat_id persist"),
    "rubric.list": (0, 0, "limit l offset search s subject"), "rubric.list-public": (0, 0, "limit l offset search s subject"),
    "rubric.get": (1, 1, ""), "rubric.export": (1, 1, "format f"),
    "kb.list": (0, 0, ""), "kb.get": (1, 1, ""),
    "template.list": (0, 0, "limit l offset"), "template.get": (1, 1, ""),
    "test.update": (2, 2, "title message m description d type t expected e"),
    "test.scenarios": (1, 1, ""), "test.add": (1, 2, "title message m messages description d type t expected e"),
    "test.run": (1, 1, "bypass b case scenario s timeout"), "test.runs": (1, 1, "limit l"),
    "test.run-detail": (1, 2, "assistant a"), "test.evaluate": (2, 3, "assistant a notes n"),
    "session.rename": (1, 1, "session s"), "skill.list": (0, 0, ""),
    "skill.load": (1, 1, "assistant a language"), "docs.index": (0, 0, ""),
    "docs.read": (1, 1, "section"), "help": (0, 0, ""),
    "analytics.chats": (1, 1, "page per_page user_id search start_date end_date"),
    "analytics.chat-detail": (2, 2, ""), "analytics.stats": (1, 1, "start_date end_date"),
    "analytics.timeline": (1, 1, "period start_date end_date"),
}



# User-local paths are unavailable in frontend AAC, even if a staged server path exists.
FILESYSTEM_COMMANDS = {"aac.attach", "kb.upload", "library.upload", "library.import",
                       "rubric.import", "user.bulk-import"}
FILESYSTEM_OPTIONS = {
    "assistant.create": {"system_prompt_file", "file_path"},
    "assistant.update": {"file_path"},
    "assistant.export": {"output_file", "f"},
    "library.export": {"output_file", "f"},
    "org.export": {"output_file", "f"},
    "rubric.export": {"file"},
    "rubric.generate": {"save_to"},
    "template.export": {"file", "f"},
    "test.add": {"messages_file", "f"},
}
FILESYSTEM_MESSAGE = (
    "Hold your horses: you are in liteshell, not a terminal on the user's computer. "
    "This filesystem operation is unavailable here and was not executed. "
    "Do not invent a path, retry a server path, or ask for approval to run it. "
    "Explain the limitation to the user and show the relevant illustrated UI guide; "
    "the user must select, upload, import or download the file in the UI. "
    "For text input, use a supported inline option instead. "
    "Library-backed virtual files are planned for LAMB 1.0 and are not available here."
)


def reject_filesystem_operation(key, kwargs):
    if key in FILESYSTEM_COMMANDS or set(kwargs) & FILESYSTEM_OPTIONS.get(key, set()):
        raise ValueError(FILESYSTEM_MESSAGE)


def validate_command(key, args, kwargs):
    minimum, maximum, options = COMMAND_CONTRACTS[key]
    if not minimum <= len(args) <= maximum:
        raise ValueError(f"{key} expects {minimum}..{maximum} positional arguments")
    for positive, negative in [('enable', 'disable'), ('vision', 'no_vision'), ('image_generation', 'no_image_generation')]:
        if positive in kwargs and negative in kwargs:
            raise ValueError(f'Use only one of --{positive} or --{negative.replace("_", "-")}')
    if 'timeout' in kwargs:
        import math
        if not math.isfinite(float(kwargs['timeout'])) or float(kwargs['timeout']) < 1:
            raise ValueError('timeout must be a finite number of seconds >= 1')
    if key == 'kb.ingest':
        if not kwargs.get('plugin', kwargs.get('p')):
            raise ValueError('Provide --plugin NAME')
        for value in kwargs.get('param', []):
            if not isinstance(value, str) or '=' not in value:
                raise ValueError('Use --param key=value')
            name = value.split('=', 1)[0].lower()
            if name in {'file', 'files', 'file_path', 'path', 'filename', 'directory'}:
                raise ValueError(FILESYSTEM_MESSAGE)
    if key == 'test.add' and 'messages' in kwargs:
        from lamb.aac.liteshell.commands import _messages
        _messages(kwargs)
    if key.endswith('.share') and not (set(kwargs) & {'enable', 'disable'}):
        raise ValueError('Specify --enable or --disable')
    if key == "test.update" and not (set(kwargs) & set(options.split())):
        raise ValueError("Provide at least one field to update")
    allowed = set(options.split()) | {"output", "o"}
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Unsupported options for {key}: {', '.join(sorted(unknown))}")
    for option, value in kwargs.items():
        if option in BOOLEAN_OPTIONS:
            if value not in (True, "true", "false"):
                raise ValueError(f"Invalid boolean for {option}")
        elif value is True:
            raise ValueError(f"Missing value for {option}")
    if kwargs.get("output", kwargs.get("o", "json")) != "json":
        raise ValueError("The AAC shell returns structured JSON; use -o json")
    if key.startswith('learning-scenario.'):
        required = {'update': ['revision'], 'remove': ['revision'], 'duplicate': ['title']}.get(key.split('.')[1], [])
        if any(field not in kwargs for field in required):
            raise ValueError('Missing required options: '+', '.join('--'+field for field in required))
        if 'moodle_course_id' in kwargs:
            course = kwargs['moodle_course_id']
            if not (key.endswith('.update') and course == 'none') and (not str(course).isdigit() or int(course) < 1):
                raise ValueError('Use a positive Moodle course ID, or none when updating')
        if 'revision' in kwargs and int(kwargs['revision']) < 1:
            raise ValueError('Revision must be positive')
        if key.endswith('.update') and not ({'title', 'content', 'moodle_course_id'} & kwargs.keys()):
            raise ValueError('Provide --title, --content or --moodle-course-id')
    if key == "frontend-manage.open":
        from lamb.aac.frontend import destination
        destination(args, kwargs)
    if key.startswith("analytics."):
        if int(args[0]) < 1:
            raise ValueError("assistant_id must be positive")
        args[0] = str(int(args[0]))
    if "s" in kwargs and key in {"assistant.create", "assistant.update"}:
        kwargs["system_prompt"] = kwargs.pop("s")
    if "rag_top_k" in kwargs and int(kwargs["rag_top_k"]) < 1:
        raise ValueError("rag_top_k must be positive")

def prepare_command(command_str: str, allowlist=None):
    """Resolve and validate without HTTP, handlers or side effects, before authorization."""
    tokens = shlex.split(command_str.strip())
    if tokens and tokens[0] == "lamb":
        tokens = tokens[1:]
    if not tokens:
        raise ValueError("No command provided. Use 'lamb help' to list supported commands.")
    group = tokens[0]
    if allowlist is not None and group not in allowlist:
        raise ValueError(f"Command '{group}' not allowed. Available: {sorted(allowlist)}")
    if group == 'moodle':
        from lamb.moodle.contract import prepare_moodle
        spec,params=prepare_moodle(shlex.join(tokens))
        return 'moodle.'+spec.key, [], params, False
    key = f"{group}.{tokens[1]}" if len(tokens) > 1 and not tokens[1].startswith("-") else group
    arg_tokens = tokens[2:] if key != group else tokens[1:]
    _, preliminary_options = _parse_args(arg_tokens)
    reject_filesystem_operation(key, preliminary_options)
    if key not in COMMAND_REGISTRY:
        if group in COMMAND_REGISTRY:
            key, arg_tokens = group, tokens[1:]
        else:
            available = sorted(k.replace('.', ' ') for k in COMMAND_REGISTRY if k.startswith(group + '.'))
            hint = f"Supported commands: {', '.join('lamb ' + k for k in available)}." if available else "Use 'lamb help' to list supported commands."
            raise ValueError(f"Unknown command '{key.replace('.', ' ')}': this command does not exist and was not executed. {hint}")
    args, kwargs = _parse_args(arg_tokens)
    help_requested = kwargs.pop("help", kwargs.pop("h", False))
    if not help_requested:
        validate_command(key, args, kwargs)
    aliases = {'d': 'description', 'n': 'name'}
    if key in {'assistant.create', 'assistant.update'}:
        aliases['s'] = 'system_prompt'
    for alias, canonical in aliases.items():
        if alias in kwargs:
            if canonical in kwargs: raise ValueError(f'Duplicate option --{canonical}')
            kwargs[canonical] = kwargs.pop(alias)
    return key, args, kwargs, help_requested

@dataclass
class ShellResult:
    """Result of a liteshell command execution."""
    success: bool
    data: Any = None
    error: str | None = None
    command: str = ""
    elapsed_ms: float = 0.0
    result_binding: dict | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"success": self.success}
        if self.success:
            d["data"] = self.data
        else:
            d["error"] = self.error
        return d


@dataclass
class LiteShell:
    """CLI-shaped command executor for the AAC agent.

    Parses command strings and routes them to Creator Interface HTTP
    endpoints via ASGI transport, or to local handlers for docs/help.

    Attributes:
        server_url: Base URL (unused for ASGI transport, kept for logging).
        token: JWT auth token for the current user.
        user_email: Authenticated user's email.
        organization_id: User's organization ID.
        allowlist: If set, only these top-level command groups are allowed.
        history: Record of executed commands (for session logging).
    """
    server_url: str
    token: str
    user_email: str
    organization_id: int
    user_id: int = 0
    moodle: Any = None
    frontend: Any = None
    allowlist: set[str] | None = None
    allowed_commands: set[str] | None = None
    knowledge: dict = field(default_factory=dict)
    history: list[ShellResult] = field(default_factory=list)
    _http_client: Any = field(default=None, repr=False)

    def _get_http(self):
        """Lazy-init the async ASGI HTTP client."""
        if self._http_client is None:
            from lamb.aac.liteshell.http_client import AsyncLambClient
            self._http_client = AsyncLambClient(token=self.token)
        return self._http_client

    async def close(self):
        """Close the HTTP client if open."""
        if self._http_client is not None:
            await self._http_client.close()
            self._http_client = None

    async def execute(self, command_str: str, *, confirmed: bool = False, review: dict | None = None) -> ShellResult:
        """Parse and execute a CLI-like command string.

        Args:
            command_str: e.g. "lamb assistant get 4"

        Returns:
            ShellResult with structured data or error.
        """
        start = time.monotonic()
        try:
            result = await self._dispatch(command_str, confirmed=confirmed, review=review)
            result.command = command_str
            result.elapsed_ms = (time.monotonic() - start) * 1000
        except Exception as e:
            logger.error(f"Liteshell error for '{command_str}': {e}")
            result = ShellResult(
                success=False,
                error=str(e),
                command=command_str,
                elapsed_ms=(time.monotonic() - start) * 1000,
            )
        self.history.append(result)
        return result

    def model_result(self, command_str, payload):
        """Bound the model view while raw ShellResult/audit/transcript stay intact."""
        from lamb.aac.result_store import ResultStore, compact
        from lamb.aac.result_authority import authority
        try:
            key, args, _, _ = prepare_command(command_str)
        except (ValueError, TypeError):
            key, args = 'unknown', []
        origin = {'command': key, 'authority': authority(key, args, payload)}
        if payload.get('skill_loaded'):
            origin['skill_id'] = payload['skill_loaded']
        if self.history and self.history[-1].command == command_str and self.history[-1].result_binding:
            origin['moodle'] = self.history[-1].result_binding
        try:
            store = ResultStore(int(self.organization_id), int(self.user_id))
        except (ValueError, TypeError):
            logger.warning('Private AAC result storage unavailable; full readback caching is disabled for this result')
            store = None
        return compact(payload, store=store, origin=origin,
                       trusted_workflow=bool(payload.get('skill_loaded')) or key == 'skill.load')

    async def _dispatch(self, command_str: str, *, confirmed: bool = False, review: dict | None = None) -> ShellResult:
        key, args, kwargs, help_requested = prepare_command(command_str, self.allowlist)
        if self.allowed_commands is not None and key not in self.allowed_commands:
            raise ValueError('Command is outside your role; ask the appropriate administrator')
        if key.startswith('moodle.'):
            if self.moodle is None:
                raise ValueError('Moodle connector is unavailable in this conversation')
            import asyncio
            import threading
            cancel = threading.Event()
            loop = asyncio.get_running_loop()
            bridge = getattr(self.frontend, '__self__', None)
            def progress(index, total):
                emit = getattr(bridge, 'emit', None)
                if not emit or cancel.is_set() or loop.is_closed():
                    return
                future = asyncio.run_coroutine_threadsafe(emit({'status':'tool',
                    'command':f"{key.replace('.', ' ')}: {index}/{total}"}), loop)
                try:
                    future.result(timeout=1)
                except Exception:
                    future.cancel()
            binding = self.moodle.result_binding()
            try:
                data=await asyncio.to_thread(self.moodle.execute,key.removeprefix('moodle.'),kwargs,
                    confirmed=confirmed,review=review,cancel=cancel,progress=progress)
            except asyncio.CancelledError:
                # Cancelling to_thread alone leaves the worker running. Task
                # requests observe this flag before/after each read and publish.
                cancel.set()
                raise
            from lamb.moodle.imports import PreparedImport, ResumeImport
            from lamb.moodle.folders import PreparedFolder, deliver_folder
            if isinstance(data, PreparedFolder):
                data = await deliver_folder(data, self._get_http(), self.moodle, self.user_id)
            if isinstance(data, (PreparedImport, ResumeImport)):
                from lamb.moodle.import_delivery import deliver
                data = await deliver(data, self._get_http(), self.moodle, self.user_id)
            if self.moodle.result_binding() != binding:
                raise PermissionError('Moodle connection changed; result withheld. Check the operation status before repeating it.')
            from lamb.moodle.runtime import SELF_READS
            from lamb.moodle.task_contract import task_specs
            unscoped = SELF_READS | task_specs().keys()
            if key.removeprefix('moodle.') not in unscoped:
                course = kwargs.get('course_id') or self.moodle.context.get('course_id')
                if key == 'moodle.calendar.events' or (key == 'moodle.badge.user' and kwargs.get('user_id') in (None, binding.get('moodle_user_id'))):
                    course = kwargs.get('course_id')  # self-scoped without an explicit filter
                if isinstance(course, (tuple, list)):
                    binding['course_ids'] = sorted(set(map(int, course)))
                elif course:
                    binding['course_id'] = int(course)
            if key in {'moodle.chart.read','moodle.analytics.result','moodle.analytics.capabilities'}:
                binding['course_id'] = data['course_id']
            if key == 'moodle.chart.list':
                binding['course_ids'] = sorted({item['course_id'] for item in data['items']})
                scopes = [scope for item in data['items'] for scope in item.get('resource_scopes', [])]
                if scopes: binding['resource_scopes'] = scopes
            elif isinstance(data,dict) and data.get('resource_scopes'):
                binding['resource_scopes'] = data['resource_scopes']
            if key == 'moodle.chart.list':
                grade_scopes = [scope for item in data['items'] for scope in item.get('grade_scopes', [])]
                if grade_scopes: binding['grade_scopes'] = grade_scopes
            elif isinstance(data,dict) and data.get('grade_scopes'):
                binding['grade_scopes'] = data['grade_scopes']
            if key == 'moodle.chart.list':
                completion_scopes = [scope for item in data['items'] for scope in item.get('completion_scopes', [])]
                if completion_scopes: binding['completion_scopes'] = completion_scopes
            elif isinstance(data,dict) and data.get('completion_scopes'):
                binding['completion_scopes'] = data['completion_scopes']
            if key in {'moodle.chart.submissions','moodle.analytics.run'}:
                binding['course_id'] = kwargs['course_id']
                emit = getattr(bridge, 'emit', None)
                if emit:
                    await emit({'status': 'chart', 'chart_id': data['chart_id'], 'title': data['title']})
            return ShellResult(success=True,data=data,result_binding=binding)
        handler = COMMAND_REGISTRY[key]
        if help_requested:
            return ShellResult(success=True, data={"command": key, "help": handler.__doc__ or "",
                "options": COMMAND_CONTRACTS[key][2].split()})

        # Build context for the handler
        ctx = CommandContext(
            http=None if key in LOCAL_COMMANDS else self._get_http(),
            server_url=self.server_url,
            token=self.token,
            user_email=self.user_email,
            organization_id=self.organization_id,
            user_id=self.user_id,
            frontend=self.frontend,
            knowledge=self.knowledge,
        )

        # Local commands are sync, HTTP commands are async
        if key in LOCAL_COMMANDS:
            data = handler(ctx, args, kwargs)
        else:
            data = await handler(ctx, args, kwargs)
        return ShellResult(success=True, data=data)

    def get_available_commands(self) -> dict[str, str]:
        """Return available commands and their descriptions."""
        result = {}
        for key, func in sorted(COMMAND_REGISTRY.items()):
            if self.allowed_commands is not None and key not in self.allowed_commands:
                continue
            doc = func.__doc__ or ""
            result[f"lamb {key.replace('.', ' ')}"] = doc.split("\n")[0].strip()
        return result


@dataclass
class CommandContext:
    """Context passed to every command handler."""
    http: Any  # AsyncLambClient for HTTP commands
    server_url: str
    token: str
    user_email: str
    organization_id: int
    user_id: int = 0
    frontend: Any = None
    knowledge: dict = field(default_factory=dict)


BOOLEAN_OPTIONS = {'bypass', 'b', 'persist', 'enable', 'disable', 'vision', 'no_vision',
                   'image_generation', 'no_image_generation', 'shared', 'help', 'h'}


def _parse_args(tokens: list[str]) -> tuple[list[str], dict[str, Any]]:
    args, kwargs = [], {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith('--') or (token.startswith('-') and len(token) == 2):
            raw = token.lstrip('-')
            if '=' in raw:
                key, value = raw.split('=', 1)
            else:
                key, value = raw, True
                normalized = key.replace('-', '_')
                if i + 1 < len(tokens) and (normalized not in BOOLEAN_OPTIONS or tokens[i + 1] in {'true', 'false'}):
                    following = tokens[i + 1]
                    if not following.startswith('-') or following[1:2].isdigit():
                        value = following
                        i += 1
            key = key.replace('-', '_')
            if key == 'param':
                kwargs.setdefault(key, []).append(value)
            elif key in kwargs:
                raise ValueError(f'Duplicate option --{key.replace("_", "-")}')
            else:
                kwargs[key] = value
        else:
            args.append(token)
        i += 1
    return args, kwargs
