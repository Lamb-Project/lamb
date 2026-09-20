"""Typed resource evidence for Moodle reads and confirmed writes."""


def command_artifacts(command, result):
    from lamb.aac.liteshell.shell import prepare_command
    try:
        key, _, params, _ = prepare_command(command)
    except ValueError:
        return []
    data = getattr(result, 'data', None)
    data = data if isinstance(data, dict) else {}
    if key in {'moodle.import.folder', 'moodle.folder.finish'}:
        return [{'type': 'moodle_folder_batch', 'id': data.get('batch_id') or params.get('batch_id'),
                 'action': 'import', 'status': data.get('status'), 'counts': data.get('counts', {})}]
    if key == 'moodle.forum.reply':
        return [{'type': 'moodle_post', 'id': data.get('post_id'), 'action': 'reply',
                 'parent_post_id': params['post_id']}]
    if key == 'moodle.forum.post':
        return [{'type': 'moodle_discussion', 'id': data.get('discussion_id'), 'action': 'create',
                 'forum_id': params['forum_id']}]
    if key == 'moodle.assign.grade':
        return [{'type': 'moodle_assignment', 'id': params['assignment_id'], 'action': 'grade',
                 'user_id': params['user_id']}]
    if key in {'moodle.import.file', 'moodle.import.page', 'moodle.import.book'}:
        return [{'type': 'kb' if params['kb_id'] is not None else 'file',
                 'id': params['kb_id'] if params['kb_id'] is not None else data.get('result', {}).get('path'),
                 'action': 'import', 'source_file_id': params['source_ref']}]
    if key in {'moodle.import.refresh', 'moodle.import.finish'}:
        return [{'type': 'moodle_import', 'id': params['import_id'], 'action': key.rsplit('.', 1)[1]}]
    identifier = next((value for name, value in params.items() if name.endswith('_id') and value is not None), None)
    return [{'type': 'moodle', 'id': identifier, 'action': 'read'}]
