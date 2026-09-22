<?php
// SPDX-License-Identifier: GPL-3.0-or-later
defined('MOODLE_INTERNAL') || die();
$functions = [
    'local_lambanalytics_resource_events' => [
        'classname' => 'local_lambanalytics\external\resource_events',
        'methodname' => 'execute',
        'description' => 'Read a bounded permission-scoped page of recorded course/resource views.',
        'type' => 'read',
        'capabilities' => 'report/log:view',
        'services' => [MOODLE_OFFICIAL_MOBILE_SERVICE],
    ],
];
