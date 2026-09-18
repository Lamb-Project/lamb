"""Generate the Moodle shell vocabulary from the installed library's Click map.

Only metadata and parameter parsing are reused. Never invoke CLI callbacks: they
load workstation profiles and render terminal output. Execution uses services.
"""
from dataclasses import dataclass
from functools import lru_cache
import shlex

import click
from moodle_cli.cli.readonly import READONLY_COMMANDS, _full_groups

# Local keyring/profile inspection has no meaning inside a Creator session.
EXCLUDED_GROUPS = frozenset({'auth'})
CURATED_WRITES = frozenset({'forum.post', 'forum.reply', 'assign.grade'})


@dataclass(frozen=True)
class CommandSpec:
    key: str
    description: str
    policy: str
    parser: click.Command

    def parse(self, arguments):
        try:
            # Parsing is deliberately separate from invoke(). No CLI context/client.
            with self.parser.make_context(self.key, list(arguments)) as context:
                return dict(context.params)
        except click.ClickException as exc:
            raise ValueError(exc.format_message()) from None
        except click.exceptions.Exit:
            raise ValueError('Use the Moodle command reference for help') from None

    def reference(self):
        with click.Context(self.parser, info_name='moodle ' + self.key.replace('.', ' ')) as ctx:
            return self.parser.get_help(ctx) + '\nPolicy: ' + self.policy


@lru_cache(maxsize=1)
def command_specs():
    groups = _full_groups()
    keys = {f'{group}.{name}' for group, names in READONLY_COMMANDS.items()
            if group not in EXCLUDED_GROUPS for name in names} | CURATED_WRITES
    result = {}
    for key in sorted(keys):
        group, name = key.split('.')
        try:
            source = groups[group].commands[name]
        except KeyError:
            raise RuntimeError(f'Installed Moodle command map drift: {key}') from None
        # Fail closed if a future library revision adds parsing callbacks: they
        # could perform I/O even without invoking the command callback itself.
        if any(parameter.callback for parameter in source.params):
            raise RuntimeError(f'Moodle parameter callback requires review: {key}')
        parser = click.Command(name, params=list(source.params), help=source.help,
                               add_help_option=False, context_settings={'allow_extra_args': False})
        result[key] = CommandSpec(key, source.help or '', 'ask' if key in CURATED_WRITES else 'auto', parser)
    return result


def prepare_moodle(command):
    """Strict CLI tokenization and typed parameters without executing anything."""
    tokens = shlex.split(command)
    if len(tokens) >= 2 and tokens[:2] == ['moodle', 'sync']:
        parser = click.Command('sync', params=[click.Argument(['course_id'],type=click.IntRange(min=1)), click.Option(['--section'],type=click.Choice(['course','forums','assignments','enrolment','calendar']))],add_help_option=False)
        spec=CommandSpec('sync','Refresh the private course cache','auto',parser)
        return spec,spec.parse(tokens[2:])
    if len(tokens) >= 3 and tokens[:3] == ['moodle','cache','show']:
        parser = click.Command('show', params=[click.Argument(['course_id'],type=click.IntRange(min=1)), click.Option(['--section'],required=True,type=click.Choice(['course','forums','assignments','enrolment','calendar']))],add_help_option=False)
        spec=CommandSpec('cache.show','Read a private cache section with its sync time','auto',parser)
        return spec,spec.parse(tokens[3:])
    if len(tokens) < 3 or tokens[0] != 'moodle':
        raise ValueError('Use moodle GROUP COMMAND; consult the Moodle command reference')
    key = '.'.join(tokens[1:3])
    spec = command_specs().get(key)
    if spec is None:
        raise ValueError(f'Unknown or unavailable Moodle command: {key}')
    return spec, spec.parse(tokens[3:])


def command_reference(*, enabled=False, connected=False, write_groups=(), allow_grade_write=False):
    if not (enabled and connected):
        return ''
    selected = []
    for key, spec in command_specs().items():
        if spec.policy == 'ask':
            if key.startswith('forum.') and 'forum' not in write_groups:
                continue
            if key == 'assign.grade' and not allow_grade_write:
                continue
        selected.append(spec.reference())
    return '# Moodle command reference\n\n' + '\n\n'.join(selected)
