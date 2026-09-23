<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/** Exact assessment grade-item authority; never invokes a grade report or regrade. */
class gradebook_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'gradeitemid'=>new external_value(PARAM_INT, 'Exact assessment grade item ID'),
            'groupid'=>new external_value(PARAM_INT, 'Population group; zero for course-wide', VALUE_DEFAULT, 0),
        ]);
    }

    public static function execute($courseid, $gradeitemid, $groupid=0): array {
        global $DB, $USER;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','gradeitemid','groupid'));
        extract($p, EXTR_OVERWRITE);
        if ($courseid<1 || $gradeitemid<1 || $groupid<0) {
            throw new \invalid_parameter_exception('Invalid gradebook evidence scope');
        }
        $context=\context_course::instance($courseid);
        self::validate_context($context);
        require_capability('moodle/course:enrolreview',$context);
        require_capability('moodle/grade:viewall',$context);
        // The adapter describes stored gradebook evidence, including hidden state.
        // Do not expose a selectively blanked report as a complete distribution.
        require_capability('moodle/grade:viewhidden',$context);
        if (!is_enrolled($context,$USER,'',true)) {
            throw new \required_capability_exception($context,'moodle/course:enrolreview','nopermissions','');
        }
        $course=get_course($courseid);
        $item=$DB->get_record('grade_items',['id'=>$gradeitemid,'courseid'=>$courseid],
            'id,courseid,itemtype,itemmodule,iteminstance,outcomeid',MUST_EXIST);
        if (!in_array($item->itemtype,['mod','manual'],true) || !empty($item->outcomeid)) {
            throw new \invalid_parameter_exception('Use an assessment item, not a category, total or outcome');
        }
        $authority=$context;$cm=null;
        if ($item->itemtype==='mod') {
            if (empty($item->itemmodule) || empty($item->iteminstance)) {
                throw new \invalid_parameter_exception('Invalid assessment module identity');
            }
            $cm=get_coursemodule_from_instance($item->itemmodule,$item->iteminstance,$courseid,false,MUST_EXIST);
            $info=get_fast_modinfo($course,$USER->id)->get_cm($cm->id);
            if (!$info->uservisible) throw new \invalid_parameter_exception('Assessment is no longer visible');
            $authority=\context_module::instance($cm->id);
            self::validate_context($authority);
            require_capability('moodle/grade:viewall',$authority);
            require_capability('moodle/grade:viewhidden',$authority);
        }
        $allgroups=has_capability('moodle/site:accessallgroups',$authority);
        if ($groupid) {
            $DB->get_record('groups',['id'=>$groupid,'courseid'=>$courseid],'id',MUST_EXIST);
            if ((!$allgroups && !groups_is_member($groupid,$USER->id)) ||
                    ($cm && $cm->groupingid && !$DB->record_exists('groupings_groups',
                        ['groupingid'=>$cm->groupingid,'groupid'=>$groupid]))) {
                throw new \invalid_parameter_exception('Group is outside assessment scope');
            }
        } else if (!$allgroups && (groups_get_course_groupmode($course)==SEPARATEGROUPS ||
                ($cm && groups_get_activity_groupmode($cm,$course)==SEPARATEGROUPS))) {
            throw new \required_capability_exception($authority,'moodle/site:accessallgroups','nopermissions','');
        }
        return ['authorized'=>true,'courseid'=>$courseid,'gradeitemid'=>$gradeitemid,'groupid'=>$groupid];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL,'Current permission only'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'gradeitemid'=>new external_value(PARAM_INT,'Assessment grade item ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group'),
        ]);
    }
}
