<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Fixed course-default schedule fields, never effective learner overrides. */
class default_dates extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Exact course'),
            'cmids'=>new external_multiple_structure(new external_value(PARAM_INT,'Assignment or quiz module ID')),
            'scopeonly'=>new external_value(PARAM_BOOL,'Revalidate without retrieving dates',VALUE_DEFAULT,false),
        ]);
    }

    public static function execute($courseid,$cmids,$scopeonly=false): array {
        global $DB,$USER;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','cmids','scopeonly'));
        extract($p,EXTR_OVERWRITE);
        if($courseid<1 || !count($cmids) || count($cmids)>100 || count(array_unique($cmids))!=count($cmids)) {
            throw new \invalid_parameter_exception('Invalid default-date scope');
        }
        $context=\context_course::instance($courseid);
        self::validate_context($context);
        if(!is_enrolled($context,$USER,'',true)) {
            throw new \required_capability_exception($context,'moodle/course:view','nopermissions','');
        }
        $course=get_course($courseid);
        $info=get_fast_modinfo($course,$USER->id);
        $modules=[];
        foreach($cmids as $cmid) {
            if($cmid<1 || !isset($info->cms[$cmid]) || !$info->cms[$cmid]->uservisible) {
                throw new \invalid_parameter_exception('Activity is outside accessible course scope');
            }
            $cm=$info->cms[$cmid];
            if(!in_array($cm->modname,['assign','quiz'],true)) {
                throw new \invalid_parameter_exception('Unsupported default-date activity');
            }
            $modulecontext=\context_module::instance($cmid);
            self::validate_context($modulecontext);
            require_capability($cm->modname==='assign'?'mod/assign:grade':'mod/quiz:viewreports',$modulecontext);
            $modules[]=$cm;
        }
        $rows=[];
        if(!$scopeonly) {
            foreach($modules as $cm) {
                // Table/field selection is server-owned, never an API parameter.
                if($cm->modname==='assign') {
                    $record=$DB->get_record('assign',['id'=>$cm->instance,'course'=>$courseid],
                        'id,allowsubmissionsfromdate,duedate,cutoffdate',MUST_EXIST);
                    $opens=$record->allowsubmissionsfromdate;$due=$record->duedate;$closes=$record->cutoffdate;
                } else {
                    $record=$DB->get_record('quiz',['id'=>$cm->instance,'course'=>$courseid],
                        'id,timeopen,timeclose',MUST_EXIST);
                    $opens=$record->timeopen;$due=$record->timeclose;$closes=$record->timeclose;
                }
                $rows[]=['cmid'=>$cm->id,'instanceid'=>$record->id,'modname'=>$cm->modname,
                    'opens'=>(int)$opens,'due'=>(int)$due,'closes'=>(int)$closes];
            }
        }
        return ['courseid'=>$courseid,'cmids'=>$cmids,'authorized'=>true,'scopeonly'=>$scopeonly,
            'basis'=>'stored_course_defaults','relative_dates'=>(bool)$course->relativedatesmode,'dates'=>$rows];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'cmids'=>new external_multiple_structure(new external_value(PARAM_INT,'Authorized module ID')),
            'authorized'=>new external_value(PARAM_BOOL,'Current access only'),
            'scopeonly'=>new external_value(PARAM_BOOL,'No date values collected'),
            'basis'=>new external_value(PARAM_ALPHANUMEXT,'Stored defaults, not effective dates'),
            'relative_dates'=>new external_value(PARAM_BOOL,'Course uses relative dates; not a universal learner schedule'),
            'dates'=>new external_multiple_structure(new external_single_structure([
                'cmid'=>new external_value(PARAM_INT,'Module ID'),
                'instanceid'=>new external_value(PARAM_INT,'Activity instance ID'),
                'modname'=>new external_value(PARAM_PLUGIN,'Supported activity type'),
                'opens'=>new external_value(PARAM_INT,'Stored opening timestamp, zero means unset'),
                'due'=>new external_value(PARAM_INT,'Assignment due or quiz close timestamp, zero means unset'),
                'closes'=>new external_value(PARAM_INT,'Assignment cutoff or quiz close timestamp, zero means unset'),
            ])),
        ]);
    }
}
