"""Typed resource evidence for Moodle reads and confirmed writes."""


def command_artifacts(command, result):
    from lamb.aac.liteshell.shell import prepare_command
    try:
        key, _, params, _ = prepare_command(command)
    except ValueError:
        return []
    data = getattr(result, 'data', None)
    data = data if isinstance(data, dict) else {}
    if key == 'moodle.forum.reply':
        return [{'type': 'moodle_post', 'id': data.get('post_id'), 'action': 'reply',
                 'parent_post_id': params['post_id']}]
    if key == 'moodle.forum.post':
        return [{'type': 'moodle_discussion', 'id': data.get('discussion_id'), 'action': 'create',
                 'forum_id': params['forum_id']}]
    if key == 'moodle.assign.grade':
        return [{'type': 'moodle_assignment', 'id': params['assignment_id'], 'action': 'grade',
                 'user_id': params['user_id']}]
    if key == 'moodle.import.file':
        return [{'type': 'kb' if params['kb_id'] is not None else 'file',
                 'id': params['kb_id'] if params['kb_id'] is not None else data.get('path'),
                 'action': 'import', 'source_file_id': params['file_id']}]
    identifier = next((value for name, value in params.items() if name.endswith('_id') and value is not None), None)
    return [{'type': 'moodle', 'id': identifier, 'action': 'read'}]
