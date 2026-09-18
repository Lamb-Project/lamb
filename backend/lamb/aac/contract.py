"""Command documentation generated from the installed liteshell contracts."""
import re


def command_reference(allowed=None):
    from lamb.aac.liteshell.shell import COMMAND_CONTRACTS
    from lamb.aac.liteshell.commands import COMMAND_REGISTRY
    from lamb.aac.authorization import ActionAuthorizer
    rows = ['# Installed command reference']
    for key in sorted(COMMAND_CONTRACTS):
        if allowed is not None and key not in allowed:
            continue
        replacement = {'test.scenarios': 'test.cases', 'test.scenario-detail': 'test.case-detail', 'test.delete-scenario': 'test.delete-case'}.get(key)
        if replacement and (allowed is None or replacement in allowed):
            continue
        if key not in COMMAND_REGISTRY:
            raise ValueError(f'Contract has no handler: {key}')
        minimum, maximum, flags = COMMAND_CONTRACTS[key]
        description = (COMMAND_REGISTRY[key].__doc__ or '').strip().split('\n')[0]
        command = key.replace('.', ' ')
        prefix = '' if key.startswith('frontend-manage.') else 'lamb '
        options = ' '.join('--'+f.replace('_','-') if len(f)>1 else '-'+f for f in flags.split())
        rows.append(f'- {prefix}{command}: args={minimum}..{maximum}; options={options or "none"}; policy={ActionAuthorizer().check(key)}. {description}')
    return '\n'.join(rows)


def skill_commands(text):
    """Extract authored inline/fenced command examples, not natural-language prose."""
    blocks = re.findall(r'```(?:aac-command|bash|sh)?\n(.*?)```', text, re.S)
    inline = re.findall(r'(?<!`)`([^`\n]+)`(?!`)', re.sub(r'```.*?```', '', text, flags=re.S))
    for block in blocks + inline:
        for line in block.splitlines():
            line = line.strip()
            if line.startswith(('lamb ', 'frontend-manage ', 'moodle ')):
                yield line


def validate_skill_contracts(pack):
    from lamb.aac.liteshell.shell import prepare_command
    errors = []
    for file in sorted(pack.skills_dir.glob('*.md')):
        for command in skill_commands(file.read_text()):
            # Use the production parser, substituting only authored placeholder
            # identifiers. No handler or HTTP operation is executed by preflight.
            try:
                example = re.sub(r'\b(?:RUBRIC_ID|LEARNING_SCENARIO_ID)\b', '00000000-0000-0000-0000-000000000001', command)
                example = re.sub(r'\b(?:ASSISTANT|KB|SCENARIO|CASE|RUN|CHAT|TEMPLATE|JOB)_ID\b', '1', example)
                example = re.sub(r'\{assistant_id\}|<assistant_id>|<id>', '1', example)
                example = re.sub(r'\b(?:COURSE|FORUM|DISCUSSION|POST|CONTEXT|ASSIGNMENT|USER)_ID\b', '1', example)
                example = example.replace('FILE_ID', 'mf_fixture')
                prepare_command(example)
            except (ValueError, TypeError) as exc:
                errors.append(f'{file.name}: {exc}: {command}')
    if errors:
        raise ValueError('\n'.join(errors))
    return True
