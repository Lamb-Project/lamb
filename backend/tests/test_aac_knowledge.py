"""Role scoping, registry provenance and pack-prefix lifetime contracts."""
import copy
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
from lamb.aac.brief import role_axes, session_brief, render_brief, processor_registry, capability_map
from lamb.aac.pack_loader import load_pack, allowed_skills, allowed_commands, render_prefix, Pack
from lamb.aac.session_guidance import refresh_guidance, POLICY_VERSION
from lamb.aac.liteshell.shell import LiteShell
from tests.aac_knowledge_fixtures import CAPABILITIES

# Independent expected role matrix, including the additive sixth combination.
ROLE_FIXTURES = [
    ('creator', False, False, 'none', ['creator']),
    ('lti_creator', False, False, 'none', ['creator', 'lti']),
    ('creator', True, False, 'org_admin', ['creator', 'org_admin']),
    ('lti_creator', True, False, 'org_admin', ['creator', 'lti', 'org_admin']),
    ('creator', False, True, 'admin', ['creator', 'org_admin', 'admin']),
    ('lti_creator', True, True, 'admin', ['creator', 'lti', 'org_admin', 'admin']),
]


class KnowledgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_restricted_command_is_absent_and_cannot_execute_or_leak_help(self):
        # Exercise the same pack layer contract across reference, menu and dispatch.
        # No current educator command is administrative; a pack can restrict one.
        from lamb.aac.contract import command_reference
        pack = load_pack()
        manifest = copy.deepcopy(pack.manifest)
        manifest['command_layers'] = {'assistant.config': 'org_admin'}
        restricted = Pack(pack.path, manifest, 'role-fixture')
        for layers, permitted in [(['creator'], False),
                                  (['creator', 'lti'], False),
                                  (['creator', 'org_admin'], True),
                                  (['creator', 'org_admin', 'admin'], True)]:
            with self.subTest(layers=layers):
                commands = allowed_commands(restricted, layers)
                self.assertEqual('assistant.config' in commands, permitted)
                self.assertEqual('- lamb assistant config:' in command_reference(commands), permitted)
                shell = LiteShell(server_url='unused', token='fake', user_email='teacher@test', organization_id=4)
                shell.allowed_commands = commands
                self.assertEqual('lamb assistant config' in shell.get_available_commands(), permitted)
                with patch.object(shell, '_get_http', side_effect=AssertionError('must not allocate HTTP')):
                    help_result = await shell.execute('lamb assistant config --help')
                    self.assertEqual(help_result.success, permitted)
                    if not permitted:
                        result = await shell.execute('lamb assistant config')
                        self.assertFalse(result.success)
                        self.assertIn('outside your role', result.error)

    async def test_pending_approval_keeps_old_pack_then_refreshes_on_next_turn_once(self):
        from lamb.aac import router
        auth = self.auth()
        old = load_pack(version='1.0.0')
        brief = session_brief(auth, 'en', CAPABILITIES, {}, old)
        state = {'brief': brief, 'pack_version':old.version, 'pack_hash':old.fingerprint,
                 'policy_version':POLICY_VERSION, 'system_prompt':render_prefix(old, brief), 'active_snapshot':'saved'}
        session = {'id':'fixture', 'skill_info':state, 'pending_action':{'command':'lamb assistant update 7 --description exact'},
                   'conversation':[{'role':'user','content':'Original request'}]}
        with patch.object(router, '_resolve_agent_llm', return_value=(N(), 'fake')), patch.object(router, 'SessionLogger'):
            pending = router._build_agent(auth, session)
            self.assertEqual(pending.pack.version, '1.0.0')
            self.assertEqual(pending.pending_action, session['pending_action'])
            self.assertEqual(pending.system_prompt, state['system_prompt'])
            self.assertEqual(pending.conversation, session['conversation'])
            resumed = dict(session, pending_action=None, skill_info=copy.deepcopy(pending.skill_state))
            updated = router._build_agent(auth, resumed)
            self.assertEqual(updated.pack.version, load_pack().version)
            self.assertNotEqual(updated.system_prompt, state['system_prompt'])
            self.assertEqual(updated.conversation[0], session['conversation'][0])
            self.assertEqual(len(updated.conversation), 2)
            repeated = router._build_agent(auth, dict(resumed, skill_info=copy.deepcopy(updated.skill_state), conversation=copy.deepcopy(updated.conversation)))
            self.assertEqual(repeated.conversation, updated.conversation)
            self.assertEqual(repeated.system_prompt, updated.system_prompt)

    async def test_invalid_pack_does_not_allocate_provider_client(self):
        from lamb.aac import router
        auth = self.auth()
        auth.organization['config'] = {'setups':{'default':{'aac':{'pack_version':'99.0.0'}}}}
        with patch.object(router, '_resolve_agent_llm') as allocate, patch.object(router, 'SessionLogger'):
            with self.assertRaises(ValueError): router._build_agent(auth, {'id':'invalid','skill_info':{'brief':{}}})
            allocate.assert_not_called()

    def auth(self, kind='creator', org_admin=False, system_admin=False):
        return N(user={'id': 7, 'email': 'teacher@test', 'auth_provider': kind},
                 organization={'id': 4, 'name': 'School', 'slug': 'school'},
                 is_org_admin=org_admin, is_system_admin=system_admin)

    async def test_role_axes_and_rendered_prefix_exclude_unassigned_material(self):
        pack = load_pack()
        for kind, org_admin, system_admin, administration, layers in ROLE_FIXTURES:
            with self.subTest(kind=kind, administration=administration):
                auth = self.auth(kind, org_admin, system_admin)
                expected = {'creator_kind': kind, 'administration': administration, 'layers': layers}
                self.assertEqual(role_axes(auth), expected)
                brief = session_brief(auth, 'ca', CAPABILITIES, {'translated_sections': 0, 'total_sections': 86}, pack)
                self.assertEqual({key: brief[key] for key in expected}, expected)
                self.assertEqual(brief['organization'], {'id': 4, 'name': 'School', 'slug': 'school'})
                self.assertEqual(brief['user'], {'id': 7, 'email': 'teacher@test'})
                self.assertNotIn('course', brief)
                self.assertNotIn('activity', brief)
                self.assertEqual(brief['glossary']['language'], 'ca')
                prefix = render_prefix(pack, brief)
                self.assertTrue(prefix.startswith(render_brief(brief)))
                for layer, marker in [('lti', '# LMS-bound creator scope'), ('org_admin', '# Organisation administrator scope'), ('admin', '# System administrator scope')]:
                    self.assertEqual(marker in prefix, layer in layers)
                self.assertEqual('test-lti-tools' in allowed_skills(pack, layers), system_admin)

    async def test_capabilities_equal_loaded_plugins_and_unavailable_kb_is_explicit(self):
        from lamb.completions.main import load_plugins
        registry = processor_registry()
        for category, plugin_type in [('rag_processors', 'rag'), ('prompt_processors', 'pps'), ('connectors', 'connectors')]:
            self.assertEqual({item['id'] for item in registry[category]}, set(load_plugins(plugin_type)))
            for item in registry[category]:
                self.assertTrue(item['description'].strip())
                self.assertNotIn('\n', item['description'])
        with patch('creator_interface.knowledges_router.kb_server_manager.get_ingestion_plugins', AsyncMock(return_value={'plugins': [{'name': 'registered-plugin', 'description': 'Module description'}]})):
            result = await capability_map(self.auth(), [N(path='/mounted', app=N(routes=[N(path='/lti/launch')]))])
        self.assertEqual(result['ingestion_plugins'], {'status': 'available', 'items': [{'id': 'registered-plugin', 'description': 'Module description'}]})
        self.assertTrue(result['lti']['available'])
        with patch('creator_interface.knowledges_router.kb_server_manager.get_ingestion_plugins', AsyncMock(side_effect=OSError('offline'))):
            result = await capability_map(self.auth())
        self.assertEqual(result['ingestion_plugins'], {'status': 'unavailable', 'items': []})
        self.assertFalse(result['lti']['available'])

    async def test_direct_skill_load_enforces_role_and_selected_pack(self):
        pack = load_pack()
        shell = LiteShell(server_url='unused', token='fake', user_email='teacher@test', organization_id=4, user_id=7)
        shell.knowledge = {'pack': pack, 'brief': {'layers': ['creator']}}
        result = await shell.execute('lamb skill list')
        self.assertTrue(result.success, result.error)
        self.assertNotIn('test-lti-tools', [row['id'] for row in result.data])
        result = await shell.execute('lamb skill load test-lti-tools')
        self.assertFalse(result.success)
        self.assertIn('outside your role', result.error)
        shell.knowledge['brief']['layers'] += ['org_admin', 'admin']
        result = await shell.execute('lamb skill load test-lti-tools')
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data['skill_id'], 'test-lti-tools')

    async def test_prefix_is_stable_and_refreshes_once_on_pack_change(self):
        pack = load_pack()
        state = {'ui_language': 'ca', 'brief': session_brief(self.auth(), 'ca', CAPABILITIES, {}, pack)}
        a = N(pack=pack, system_prompt='')
        self.assertIsNone(refresh_guidance(a, state, {}, 'unused'))
        first = copy.deepcopy(state)
        self.assertIsNone(refresh_guidance(a, state, {}, 'unused'))
        self.assertEqual(state, first)
        newer = Pack(pack.path, {**pack.manifest, 'version': '1.1.1'}, 'new-release-hash')
        a.pack = newer
        notice = refresh_guidance(a, state, {}, 'unused')
        self.assertIn('actualitzat', notice)
        self.assertEqual(state['pack_version'], '1.1.1')
        self.assertNotEqual(state['system_prompt'], first['system_prompt'])
        changed = copy.deepcopy(state)
        self.assertIsNone(refresh_guidance(a, state, {}, 'unused'))
        self.assertEqual(state, changed)
        a.pack = Pack(pack.path, newer.manifest, 'tampered')
        with self.assertRaisesRegex(ValueError, 'without a new version'): refresh_guidance(a, state, {}, 'unused')
