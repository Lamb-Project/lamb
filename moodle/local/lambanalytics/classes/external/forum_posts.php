<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace local_lambanalytics\external;
defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/** Bounded public post metadata with stored, not display-adjusted, timestamps. */
class forum_posts extends external_api {
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'forumid'=>new external_value(PARAM_INT,'Forum ID'),
            'discussionid'=>new external_value(PARAM_INT,'Discussion ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group',VALUE_DEFAULT,0),
            'afterid'=>new external_value(PARAM_INT,'Exclusive post ID cursor',VALUE_DEFAULT,0),
            'throughid'=>new external_value(PARAM_INT,'Original upper post ID',VALUE_DEFAULT,0),
            'limit'=>new external_value(PARAM_INT,'Page size, 1 to 200',VALUE_DEFAULT,200),
        ]);
    }

    public static function execute($courseid,$forumid,$discussionid,$groupid=0,$afterid=0,$throughid=0,$limit=200): array {
        global $DB, $USER, $CFG;
        require_once($CFG->dirroot.'/mod/forum/lib.php');
        $p=self::validate_parameters(self::execute_parameters(),compact('courseid','forumid','discussionid','groupid','afterid','throughid','limit'));
        extract($p, EXTR_OVERWRITE);
        if ($discussionid<1 || $afterid<0 || $throughid<0 || $limit<1 || $limit>200 || ($afterid && !$throughid)) {
            throw new \invalid_parameter_exception('Use a bounded post page and original upper ID');
        }
        forum_scope::execute($courseid,$forumid,$discussionid,$groupid);
        $forum=$DB->get_record('forum',['id'=>$forumid,'course'=>$courseid],'id,course,type',MUST_EXIST);
        $discussion=$DB->get_record('forum_discussions',['id'=>$discussionid,'forum'=>$forumid,'course'=>$courseid],
            'id,course,forum,groupid,timestart,timeend,userid,firstpost',MUST_EXIST);
        $cm=get_coursemodule_from_instance('forum',$forumid,$courseid,false,MUST_EXIST);
        $context=\context_module::instance($cm->id);
        // Without this capability Q&A visibility depends on individual posting
        // history and edit windows. Do not expose hidden-post cursor metadata.
        if ($forum->type==='qanda') require_capability('mod/forum:viewqandawithoutposting',$context);
        $params=['discussionid'=>$discussionid];
        // Private and deleted posts are outside this public-participation source.
        // Neither their identities nor their counts contribute to pagination.
        $where='discussion = :discussionid AND deleted = 0 AND privatereplyto = 0';
        if (!$throughid) {
            $throughid=(int)$DB->get_field_sql('SELECT MAX(id) FROM {forum_posts} WHERE '.$where,$params);
        }
        if ($afterid>$throughid) throw new \invalid_parameter_exception('Post cursor exceeds upper ID');
        $params+=['afterid'=>$afterid,'throughid'=>$throughid];
        $records=array_values($DB->get_records_select('forum_posts',
            $where.' AND id > :afterid AND id <= :throughid',$params,'id ASC',
            'id,discussion,parent,userid,created,modified,deleted,privatereplyto',0,$limit+1));
        $more=count($records)>$limit;
        $records=array_slice($records,0,$limit);$rows=[];$lastid=$afterid;
        foreach ($records as $post) {
            if (!forum_user_can_see_post($forum,$discussion,$post,$USER,$cm,true)) {
                throw new \required_capability_exception($context,'mod/forum:viewdiscussion','nopermissions','');
            }
            if ($post->parent) {
                $parent=$DB->get_record('forum_posts', ['id'=>$post->parent,'discussion'=>$discussionid,
                    'deleted'=>0,'privatereplyto'=>0], 'id,discussion,parent,userid,created,modified,deleted,privatereplyto');
                if (!$parent || !forum_user_can_see_post($forum,$discussion,$parent,$USER,$cm,true)) {
                    // A parent pointer must not disclose a hidden/private identity.
                    throw new \invalid_parameter_exception('Public post ancestry is unavailable');
                }
            }
            $lastid=(int)$post->id;
            $rows[]=['id'=>$lastid,'parent_id'=>$post->parent ? (int)$post->parent : null,
                'author_id'=>(int)$post->userid,'created'=>(int)$post->created,'modified'=>(int)$post->modified];
        }
        forum_scope::execute($courseid,$forumid,$discussionid,$groupid);
        // Recheck the extra Q&A gate at response time as well.
        if ($forum->type==='qanda') require_capability('mod/forum:viewqandawithoutposting',$context);
        return ['schema_version'=>1,'courseid'=>$courseid,'forumid'=>$forumid,
            'discussionid'=>$discussionid,'groupid'=>$groupid,'throughid'=>$throughid,
            'next_afterid'=>$lastid,'has_more'=>$more,'posts'=>$rows,
            'collected_at'=>time(),'atomic_snapshot'=>false,'source'=>'forum_posts',
            'timestamp_basis'=>'stored_creation','population'=>'visible_public_nondeleted_posts',
            'limitations'=>'Private and deleted posts are excluded without exposing their counts. '
                .'No replies means no observed public replies, not unresolved. '
                .'Upper ID excludes later posts but does not freeze edits, deletions or permission changes.'];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'schema_version'=>new external_value(PARAM_INT,'Schema version'),
            'courseid'=>new external_value(PARAM_INT,'Course ID'),
            'forumid'=>new external_value(PARAM_INT,'Forum ID'),
            'discussionid'=>new external_value(PARAM_INT,'Discussion ID'),
            'groupid'=>new external_value(PARAM_INT,'Population group'),
            'throughid'=>new external_value(PARAM_INT,'Upper public post ID'),
            'next_afterid'=>new external_value(PARAM_INT,'Last returned public post ID'),
            'has_more'=>new external_value(PARAM_BOOL,'More public posts below upper ID'),
            'posts'=>new external_multiple_structure(new external_single_structure([
                'id'=>new external_value(PARAM_INT,'Post ID'),
                'parent_id'=>new external_value(PARAM_INT,'Parent; null for root',VALUE_REQUIRED,null,NULL_ALLOWED),
                'author_id'=>new external_value(PARAM_INT,'Private population join ID'),
                'created'=>new external_value(PARAM_INT,'Stored creation timestamp'),
                'modified'=>new external_value(PARAM_INT,'Stored modification timestamp'),
            ])),
            'collected_at'=>new external_value(PARAM_INT,'Page collection timestamp'),
            'atomic_snapshot'=>new external_value(PARAM_BOOL,'False: concurrent changes possible'),
            'source'=>new external_value(PARAM_ALPHANUMEXT,'Fixed source'),
            'timestamp_basis'=>new external_value(PARAM_ALPHANUMEXT,'Stored creation, not release time'),
            'population'=>new external_value(PARAM_ALPHANUMEXT,'Fixed public-only population'),
            'limitations'=>new external_value(PARAM_TEXT,'Evidence limits'),
        ]);
    }
}
