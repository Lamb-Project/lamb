<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Permission-only revalidation for stored analytics; no event or roster query. */
class resource_scope extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'groupid'=>new external_value(PARAM_INT, 'Group scope', VALUE_DEFAULT, 0),
            'cmids'=>new external_multiple_structure(new external_value(PARAM_INT, 'Resource module ID'), 'Saved modules', VALUE_DEFAULT, []),
        ]);
    }

    public static function execute($courseid, $groupid = 0, $cmids = []): array {
        global $DB, $USER;
        $p = self::validate_parameters(self::execute_parameters(), compact('courseid','groupid','cmids'));
        extract($p, EXTR_OVERWRITE);
        if ($courseid < 1 || $groupid < 0 || count($cmids) > 100 || count(array_unique($cmids)) != count($cmids)) {
            throw new \invalid_parameter_exception('Invalid saved resource scope');
        }
        $context = \context_course::instance($courseid);
        self::validate_context($context);
        require_capability('report/log:view', $context);
        require_capability('moodle/course:enrolreview', $context);
        if (!is_enrolled($context, $USER, '', true)) {
            throw new \required_capability_exception($context, 'report/log:view', 'nopermissions', '');
        }
        $course = get_course($courseid);
        $allgroups = has_capability('moodle/site:accessallgroups', $context);
        if ($groupid) {
            $DB->get_record('groups',['id'=>$groupid,'courseid'=>$courseid],'*',MUST_EXIST);
            if (!$allgroups && !groups_is_member($groupid,$USER->id)) {
                throw new \invalid_parameter_exception('Group is outside your current scope');
            }
        } else if (!$allgroups && groups_get_course_groupmode($course) == SEPARATEGROUPS) {
            throw new \invalid_parameter_exception('An authorized group is required');
        }
        $modinfo = get_fast_modinfo($course,$USER->id);
        foreach ($cmids as $cmid) {
            if ($cmid < 1 || !isset($modinfo->cms[$cmid]) || !$modinfo->cms[$cmid]->uservisible) {
                throw new \invalid_parameter_exception('Saved resource is no longer accessible');
            }
            $cm = $modinfo->cms[$cmid];
            if (!in_array($cm->modname,['resource','page','url','folder','book'],true)) {
                throw new \invalid_parameter_exception('Not a supported resource module');
            }
            require_capability('report/log:view', \context_module::instance($cmid));
            if (!$allgroups && !$groupid && groups_get_activity_groupmode($cm,$course) == SEPARATEGROUPS) {
                throw new \invalid_parameter_exception('An authorized activity group is required');
            }
        }
        return ['authorized'=>true,'courseid'=>$courseid,'groupid'=>$groupid,'cmids'=>$cmids];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'authorized'=>new external_value(PARAM_BOOL, 'Current permission only, not a durable grant'),
            'courseid'=>new external_value(PARAM_INT, 'Course ID'),
            'groupid'=>new external_value(PARAM_INT, 'Group ID'),
            'cmids'=>new external_multiple_structure(new external_value(PARAM_INT, 'Module ID')),
        ]);
    }
}
