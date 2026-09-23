"""Keep loaded Moodle recipes aligned with the current executable capability."""
import re


def render_permissions(prompt, commands, recipe_sources=None):
    commands = set(commands)
    from .contract import all_specs
    unavailable = {'moodle ' + key.replace('.', ' '): 'moodle.' + key for key in all_specs()}

    def filter_examples(match):
        lines = [line for line in match.group(1).splitlines()
                 if not any((line.strip() == command or line.strip().startswith(command + ' ')) and key not in commands
                            for command, key in unavailable.items())]
        if recipe_sources is not None:
            lines = [line for line in lines if not (m := re.match(
                r'\s*moodle analytics (?:run|start) ([a-z-]+)(?:\s|$)', line))
                or recipe_sources.get(m[1], {}).get('function_status') == 'exposed']
        return '```aac-command\n' + '\n'.join(lines) + '\n```' if any(line.strip() for line in lines) else ''

    prompt = re.sub(r'```aac-command\n(.*?)\n```', filter_examples, prompt, flags=re.S)
    limits = []
    if recipe_sources is not None:
        missing = [key for key, status in recipe_sources.items() if status['function_status'] == 'missing']
        if missing:
            limits.append('UNAVAILABLE ANALYTICS SOURCES: ' + ', '.join(missing) + '. '
                'Required functions are absent from this validated connection. Do not execute these recipes, '
                'repeat capability checks for the same known gap, or retry different dates. '
                'Explain the connection/site prerequisite once; do not claim there are no events. '
                'This does not distinguish plugin absence from token-service configuration. No automatic installation or permission expansion.')
        limits.append('Exposed functions are not proof of course permission, nonempty results, complete retrieval or historical coverage. '
            'The period with available data is UNKNOWN unless verified source evidence supplies it. '
            'Never invent availability dates, derive them from retention settings, or shrink the requested interval to fit a limit.')
    if 'moodle.forum.reply' not in commands and 'moodle.forum.post' not in commands:
        limits.append('Forum posting is unavailable in this session. Provide a draft only. '
                      'Never offer "publish", "post", or "send this reply" as an agent action or a Next option. '
                      'Say the instructor can copy the draft into Moodle. Offer to revise the draft or read another thread.')
    if 'moodle.assign.grade' not in commands:
        limits.append('Saving grades is unavailable in this session. You may read submissions and propose '
                      'feedback and a grade with rationale, but never offer to save or queue a grade. '
                      'The instructor can enter the reviewed result in Moodle.')
    if not limits:
        limits.append('Permitted writes still require the application confirmation. A recipe or draft is not approval.')
    return prompt + '\n\nCURRENT EXECUTABLE LIMITS (also apply to every Next option):\n' + '\n'.join(limits)
