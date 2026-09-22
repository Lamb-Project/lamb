<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Existing log evidence only: this endpoint never triggers a viewed event. */
class resource_events extends external_api {
    private const EVENTS = [
        '\\core\\event\\course_viewed',
        '\\mod_resource\\event\\course_module_viewed',
        '\\mod_page\\event\\course_module_viewed',
        '\\mod_url\\event\\course_module_viewed',
        '\\mod_folder\\event\\course_module_viewed',
        '\\mod_book\\event\\course_module_viewed',
        '\\mod_book\\event\\chapter_viewed',
    ];

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Authorized enrolled course'),
            'since' => new external_value(PARAM_INT, 'Inclusive Unix timestamp'),
            'until' => new external_value(PARAM_INT, 'Exclusive Unix timestamp, not in the future'),
            'groupid' => new external_value(PARAM_INT, 'Current membership scope; zero means all authorized groups', VALUE_DEFAULT, 0),
            'afterid' => new external_value(PARAM_INT, 'Keyset cursor', VALUE_DEFAULT, 0),
            'throughid' => new external_value(PARAM_INT, 'Upper ID from first page; zero establishes a watermark', VALUE_DEFAULT, 0),
            'limit' => new external_value(PARAM_INT, 'Page size, 1 to 200', VALUE_DEFAULT, 200),
        ]);
    }

    public static function execute($courseid, $since, $until, $groupid = 0, $afterid = 0, $throughid = 0, $limit = 200): array {
        global $DB, $USER;
        $p = self::validate_parameters(self::execute_parameters(), compact(
            'courseid', 'since', 'until', 'groupid', 'afterid', 'throughid', 'limit'));
        extract($p, EXTR_OVERWRITE);
        if ($courseid < 1 || $since < 0 || $until <= $since || $until > time() ||
                $until - $since > 90 * DAYSECS || $afterid < 0 || $throughid < 0 ||
                $groupid < 0 || $limit < 1 || $limit > 200) {
            throw new \invalid_parameter_exception('Use a past window of at most 90 days and a page of at most 200 events');
        }
        $context = \context_course::instance($courseid);
        self::validate_context($context);
        require_capability('report/log:view', $context);
        if (!is_enrolled($context, $USER, '', true)) {
            throw new \required_capability_exception($context, 'report/log:view', 'nopermissions', '');
        }
        $course = get_course($courseid);
        $allgroups = has_capability('moodle/site:accessallgroups', $context);
        if ($groupid) {
            $DB->get_record('groups', ['id'=>$groupid, 'courseid'=>$courseid], '*', MUST_EXIST);
            if (!$allgroups && !groups_is_member($groupid, $USER->id)) {
                throw new \invalid_parameter_exception('Group is outside your scope');
            }
        } else if (groups_get_course_groupmode($course) == SEPARATEGROUPS && !$allgroups) {
            throw new \invalid_parameter_exception('Select an authorized group for this separate-groups course');
        }
        $readers = get_log_manager()->get_readers();
        if (!isset($readers['logstore_standard'])) {
            throw new \invalid_parameter_exception('The standard log reader is unavailable');
        }
        [$insql, $inparams] = $DB->get_in_or_equal(self::EVENTS, SQL_PARAMS_NAMED, 'ev');
        $params = ['course'=>$courseid, 'since'=>$since, 'until'=>$until] + $inparams;
        $where = "courseid = :course AND timecreated >= :since AND timecreated < :until AND eventname $insql AND anonymous = 0 AND userid > 0";
        if ($groupid) {
            $where .= ' AND userid IN (SELECT userid FROM {groups_members} WHERE groupid = :groupid)';
            $params['groupid'] = $groupid;
        }
        if (!$throughid) {
            $throughid = (int)$DB->get_field_sql('SELECT MAX(id) FROM {logstore_standard_log} WHERE '.$where, $params);
        }
        if ($afterid > $throughid) {
            throw new \invalid_parameter_exception('Cursor exceeds the upper event watermark');
        }
        $params += ['afterid'=>$afterid, 'throughid'=>$throughid];
        $where .= ' AND id > :afterid AND id <= :throughid';
        $rows = array_values($DB->get_records_select('logstore_standard_log', $where, $params, 'id ASC',
            'id,eventname,userid,contextlevel,contextinstanceid,objectid,timecreated', 0, $limit + 1));
        $more = count($rows) > $limit;
        $rows = array_slice($rows, 0, $limit);
        $modinfo = get_fast_modinfo($course, $USER->id);
        $events = [];
        $omitted = 0;
        $lastid = $afterid;
        foreach ($rows as $row) {
            $lastid = (int)$row->id;
            $cmid = 0;
            if ((int)$row->contextlevel === CONTEXT_MODULE) {
                $cmid = (int)$row->contextinstanceid;
                if (!isset($modinfo->cms[$cmid]) || !$modinfo->cms[$cmid]->uservisible) {
                    $omitted++;
                    continue;
                }
                $cm = $modinfo->cms[$cmid];
                if (!$allgroups && groups_get_activity_groupmode($cm, $course) == SEPARATEGROUPS && !$groupid) {
                    throw new \invalid_parameter_exception('Select an authorized group for separate-group activities');
                }
            } else if ($row->eventname !== '\\core\\event\\course_viewed') {
                $omitted++;
                continue;
            }
            $events[] = ['id'=>(int)$row->id, 'eventname'=>$row->eventname, 'userid'=>(int)$row->userid,
                'cmid'=>$cmid, 'objectid'=>(int)$row->objectid, 'timecreated'=>(int)$row->timecreated];
        }
        return ['schema_version'=>1, 'courseid'=>$courseid, 'groupid'=>$groupid,
            'since'=>$since, 'until'=>$until, 'throughid'=>$throughid,
            'next_afterid'=>$lastid, 'has_more'=>$more, 'events'=>$events, 'omitted_inaccessible_modules'=>$omitted,
            'source'=>'logstore_standard', 'history_complete'=>false,
            'configured_retention_days'=>(int)get_config('logstore_standard', 'loglifetime'),
            'limitations'=>'Recorded views only, not reading or learning. Group membership and module visibility are current, not historical. Retention configuration does not prove historical completeness.'];
    }

    public static function execute_returns(): external_single_structure {
        $fields = [];
        foreach (['schema_version','courseid','groupid','since','until','throughid','next_afterid','omitted_inaccessible_modules','configured_retention_days'] as $key) {
            $fields[$key] = new external_value(PARAM_INT, $key);
        }
        $fields['has_more'] = new external_value(PARAM_BOOL, 'More rows within the watermark');
        $fields['history_complete'] = new external_value(PARAM_BOOL, 'Historical completeness established');
        $fields['source'] = new external_value(PARAM_TEXT, 'Log source');
        $fields['limitations'] = new external_value(PARAM_TEXT, 'Interpretation and retention limits');
        $fields['events'] = new external_multiple_structure(new external_single_structure([
            'id'=>new external_value(PARAM_INT, 'Log ID'),
            'eventname'=>new external_value(PARAM_RAW, 'Allowlisted event class'),
            'userid'=>new external_value(PARAM_INT, 'Event actor ID, not a learner-role claim'),
            'cmid'=>new external_value(PARAM_INT, 'Course module ID, zero for course views'),
            'objectid'=>new external_value(PARAM_INT, 'Source object ID'),
            'timecreated'=>new external_value(PARAM_INT, 'Event Unix timestamp'),
        ]));
        return new external_single_structure($fields);
    }
}
