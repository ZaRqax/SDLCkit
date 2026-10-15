"""Configuration precedence, path security and exact recipe validation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from sdlc.config import (apply_profile, explain_config, load_config, load_for_target,
                         load_workflow, merge_config, read_document, validate_config, validate_workflow)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / '.sdlc/workspace.json'
        self.config.parent.mkdir()
        self.project = self.root / 'python-api'
        self.project.mkdir()
        self.write(self.config, {'schema_version': 2, 'workspace': {'name': 'sample', 'root': '.',
                    'projects': [{'id': 'api', 'path': 'python-api'}]}})

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_prompt_only_defaults_are_neutral_and_independent(self):
        result = load_config(self.config)
        self.assertEqual(result['agent']['model'], 'inherit')
        self.assertEqual(result['delivery']['default'], 'working_tree')
        self.assertFalse(result['parallelism']['enabled'])
        self.assertEqual(result['requirements']['enabled'], ['prompt', 'local_files'])
        self.assertTrue(all(not values.get('enabled', False) for name, values in result['integrations'].items()
                            if name != 'custom_mcp'))

    def test_json_workspace_local_project_precedence_and_provenance(self):
        self.write(self.config.parent / 'local.json', {'policy': {'deny': ['push']},
                    'delivery': {'default': 'patch'}})
        self.write(self.project / '.sdlc/project.json', {'schema_version': 2, 'project': {
            'id': 'api', 'commands': {'test': ['python3 -m unittest']},
            'policy': {'deny': ['comment'], 'external_write': 'forbidden'}}})
        report = explain_config(self.config, 'api')
        result = report['effective']
        self.assertEqual(result['workspace']['root'], str(self.root))
        self.assertEqual(result['workspace']['projects'][0]['path'], str(self.project))
        self.assertEqual(result['delivery']['default'], 'patch')
        self.assertEqual(result['policy']['deny'], ['push', 'comment'])
        self.assertEqual(result['project']['commands']['test'], ['python3 -m unittest'])
        self.assertEqual(result['policy']['external_write'], 'forbidden')
        self.assertTrue(report['provenance']['delivery.default'].endswith('local.json'))
        self.assertTrue(report['sources'][-1].endswith('project.json'))

    def test_explicit_local_target_loads_its_policy_without_workspace(self):
        standalone = self.root / 'standalone'
        standalone.mkdir()
        self.write(standalone / '.sdlc/project.yaml', {'schema_version': 2, 'project': {
            'id': 'single', 'policy': {'external_write': 'forbidden'}}})
        # Existing parent allowlist still applies; this target remains inside it.
        result = load_for_target(standalone)
        self.assertEqual(result['policy']['external_write'], 'forbidden')
        self.assertEqual(result['project']['path'], str(standalone))

    def test_path_escape_and_symlink_escape_are_rejected(self):
        outside = self.root.parent / ('outside-' + self.root.name)
        self.write(self.config, {'schema_version': 2, 'workspace': {'root': '.',
                   'projects': [{'id': 'bad', 'path': str(outside)}]}})
        with self.assertRaisesRegex(ValueError, 'escapes'):
            load_config(self.config)
        symlink = self.root / 'link'
        symlink.symlink_to(self.root.parent)
        self.write(self.config, {'workspace': {'projects': [{'id': 'bad', 'path': 'link'}]}})
        with self.assertRaisesRegex(ValueError, 'escapes'):
            load_config(self.config)

    def test_explicit_workspace_allowlist_permits_external_repo(self):
        self.write(self.config, {'workspace': {'root': '.', 'allowed_paths': [str(self.root.parent)],
                    'projects': [{'id': 'external', 'path': str(self.root.parent)}]}})
        self.assertEqual(load_config(self.config)['workspace']['projects'][0]['path'], str(self.root.parent))

    def test_unsafe_schema_values_unknown_keys_and_duplicate_yaml_fail(self):
        baseline = load_config(self.config)
        for section, key, value in [('parallelism', 'max_workers', 0), ('agent', 'model', 23),
                                    ('delivery', 'never_auto_merge', False),
                                    ('policy', 'external_write', 'allow')]:
            with self.subTest(section=section, key=key):
                result = copy.deepcopy(baseline)
                result[section][key] = value
                with self.assertRaises(ValueError):
                    validate_config(result)
        result = copy.deepcopy(baseline)
        result['typo'] = True
        with self.assertRaises(ValueError):
            validate_config(result)
        path = self.root / 'duplicate.yaml'
        path.write_text('schema_version: 2\nschema_version: 9\n')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            read_document(path)

    def test_local_override_cannot_expand_workspace_authority(self):
        local = self.config.parent / 'local.json'
        for override in ({'root': str(self.root.parent)}, {'allowed_paths': [str(self.root.parent)]}):
            self.write(local, {'workspace': override})
            with self.assertRaisesRegex(ValueError, 'local overrides cannot'):
                load_config(self.config)
        self.write(local, {'roles': [{'id': 'reviewer', 'enabled': True},
                                     {'id': 'reviewer', 'enabled': False}]})
        with self.assertRaisesRegex(ValueError, 'unique'):
            load_config(self.config)

    def test_policy_merge_cannot_weaken_or_drop_denies(self):
        with self.assertRaisesRegex(ValueError, 'cannot weaken'):
            merge_config({'policy': {'external_write': 'forbidden'}},
                         {'policy': {'external_write': 'approval_required'}})
        self.assertEqual(merge_config({'policy': {'deny': ['push']}},
                                     {'policy': {'deny': []}})['policy']['deny'], ['push'])
        merged = merge_config({'roles': [{'id': 'reviewer', 'enabled': True, 'model': 'inherit'}]},
                              {'roles': [{'id': 'reviewer', 'enabled': False}]})
        self.assertEqual(merged['roles'], [{'id': 'reviewer', 'enabled': False, 'model': 'inherit'}])

    def test_invalid_project_dependency_cycle_and_delivery_contradiction(self):
        baseline = load_config(self.config)
        baseline['workspace']['projects'] = [
            {'id': 'a', 'path': 'a', 'relationship': {'depends_on': ['b']}},
            {'id': 'b', 'path': 'b', 'relationship': {'depends_on': ['a']}}]
        with self.assertRaisesRegex(ValueError, 'cycle'):
            validate_config(baseline)
        baseline['workspace']['projects'] = []
        baseline['delivery']['allowed'] = ['patch']
        with self.assertRaisesRegex(ValueError, 'delivery.default'):
            validate_config(baseline)

    def test_go_profile_is_optional_and_preserves_project_command(self):
        config = load_config(self.config, 'api')
        config['project']['commands'] = {'test': ['go test ./pkg/...']}
        generic = apply_profile(config, 'generic')
        self.assertNotIn('profiles', generic)
        go = apply_profile(config, 'go')
        self.assertEqual(go['project']['commands']['test'], ['go test ./pkg/...'])
        self.assertIn('**/*.pb.go', go['project']['generated_paths'])
        self.assertEqual(go['profiles'], ['go'])

    def test_workflow_references_cycles_and_expression_injection(self):
        recipe = load_workflow('feature')
        self.assertTrue(all(stage['selected'] for stage in recipe['stages']))
        for mutate, message in [
            (lambda r: r['stages'][0].update(role='invented'), 'unknown role'),
            (lambda r: r['stages'][0].update(needs=['deliver']), 'cycle'),
            (lambda r: r['stages'][0].update(when='__import__("os").system("false")'), 'unsupported')]:
            with self.subTest(message=message):
                changed = copy.deepcopy(recipe)
                mutate(changed)
                with self.assertRaisesRegex(ValueError, message):
                    validate_workflow(changed)

    def test_mcp_credentials_reference_environment_only(self):
        config = load_config(self.config)
        config['integrations']['custom_mcp'] = [{'id': 'example', 'enabled': True,
             'command': ['existing-server'], 'env': {'API_TOKEN': 'plaintext'}}]
        with self.assertRaisesRegex(ValueError, 'environment'):
            validate_config(config)
        config['integrations']['custom_mcp'][0]['env']['API_TOKEN'] = '${EXAMPLE_TOKEN}'
        validate_config(config)


if __name__ == '__main__':
    unittest.main()
