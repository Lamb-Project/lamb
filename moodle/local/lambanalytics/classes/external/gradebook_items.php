<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Permission-filtered stored item discovery. Never reads grades or regrades. */
class gradebook_items extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group',VALUE_DEFAULT,0),
            'afterid'=>new external_value(PARAM_INT,'Exclusive scanned item cursor',VALUE_DEFAULT,0),
            'throughid'=>new external_value(PARAM_INT,'Original upper item ID',VALUE_DEFAULT,0),
            'limit'=>new external_value(PARAM_INT,'Maximum items scanned, 1 to 100',VALUE_DEFAULT,100),
        ]);
    }

    private static function authorize($courseid,$groupid): void {
        global $DB,$USER;
        $context=\context_course::instance($courseid);
        self::validate_context($context);
        foreach (['moodle/course:enrolreview','moodle/grade:viewall','moodle/grade:viewhidden'] as $cap) {
            require_capability($cap,$context);
        }
        if (!is_enrolled($context,$USER,'',true)) {
            throw new \required_capability_exception($context,'moodle/course:enrolreview','nopermissions','');
        }
        $allgroups=has_capability('moodle/site:accessallgroups',$context);
        if ($groupid) {
            $DB->get_record('groups',['id'=>$groupid,'courseid'=>$courseid],'id',MUST_EXIST);
            if (!$allgroups && !groups_is_member($groupid,$USER->id)) {
                throw new \invalid_parameter_exception('Group is outside course scope');
            }
        } else if (!$allgroups && groups_get_course_groupmode(get_course($courseid))==SEPARATEGROUPS) {
            throw new \required_capability_exception($context,'moodle/site:accessallgroups','nopermissions','');
        }
    }

    public static function execute($courseid,$groupid=0,$afterid=0,$throughid=0,$limit=100): array {
        global $DB;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','groupid','afterid','throughid','limit'));
        extract($p,EXTR_OVERWRITE);
        if ($courseid<1 || $groupid<0 || $afterid<0 || $throughid<0 || $limit<1 || $limit>100 || ($afterid && !$throughid)) {
            throw new \invalid_parameter_exception('Use a bounded item page and original upper ID');
        }
        self::authorize($courseid,$groupid);
        $where="courseid=:courseid AND itemtype IN ('mod','manual') AND (outcomeid IS NULL OR outcomeid=0)";
        $params=['courseid'=>$courseid];
        if (!$throughid) $throughid=(int)$DB->get_field_sql('SELECT MAX(id) FROM {grade_items} WHERE '.$where,$params);
        if ($afterid>$throughid) throw new \invalid_parameter_exception('Item cursor exceeds upper ID');
        $params+=['afterid'=>$afterid,'throughid'=>$throughid];
        $records=array_values($DB->get_records_sql('SELECT id,itemname,itemtype,itemmodule,iteminstance,itemnumber,gradetype,needsupdate '
            .'FROM {grade_items} WHERE '.$where.' AND id>:afterid AND id<=:throughid ORDER BY id ASC',$params,0,$limit+1));
        $more=count($records)>$limit;$records=array_slice($records,0,$limit);
        $rows=[];$last=$afterid;
        foreach ($records as $item) {
            $last=(int)$item->id;
            try {
                gradebook_scope::execute($courseid,$last,$groupid);
            } catch (\required_capability_exception | \invalid_parameter_exception | \dml_missing_record_exception $e) {
                // Do not leak names or metadata for hidden/revoked/deleted items.
                // Advance over scanned IDs even when no authorized row is returned.
                continue;
            }
            $rows[]=['gradeitemid'=>$last,
                'name'=>\core_text::substr(trim(strip_tags((string)$item->itemname)),0,160),
                'itemtype'=>$item->itemtype,'itemmodule'=>$item->itemmodule,
                'iteminstance'=>$item->iteminstance===null ? null : (int)$item->iteminstance,
                'itemnumber'=>$item->itemnumber===null ? null : (int)$item->itemnumber,
                'gradetype'=>(int)$item->gradetype,'needsupdate'=>(int)$item->needsupdate];
        }
        self::authorize($courseid,$groupid);
        foreach ($rows as $row) gradebook_scope::execute($courseid,$row['gradeitemid'],$groupid);
        return ['schema_version'=>1,'courseid'=>$courseid,'groupid'=>$groupid,'throughid'=>$throughid,
            'next_afterid'=>$last,'has_more'=>$more,'items'=>$rows,'collected_at'=>time(),
            'source'=>'stored_grade_items','atomic_snapshot'=>false];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'schema_version'=>new external_value(PARAM_INT,'Schema version'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group'),
            'throughid'=>new external_value(PARAM_INT,'Upper scanned item ID'),
            'next_afterid'=>new external_value(PARAM_INT,'Last scanned ID, possibly not returned'),
            'has_more'=>new external_value(PARAM_BOOL,'More candidates below upper ID, not an authorized total'),
            'items'=>new external_multiple_structure(new external_single_structure([
                'gradeitemid'=>new external_value(PARAM_INT,'Gradebook item ID, not module instance ID'),
                'name'=>new external_value(PARAM_TEXT,'Stored item label; may be empty'),
                'itemtype'=>new external_value(PARAM_ALPHA,'Manual or module'),
                'itemmodule'=>new external_value(PARAM_PLUGIN,'Module type',VALUE_REQUIRED,null,NULL_ALLOWED),
                'iteminstance'=>new external_value(PARAM_INT,'Module instance ID',VALUE_REQUIRED,null,NULL_ALLOWED),
                'itemnumber'=>new external_value(PARAM_INT,'Grade component number',VALUE_REQUIRED,null,NULL_ALLOWED),
                'gradetype'=>new external_value(PARAM_INT,'Stored grade type; numeric is 1'),
                'needsupdate'=>new external_value(PARAM_INT,'Cached grades may be stale; no recalculation'),
            ])),
            'collected_at'=>new external_value(PARAM_INT,'Observation time'),
            'source'=>new external_value(PARAM_ALPHANUMEXT,'Stored metadata source'),
            'atomic_snapshot'=>new external_value(PARAM_BOOL,'False; IDs do not freeze metadata or permissions'),
        ]);
    }
}
