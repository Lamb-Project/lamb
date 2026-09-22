<?php
// SPDX-License-Identifier: GPL-3.0-or-later
defined('MOODLE_INTERNAL') || die();
$functions = [
    'local_lambanalytics_grade_scope' => [
        'classname' => 'local_lambanalytics\external\grade_scope',
        'methodname' => 'execute',
        'description' => 'Revalidate assignment grading and population permissions without reading grades.',
        'type' => 'read',
        'capabilities' => 'mod/assign:grade,moodle/course:enrolreview',
        'services' => [MOODLE_OFFICIAL_MOBILE_SERVICE],
    ],
    'local_lambanalytics_resource_scope' => [
        'classname' => 'local_lambanalytics\external\resource_scope',
        'methodname' => 'execute',
        'description' => 'Revalidate current course, group and resource permissions without querying event evidence.',
        'type' => 'read',
        'capabilities' => 'report/log:view,moodle/course:enrolreview',
        'services' => [MOODLE_OFFICIAL_MOBILE_SERVICE],
    ],
    'local_lambanalytics_resource_events' => [
        'classname' => 'local_lambanalytics\external\resource_events',
        'methodname' => 'execute',
        'description' => 'Read a bounded permission-scoped page of recorded course/resource views.',
        'type' => 'read',
        'capabilities' => 'report/log:view',
        'services' => [MOODLE_OFFICIAL_MOBILE_SERVICE],
    ],
];
