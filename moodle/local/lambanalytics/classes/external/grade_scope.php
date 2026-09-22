<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/** Permission-only check for course-wide raw assignment grade snapshots. */
class grade_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'assignmentid'=>new external_value(PARAM_INT, 'Assignment ID'),
        ]);
    }

    public static function execute($courseid, $assignmentid): array {
        global $CFG, $USER;
        require_once($CFG->dirroot.'/mod/assign/locallib.php');
        $p = self::validate_parameters(self::execute_parameters(), compact('courseid','assignmentid'));
        extract($p, EXTR_OVERWRITE);
        if ($courseid < 1 || $assignmentid < 1) {
            throw new \invalid_parameter_exception('Invalid assignment evidence scope');
        }
        $context = \context_course::instance($courseid);
        self::validate_context($context);
        require_capability('moodle/course:enrolreview', $context);
        if (!is_enrolled($context, $USER, '', true)) {
            throw new \required_capability_exception($context, 'moodle/course:enrolreview', 'nopermissions', '');
        }
        $course = get_course($courseid);
        $cm = get_coursemodule_from_instance('assign', $assignmentid, $courseid, false, MUST_EXIST);
        $info = get_fast_modinfo($course, $USER->id)->get_cm($cm->id);
        if (!$info->uservisible) {
            throw new \invalid_parameter_exception('Assignment is no longer visible');
        }
        $modulecontext = \context_module::instance($cm->id);
        self::validate_context($modulecontext);
        require_capability('mod/assign:grade', $modulecontext);
        // The saved distribution has no group filter. Do not authorize it for a
        // caller restricted to one separate group, even if the raw WS is broad.
        if ((groups_get_course_groupmode($course) == SEPARATEGROUPS ||
                groups_get_activity_groupmode($cm, $course) == SEPARATEGROUPS) &&
                !has_capability('moodle/site:accessallgroups', $modulecontext)) {
            throw new \required_capability_exception($modulecontext, 'moodle/site:accessallgroups', 'nopermissions', '');
        }
        $assignment = new \assign($modulecontext, $cm, $course);
        $assignment->require_view_grades();
        return ['authorized'=>true,'courseid'=>$courseid,'assignmentid'=>$assignmentid];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL, 'Current permission only'),
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'assignmentid'=>new external_value(PARAM_INT, 'Assignment ID'),
        ]);
    }
}
