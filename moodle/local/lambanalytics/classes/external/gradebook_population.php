<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Filter supplied active student candidates by Moodle user-list restrictions. */
class gradebook_population extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'gradeitemid'=>new external_value(PARAM_INT,'Assessment grade item ID'),
            'userids'=>new external_multiple_structure(new external_value(PARAM_INT,'Candidate learner ID')),
            'groupid'=>new external_value(PARAM_INT,'Population group',VALUE_DEFAULT,0),
        ]);
    }

    public static function execute($courseid,$gradeitemid,$userids,$groupid=0): array {
        global $DB, $USER;
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','gradeitemid','userids','groupid'));
        extract($p,EXTR_OVERWRITE);
        if (count($userids)>200 || count(array_unique($userids))!==count($userids) ||
                array_filter($userids,fn($id)=>$id<1)) {
            throw new \invalid_parameter_exception('Use at most 200 distinct positive candidate IDs');
        }
        gradebook_scope::execute($courseid,$gradeitemid,$groupid);
        $context=\context_course::instance($courseid);
        $users=[];
        foreach ($userids as $id) {
            // Caller establishes student roles from the complete current roster.
            // A changed enrolment/group invalidates the batch, not the denominator.
            if (!is_enrolled($context,$id,'',true) || ($groupid && !groups_is_member($groupid,$id))) {
                throw new \invalid_parameter_exception('Candidate population changed or is outside scope');
            }
            $users[$id]=(object)['id'=>$id];
        }
        $item=$DB->get_record('grade_items',['id'=>$gradeitemid,'courseid'=>$courseid],
            'id,itemtype,itemmodule,iteminstance',MUST_EXIST);
        $basis='active_candidate_population_manual_item';
        $filtered=$users;
        if ($item->itemtype==='mod') {
            $cm=get_coursemodule_from_instance($item->itemmodule,$item->iteminstance,$courseid,false,MUST_EXIST);
            $info=get_fast_modinfo($courseid,$USER->id)->get_cm($cm->id);
            $availability=new \core_availability\info_module($info);
            $filtered=$availability->filter_user_list($users);
            $basis='module_and_section_availability_user_list';
        }
        gradebook_scope::execute($courseid,$gradeitemid,$groupid);
        // Repeat membership checks after availability evaluation as well.
        foreach ($userids as $id) {
            if (!is_enrolled($context,$id,'',true) || ($groupid && !groups_is_member($groupid,$id))) {
                throw new \invalid_parameter_exception('Candidate population changed during filtering');
            }
        }
        $included=array_map('intval',array_keys($filtered));sort($included,SORT_NUMERIC);
        $excluded=array_values(array_diff($userids,$included));sort($excluded,SORT_NUMERIC);
        return ['schema_version'=>1,'courseid'=>$courseid,'gradeitemid'=>$gradeitemid,'groupid'=>$groupid,
            'included_userids'=>$included,'excluded_userids'=>$excluded,'population_basis'=>$basis,
            'collected_at'=>time(),'atomic_snapshot'=>false,
            'limitations'=>'Candidate student roles are established by the caller. Moodle user-list availability '
                .'restrictions include module and section targeting but omit temporal conditions such as dates. '
                .'This is not current access, required work, historical eligibility or submission status. '
                .'Hidden activities and module-specific submission capabilities are not eligibility filters. '
                .'Manual items have no activity availability restrictions.'];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'schema_version'=>new external_value(PARAM_INT,'Schema version'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'gradeitemid'=>new external_value(PARAM_INT,'Grade item ID'),
            'groupid'=>new external_value(PARAM_INT,'Group ID'),
            'included_userids'=>new external_multiple_structure(new external_value(PARAM_INT,'Included candidate')),
            'excluded_userids'=>new external_multiple_structure(new external_value(PARAM_INT,'Excluded candidate')),
            'population_basis'=>new external_value(PARAM_ALPHANUMEXT,'Target population basis'),
            'collected_at'=>new external_value(PARAM_INT,'Observation timestamp'),
            'atomic_snapshot'=>new external_value(PARAM_BOOL,'False; concurrent changes possible'),
            'limitations'=>new external_value(PARAM_TEXT,'Population interpretation limits'),
        ]);
    }
}
