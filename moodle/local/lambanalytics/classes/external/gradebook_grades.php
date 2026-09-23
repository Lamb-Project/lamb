<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Stored gradebook evidence only. No grade API, report, event or recalculation. */
class gradebook_grades extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'gradeitemid'=>new external_value(PARAM_INT,'Assessment grade item ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group',VALUE_DEFAULT,0),
            'afterid'=>new external_value(PARAM_INT,'Exclusive grade record cursor',VALUE_DEFAULT,0),
            'throughid'=>new external_value(PARAM_INT,'Original upper grade record ID',VALUE_DEFAULT,0),
            'limit'=>new external_value(PARAM_INT,'Page size, 1 to 200',VALUE_DEFAULT,200),
        ]);
    }

    private static function item($courseid,$gradeitemid) {
        global $DB;
        return $DB->get_record('grade_items',['id'=>$gradeitemid,'courseid'=>$courseid],
            'id,courseid,itemtype,itemmodule,iteminstance,itemnumber,gradetype,grademin,grademax,gradepass,scaleid,'
            .'hidden,locked,locktime,needsupdate,calculation,multfactor,plusfactor,timecreated,timemodified',MUST_EXIST);
    }

    public static function execute($courseid,$gradeitemid,$groupid=0,$afterid=0,$throughid=0,$limit=200): array {
        global $DB;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','gradeitemid','groupid','afterid','throughid','limit'));
        extract($p,EXTR_OVERWRITE);
        if ($afterid<0 || $throughid<0 || $limit<1 || $limit>200 || ($afterid && !$throughid)) {
            throw new \invalid_parameter_exception('Use a bounded grade page and original upper ID');
        }
        gradebook_scope::execute($courseid,$gradeitemid,$groupid);
        $item=self::item($courseid,$gradeitemid);
        $fingerprint=hash('sha256',json_encode($item));
        $params=['itemid'=>$gradeitemid];
        $where='g.itemid = :itemid';
        if ($groupid) {
            $where.=' AND EXISTS (SELECT 1 FROM {groups_members} gm WHERE gm.userid=g.userid AND gm.groupid=:groupid)';
            $params['groupid']=$groupid;
        }
        if (!$throughid) {
            $throughid=(int)$DB->get_field_sql('SELECT MAX(g.id) FROM {grade_grades} g WHERE '.$where,$params);
        }
        if ($afterid>$throughid) throw new \invalid_parameter_exception('Grade cursor exceeds upper ID');
        $params+=['afterid'=>$afterid,'throughid'=>$throughid];
        $records=array_values($DB->get_records_sql('SELECT g.id,g.userid,g.rawgrade,g.rawgrademin,g.rawgrademax,'
            .'g.rawscaleid,g.finalgrade,g.hidden,g.locked,g.locktime,g.overridden,g.excluded,g.timecreated,g.timemodified '
            .'FROM {grade_grades} g WHERE '.$where.' AND g.id>:afterid AND g.id<=:throughid ORDER BY g.id ASC',
            $params,0,$limit+1));
        $more=count($records)>$limit;$records=array_slice($records,0,$limit);
        $rows=[];$last=$afterid;
        foreach ($records as $record) {
            $row=[];
            foreach (['id','userid','rawscaleid','hidden','locked','locktime','overridden','excluded','timecreated','timemodified'] as $key) {
                $row[$key]=$record->$key===null ? null : (int)$record->$key;
            }
            foreach (['rawgrade','rawgrademin','rawgrademax','finalgrade'] as $key) {
                $row[$key]=$record->$key===null ? null : (string)$record->$key;
            }
            $rows[]=$row;$last=$row['id'];
        }
        gradebook_scope::execute($courseid,$gradeitemid,$groupid);
        if ($fingerprint!==hash('sha256',json_encode(self::item($courseid,$gradeitemid)))) {
            throw new \invalid_parameter_exception('Grade item changed during collection');
        }
        $metadata=[];
        foreach (['id','gradetype','scaleid','hidden','locked','locktime','needsupdate','iteminstance','itemnumber','timecreated','timemodified'] as $key) {
            $metadata[$key]=$item->$key===null ? null : (int)$item->$key;
        }
        foreach (['grademin','grademax','gradepass','multfactor','plusfactor'] as $key) {
            $metadata[$key]=$item->$key===null ? null : (string)$item->$key;
        }
        $metadata['itemtype']=$item->itemtype;$metadata['itemmodule']=$item->itemmodule;
        $metadata['has_calculation']=!empty($item->calculation);
        return ['schema_version'=>1,'courseid'=>$courseid,'gradeitemid'=>$gradeitemid,'groupid'=>$groupid,
            'throughid'=>$throughid,'next_afterid'=>$last,'has_more'=>$more,'grades'=>$rows,
            'item'=>$metadata,'item_fingerprint'=>$fingerprint,'collected_at'=>time(),
            'atomic_snapshot'=>false,'source'=>'stored_grade_items_and_grade_grades',
            'limitations'=>'Stored raw and cached final grades are distinct. No recalculation was requested. '
                .'needsupdate marks potentially stale final values. No record or null grade is not zero. '
                .'Records are not an enrolment or submission denominator. Hidden, locked, overridden and excluded fields retain stored flags/timestamps. '
                .'Upper ID does not freeze edits, deletion, group membership or permissions. Item fingerprint must remain stable across pages. '
                .'Grade modification time is not first grading, feedback release or submission time.'];
    }

    public static function execute_returns(): external_single_structure {
        $nullableint=fn($description)=>new external_value(PARAM_INT,$description,VALUE_REQUIRED,null,NULL_ALLOWED);
        $decimal=fn($description)=>new external_value(PARAM_RAW,$description.' (stored decimal string)',VALUE_REQUIRED,null,NULL_ALLOWED);
        $row=[];
        foreach (['id','userid','rawscaleid','hidden','locked','locktime','overridden','excluded','timecreated','timemodified'] as $key) {
            $row[$key]=$nullableint($key);
        }
        foreach (['rawgrade','rawgrademin','rawgrademax','finalgrade'] as $key) $row[$key]=$decimal($key);
        $item=[];
        foreach (['id','gradetype','scaleid','hidden','locked','locktime','needsupdate','iteminstance','itemnumber','timecreated','timemodified'] as $key) {
            $item[$key]=$nullableint($key);
        }
        foreach (['grademin','grademax','gradepass','multfactor','plusfactor'] as $key) $item[$key]=$decimal($key);
        $item['itemtype']=new external_value(PARAM_ALPHA,'Grade item type');
        $item['itemmodule']=new external_value(PARAM_PLUGIN,'Module or null',VALUE_REQUIRED,null,NULL_ALLOWED);
        $item['has_calculation']=new external_value(PARAM_BOOL,'Stored calculation exists, not its formula');
        return new external_single_structure([
            'schema_version'=>new external_value(PARAM_INT,'Schema version'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'gradeitemid'=>new external_value(PARAM_INT,'Assessment grade item ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group'),
            'throughid'=>new external_value(PARAM_INT,'Upper grade record ID'),
            'next_afterid'=>new external_value(PARAM_INT,'Last returned record ID'),
            'has_more'=>new external_value(PARAM_BOOL,'More records below upper ID'),
            'grades'=>new external_multiple_structure(new external_single_structure($row)),
            'item'=>new external_single_structure($item),
            'item_fingerprint'=>new external_value(PARAM_ALPHANUM,'Item consistency hash'),
            'collected_at'=>new external_value(PARAM_INT,'Observation timestamp'),
            'atomic_snapshot'=>new external_value(PARAM_BOOL,'False; concurrent changes possible'),
            'source'=>new external_value(PARAM_ALPHANUMEXT,'Fixed stored source'),
            'limitations'=>new external_value(PARAM_TEXT,'Evidence limits'),
        ]);
    }
}
