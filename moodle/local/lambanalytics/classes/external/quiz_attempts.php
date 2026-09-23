<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Fixed raw attempt fields, never quiz questions, answers, feedback or secrets. */
class quiz_attempts extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'quizid'=>new external_value(PARAM_INT,'Quiz ID'),
            'groupid'=>new external_value(PARAM_INT,'Current group scope',VALUE_DEFAULT,0),
            'afterid'=>new external_value(PARAM_INT,'Exclusive attempt ID cursor',VALUE_DEFAULT,0),
            'throughid'=>new external_value(PARAM_INT,'First-page upper ID; zero establishes it',VALUE_DEFAULT,0),
            'limit'=>new external_value(PARAM_INT,'Page size, 1 to 200',VALUE_DEFAULT,200),
        ]);
    }

    public static function execute($courseid,$quizid,$groupid=0,$afterid=0,$throughid=0,$limit=200): array {
        global $DB;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','quizid','groupid','afterid','throughid','limit'));
        extract($p,EXTR_OVERWRITE);
        if ($afterid<0 || $throughid<0 || $limit<1 || $limit>200 || ($afterid && !$throughid)) {
            throw new \invalid_parameter_exception('Use a bounded attempt page and its original upper ID');
        }
        quiz_scope::execute($courseid,$quizid,$groupid);
        $context=\context_course::instance($courseid);
        [$enrolledsql,$params]=get_enrolled_sql($context,'',$groupid,true);
        $params['quizid']=$quizid;
        // Active enrolment is enforced at the source, independently of any
        // population join done by the client. Preview attempts are retained as
        // explicitly flagged evidence, never silently mistaken for learners.
        $where="quiz = :quizid AND userid IN ($enrolledsql)";
        if (!$throughid) {
            $throughid=(int)$DB->get_field_sql('SELECT MAX(id) FROM {quiz_attempts} WHERE '.$where,$params);
        }
        if ($afterid>$throughid) {
            throw new \invalid_parameter_exception('Attempt cursor exceeds its upper ID');
        }
        $params+=['afterid'=>$afterid,'throughid'=>$throughid];
        $where.=' AND id > :afterid AND id <= :throughid';
        $records=array_values($DB->get_records_select('quiz_attempts',$where,$params,'id ASC',
            'id,quiz,userid,attempt,preview,state,sumgrades,timestart,timefinish,timemodified',0,$limit+1));
        $more=count($records)>$limit;
        $records=array_slice($records,0,$limit);$rows=[];$lastid=$afterid;
        foreach ($records as $row) {
            $lastid=(int)$row->id;
            $rows[]=['id'=>$lastid,'quiz'=>(int)$row->quiz,'userid'=>(int)$row->userid,
                'attempt'=>(int)$row->attempt,'preview'=>(bool)$row->preview,'state'=>$row->state,
                'sumgrades'=>$row->sumgrades===null ? null : (float)$row->sumgrades,
                'timestart'=>(int)$row->timestart,'timefinish'=>(int)$row->timefinish,
                'timemodified'=>(int)$row->timemodified];
        }
        $quiz=$DB->get_record('quiz',['id'=>$quizid,'course'=>$courseid],
            'id,sumgrades,grade,grademethod',MUST_EXIST);
        // Revalidate after retrieval as well, without exposing rows on revocation.
        quiz_scope::execute($courseid,$quizid,$groupid);
        return ['schema_version'=>1,'courseid'=>$courseid,'quizid'=>$quizid,'groupid'=>$groupid,
            'throughid'=>$throughid,'next_afterid'=>$lastid,'has_more'=>$more,'attempts'=>$rows,
            'raw_maximum'=>(float)$quiz->sumgrades,'grade_maximum'=>(float)$quiz->grade,
            'grading_method'=>(int)$quiz->grademethod,'collected_at'=>time(),
            'atomic_snapshot'=>false,'source'=>'quiz_attempts',
            'limitations'=>'Current active enrolments and group membership, not historical population. '
                .'The upper ID excludes later attempts but does not freeze edits or regrading of existing attempts. '
                .'Raw marks are not final gradebook marks. Elapsed time is not study time.'];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'schema_version'=>new external_value(PARAM_INT,'Schema version'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'quizid'=>new external_value(PARAM_INT,'Quiz ID'),
            'groupid'=>new external_value(PARAM_INT,'Group ID'),
            'throughid'=>new external_value(PARAM_INT,'Upper attempt ID'),
            'next_afterid'=>new external_value(PARAM_INT,'Last returned attempt ID'),
            'has_more'=>new external_value(PARAM_BOOL,'More attempts below upper ID'),
            'attempts'=>new external_multiple_structure(new external_single_structure([
                'id'=>new external_value(PARAM_INT,'Attempt ID'),
                'quiz'=>new external_value(PARAM_INT,'Quiz ID'),
                'userid'=>new external_value(PARAM_INT,'Private population join ID'),
                'attempt'=>new external_value(PARAM_INT,'Actual attempt number'),
                'preview'=>new external_value(PARAM_BOOL,'Preview attempt'),
                'state'=>new external_value(PARAM_ALPHA,'Attempt state'),
                'sumgrades'=>new external_value(PARAM_FLOAT,'Raw attempt points; null means ungraded',VALUE_REQUIRED,null,NULL_ALLOWED),
                'timestart'=>new external_value(PARAM_INT,'Start timestamp'),
                'timefinish'=>new external_value(PARAM_INT,'Finish timestamp, zero if unfinished'),
                'timemodified'=>new external_value(PARAM_INT,'Last modification timestamp'),
            ])),
            'raw_maximum'=>new external_value(PARAM_FLOAT,'Current raw point maximum'),
            'grade_maximum'=>new external_value(PARAM_FLOAT,'Current quiz grade maximum'),
            'grading_method'=>new external_value(PARAM_INT,'Current Moodle quiz grading method'),
            'collected_at'=>new external_value(PARAM_INT,'This page collection timestamp'),
            'atomic_snapshot'=>new external_value(PARAM_BOOL,'False: updates can occur between pages'),
            'source'=>new external_value(PARAM_ALPHANUMEXT,'Fixed source'),
            'limitations'=>new external_value(PARAM_TEXT,'Evidence limits'),
        ]);
    }
}
