<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/** Exact current discussion authority. No posts, authors or dates are returned. */
class forum_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'forumid'=>new external_value(PARAM_INT, 'Forum ID'),
            'discussionid'=>new external_value(PARAM_INT, 'Discussion ID'),
            'groupid'=>new external_value(PARAM_INT, 'Population group, zero for course-wide', VALUE_DEFAULT, 0),
        ]);
    }

    public static function execute($courseid, $forumid, $discussionid, $groupid=0): array {
        global $DB, $USER, $CFG;
        require_once($CFG->dirroot.'/mod/forum/lib.php');
        $p=self::validate_parameters(self::execute_parameters(), compact('courseid','forumid','discussionid','groupid'));
        extract($p, EXTR_OVERWRITE);
        if ($courseid<1 || $forumid<1 || $discussionid<1 || $groupid<0) {
            throw new \invalid_parameter_exception('Invalid forum evidence scope');
        }
        $context=\context_course::instance($courseid);
        self::validate_context($context);
        require_capability('moodle/course:enrolreview', $context);
        if (!is_enrolled($context, $USER, '', true)) {
            throw new \required_capability_exception($context, 'moodle/course:enrolreview', 'nopermissions', '');
        }
        $course=get_course($courseid);
        $cm=get_coursemodule_from_instance('forum', $forumid, $courseid, false, MUST_EXIST);
        $info=get_fast_modinfo($course, $USER->id)->get_cm($cm->id);
        if (!$info->uservisible) throw new \invalid_parameter_exception('Forum is no longer visible');
        $modulecontext=\context_module::instance($cm->id);
        self::validate_context($modulecontext);
        require_capability('mod/forum:viewdiscussion', $modulecontext);
        $allgroups=has_capability('moodle/site:accessallgroups', $modulecontext);
        if ($groupid) {
            $DB->get_record('groups', ['id'=>$groupid, 'courseid'=>$courseid], 'id', MUST_EXIST);
            if ((!$allgroups && !groups_is_member($groupid, $USER->id)) ||
                    ($cm->groupingid && !$DB->record_exists('groupings_groups',
                        ['groupingid'=>$cm->groupingid, 'groupid'=>$groupid]))) {
                throw new \invalid_parameter_exception('Group is outside forum evidence scope');
            }
        } else if (!$allgroups && (groups_get_course_groupmode($course)==SEPARATEGROUPS ||
                groups_get_activity_groupmode($cm, $course)==SEPARATEGROUPS)) {
            throw new \required_capability_exception($modulecontext, 'moodle/site:accessallgroups', 'nopermissions', '');
        }
        $discussion=$DB->get_record('forum_discussions',
            ['id'=>$discussionid, 'course'=>$courseid, 'forum'=>$forumid],
            'id,course,forum,groupid,timestart,timeend,userid', MUST_EXIST);
        if ($groupid && $discussion->groupid>0 && $discussion->groupid!=$groupid) {
            throw new \invalid_parameter_exception('Discussion is outside selected group');
        }
        $forum=(object)['id'=>$forumid, 'course'=>$courseid];
        if (!forum_user_can_see_discussion($forum, $discussion, $modulecontext, $USER)) {
            throw new \required_capability_exception($modulecontext, 'mod/forum:viewdiscussion', 'nopermissions', '');
        }
        return ['authorized'=>true, 'courseid'=>$courseid, 'forumid'=>$forumid,
            'discussionid'=>$discussionid, 'groupid'=>$groupid];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL, 'Current permission only'),
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'forumid'=>new external_value(PARAM_INT, 'Forum ID'),
            'discussionid'=>new external_value(PARAM_INT, 'Discussion ID'),
            'groupid'=>new external_value(PARAM_INT, 'Population group'),
        ]);
    }
}
