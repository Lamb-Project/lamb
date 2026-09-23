<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_multiple_structure;
use core_external\external_value;

/** Bounded exact saved-discussion authority, without post data. */
class forum_evidence_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'forumid'=>new external_value(PARAM_INT,'Forum ID'),
            'groupid'=>new external_value(PARAM_INT,'Group ID; zero for course-wide',VALUE_DEFAULT,0),
            'discussionids'=>new external_multiple_structure(
                new external_value(PARAM_INT,'Exact saved discussion ID'), 'Up to 100 IDs',VALUE_DEFAULT,[]),
        ]);
    }

    public static function execute($courseid,$forumid,$groupid=0,$discussionids=[]): array {
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','forumid','groupid','discussionids'));
        extract($p,EXTR_OVERWRITE);
        if (count($discussionids)>100 || count(array_unique($discussionids))!==count($discussionids)) {
            throw new \invalid_parameter_exception('Invalid saved discussion scope');
        }
        foreach ($discussionids as $id) {
            if ($id<1) throw new \invalid_parameter_exception('Invalid saved discussion ID');
        }
        forum_scope::execute($courseid,$forumid,0,$groupid);
        foreach ($discussionids as $id) forum_scope::execute($courseid,$forumid,$id,$groupid);
        forum_scope::execute($courseid,$forumid,0,$groupid);
        return ['authorized'=>true,'courseid'=>$courseid,'forumid'=>$forumid,
            'groupid'=>$groupid,'discussionids'=>$discussionids];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL,'Current permission only'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'forumid'=>new external_value(PARAM_INT,'Forum ID'),
            'groupid'=>new external_value(PARAM_INT,'Group ID'),
            'discussionids'=>new external_multiple_structure(new external_value(PARAM_INT,'Authorized discussion ID')),
        ]);
    }
}
