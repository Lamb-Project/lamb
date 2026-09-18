"""Curated writes, with lineage resolved using a separate read-only client."""
from moodle_cli.services.course import CourseService
from moodle_cli.services.forum import ForumService
from .scope import MoodleScope

FORUM_WRITES = frozenset({'forum.post', 'forum.reply'})


def verify_forum_target(client, key, params, *, owner_moodle_id, context):
    course = context.get('course_id')
    if not course:
        raise PermissionError('Select an instructor course before posting')
    MoodleScope(client, owner_moodle_id).require_teacher(course)
    contents = CourseService(client).get_contents(course)
    forums = [int(m['instance']) for section in contents for m in section.modules
              if m.get('modname') == 'forum']
    if key == 'forum.post':
        if params['forum_id'] in forums:
            return
    elif key == 'forum.reply':
        service = ForumService(client)
        for forum in forums:
            for discussion in service.get_discussions(forum):
                # Discussion IDs and root post IDs are distinct in Moodle.
                for post in service.get_posts(discussion.discussion or discussion.id):
                    if post.id == params['post_id']:
                        return
    raise PermissionError('Moodle forum or post is outside the selected instructor course')


def write_forum(client, key, params):
    service = ForumService(client)
    if key == 'forum.post':
        result = service.add_discussion(params['forum_id'], params['subject'], params['message'])
        return {'discussion_id': result, 'forum_id': params['forum_id'], 'posted': True}
    if key == 'forum.reply':
        result = service.reply_to_post(params['post_id'], params['subject'], params['message'])
        return {'post_id': result, 'parent_post_id': params['post_id'], 'posted': True}
    raise PermissionError('Unsupported Moodle write')
