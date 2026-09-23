<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/** Current quiz-report authority only; never reads attempts or learner rows. */
class quiz_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'quizid'=>new external_value(PARAM_INT, 'Quiz ID'),
            'groupid'=>new external_value(PARAM_INT, 'Exact population group, zero for course-wide', VALUE_DEFAULT, 0),
        ]);
    }

    public static function execute($courseid, $quizid, $groupid = 0): array {
        global $DB, $USER;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','quizid','groupid'));
        extract($p, EXTR_OVERWRITE);
        if ($courseid<1 || $quizid<1 || $groupid<0) {
            throw new \invalid_parameter_exception('Invalid quiz evidence scope');
        }
        $context=\context_course::instance($courseid);
        self::validate_context($context);
        require_capability('moodle/course:enrolreview',$context);
        if (!is_enrolled($context,$USER,'',true)) {
            throw new \required_capability_exception($context,'moodle/course:enrolreview','nopermissions','');
        }
        $course=get_course($courseid);
        $cm=get_coursemodule_from_instance('quiz',$quizid,$courseid,false,MUST_EXIST);
        $info=get_fast_modinfo($course,$USER->id)->get_cm($cm->id);
        if (!$info->uservisible) {
            throw new \invalid_parameter_exception('Quiz is no longer visible');
        }
        $modulecontext=\context_module::instance($cm->id);
        self::validate_context($modulecontext);
        require_capability('mod/quiz:viewreports',$modulecontext);
        $allgroups=has_capability('moodle/site:accessallgroups',$modulecontext);
        if ($groupid) {
            $DB->get_record('groups',['id'=>$groupid,'courseid'=>$courseid],'id',MUST_EXIST);
            if ((!$allgroups && !groups_is_member($groupid,$USER->id)) ||
                    ($cm->groupingid && !$DB->record_exists('groupings_groups',
                        ['groupingid'=>$cm->groupingid,'groupid'=>$groupid]))) {
                throw new \invalid_parameter_exception('Group is outside the quiz population scope');
            }
        } else if (!$allgroups && (groups_get_course_groupmode($course)==SEPARATEGROUPS ||
                groups_get_activity_groupmode($cm,$course)==SEPARATEGROUPS)) {
            throw new \required_capability_exception($modulecontext,'moodle/site:accessallgroups','nopermissions','');
        }
        return ['authorized'=>true,'courseid'=>$courseid,'quizid'=>$quizid,'groupid'=>$groupid];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL, 'Current permission only'),
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'quizid'=>new external_value(PARAM_INT, 'Quiz ID'),
            'groupid'=>new external_value(PARAM_INT, 'Group ID'),
        ]);
    }
}
