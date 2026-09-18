from lamb.moodle.workflow import render_permissions


def test_readonly_recipe_omits_write_examples_and_offers_human_handoff():
    prompt = '```aac-command\nmoodle forum posts DISCUSSION_ID\nmoodle forum reply --post-id ID\n```'
    result = render_permissions(prompt, {'moodle.forum.posts'})
    assert 'moodle forum posts DISCUSSION_ID' in result
    assert 'moodle forum reply --post-id' not in result
    assert 'instructor can copy the draft' in result
    assert 'Saving grades is unavailable' in result


def test_enabled_forum_write_keeps_recipe_but_grade_stays_unavailable():
    prompt = '```aac-command\nmoodle forum reply --post-id ID\nmoodle assign grade 3\n```'
    result = render_permissions(prompt, {'moodle.forum.reply'})
    assert 'moodle forum reply --post-id ID' in result
    assert 'moodle assign grade 3' not in result
    assert 'Forum posting is unavailable' not in result
    assert 'Saving grades is unavailable' in result
