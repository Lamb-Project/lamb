"""Keep loaded Moodle recipes aligned with the current executable capability."""
import re


def render_permissions(prompt, commands):
    commands = set(commands)
    from .contract import all_specs
    unavailable = {'moodle ' + key.replace('.', ' '): 'moodle.' + key for key in all_specs()}

    def filter_examples(match):
        lines = [line for line in match.group(1).splitlines()
                 if not any((line.strip() == command or line.strip().startswith(command + ' ')) and key not in commands
                            for command, key in unavailable.items())]
        return '```aac-command\n' + '\n'.join(lines) + '\n```' if any(line.strip() for line in lines) else ''

    prompt = re.sub(r'```aac-command\n(.*?)\n```', filter_examples, prompt, flags=re.S)
    limits = []
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
