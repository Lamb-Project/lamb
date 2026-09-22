<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Permission-only authorization of a course-wide completion snapshot. */
class completion_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'cmids'=>new external_multiple_structure(new external_value(PARAM_INT, 'Activity module ID'), 'Exact saved activities', VALUE_DEFAULT, []),
        ]);
    }

    public static function execute($courseid, $cmids = []): array {
        global $USER;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','cmids'));
        extract($p,EXTR_OVERWRITE);
        if($courseid<1 || count($cmids)>100 || count(array_unique($cmids))!=count($cmids)) {
            throw new \invalid_parameter_exception('Invalid completion evidence scope');
        }
        $context=\context_course::instance($courseid);
        self::validate_context($context);
        require_capability('report/progress:view',$context);
        require_capability('moodle/course:enrolreview',$context);
        if(!is_enrolled($context,$USER,'',true)) {
            throw new \required_capability_exception($context,'report/progress:view','nopermissions','');
        }
        $course=get_course($courseid);
        if(groups_get_course_groupmode($course)==SEPARATEGROUPS && !has_capability('moodle/site:accessallgroups',$context)) {
            throw new \required_capability_exception($context,'moodle/site:accessallgroups','nopermissions','');
        }
        $info=get_fast_modinfo($course,$USER->id);
        foreach($cmids as $cmid) {
            if($cmid<1 || !isset($info->cms[$cmid]) || !$info->cms[$cmid]->uservisible) {
                throw new \invalid_parameter_exception('Saved activity is no longer accessible');
            }
            $cm=$info->cms[$cmid];
            $modulecontext=\context_module::instance($cmid);
            self::validate_context($modulecontext);
            require_capability('report/progress:view',$modulecontext);
            if(groups_get_activity_groupmode($cm,$course)==SEPARATEGROUPS &&
                    !has_capability('moodle/site:accessallgroups',$modulecontext)) {
                throw new \required_capability_exception($modulecontext,'moodle/site:accessallgroups','nopermissions','');
            }
        }
        return ['authorized'=>true,'courseid'=>$courseid,'cmids'=>$cmids];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL,'Current permission only'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'cmids'=>new external_multiple_structure(new external_value(PARAM_INT,'Activity module ID')),
        ]);
    }
}
