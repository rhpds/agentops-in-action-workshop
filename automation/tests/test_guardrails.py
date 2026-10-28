"""Check NeMo provisioning and shared inference settings across tenant charts."""
import unittest

import yaml

from test_namespace_consolidation import render, resource


class Guardrails(unittest.TestCase):
    def bootstrap(self, **overrides):
        params = {
            'tenant.username': 'user-test',
            'namespaceSuffix': 'training',
            'secrets.modelApiKey': 'test-only-model-key',
            'secrets.apiServerKey': 'test-only-server-key',
        }
        params.update(overrides)
        return render('bootstrap-tenant', 'user-test-bootstrap', 'openshift-gitops', params)

    def child(self, app):
        source = app['spec']['source']
        return render(source['path'].split('/')[-1], source['helm']['releaseName'],
                      app['spec']['destination']['namespace'],
                      {p['name']: p['value'] for p in source['helm']['parameters']})

    def test_shared_model_and_existing_secret(self):
        base_url = 'https://model.example.test/v1'
        model_name = 'workshop-judge-model'
        bootstrap = self.bootstrap(**{'model.baseUrl': base_url, 'model.model': model_name})
        app = resource(bootstrap, 'Application', 'user-test-guardrails')
        self.assertEqual(app['spec']['destination']['namespace'], 'user-test-training')
        self.assertEqual(app['spec']['syncPolicy']['automated'], {})
        self.assertEqual(app['spec']['source']['repoURL'],
                         resource(bootstrap, 'Application', 'user-test-platform')['spec']['source']['repoURL'])
        docs = self.child(app)
        cr = resource(docs, 'NemoGuardrails', 'nemo-guardrails')
        cm = resource(docs, 'ConfigMap', 'nemo-guardrails-config')
        self.assertEqual(cr['metadata']['namespace'], 'user-test-training')
        self.assertEqual(cr['spec']['nemoConfigs'], [{
            'name': 'northgate', 'default': True, 'configMaps': [cm['metadata']['name']],
        }])
        key_ref = cr['spec']['env'][0]['valueFrom']['secretKeyRef']
        secret = resource(bootstrap, 'Secret', key_ref['name'])
        self.assertIn(key_ref['key'], secret['stringData'])
        self.assertNotIn('test-only-model-key', str(cm['data']))
        config = yaml.safe_load(cm['data']['config.yaml'])
        main = config['models'][0]
        self.assertEqual(main['model'], model_name)
        self.assertEqual(main['parameters']['base_url'], base_url)
        self.assertEqual(main['api_key_env_var'], cr['spec']['env'][0]['name'])
        for direction in ('input', 'output'):
            self.assertEqual(config['rails'][direction]['flows'], [
                f'detect sensitive data on {direction}', f'self check {direction}',
            ])
            detection = config['rails']['config']['sensitive_data_detection'][direction]
            self.assertEqual(detection['entities'], ['EMAIL_ADDRESS', 'PHONE_NUMBER'])
        prompts = yaml.safe_load(cm['data']['prompts.yaml'])['prompts']
        self.assertEqual({p['task'] for p in prompts}, {'self_check_input', 'self_check_output'})
        for prompt in prompts:
            self.assertIn('{{ user_input }}', prompt['content'])
        self.assertIn('{{ bot_response }}', prompts[1]['content'])
        for suffix, expected in [
            ('platform', {'agent.litellm.baseUrl': base_url, 'agent.litellm.model': model_name}),
            ('openshell', {'model.baseUrl': base_url, 'model.model': model_name}),
        ]:
            other = resource(bootstrap, 'Application', f'user-test-{suffix}')
            params = {p['name']: p['value'] for p in other['spec']['source']['helm']['parameters']}
            for name, value in expected.items():
                self.assertEqual(params[name], value)

    def test_pii_can_be_disabled_without_disabling_judge(self):
        docs = render('tenant-guardrails', 'test-guardrails', 'user1-agentops',
                      {'pii.enabled': 'false'})
        cm = resource(docs, 'ConfigMap', 'nemo-guardrails-config')
        rails = yaml.safe_load(cm['data']['config.yaml'])['rails']
        self.assertNotIn('config', rails)
        for direction in ('input', 'output'):
            self.assertEqual(rails[direction]['flows'], [f'self check {direction}'])

    def test_guardrails_opt_out_and_non_hermes_harness(self):
        for overrides in [{'guardrails.enabled': 'false'}, {'platform.agentHarness': 'waterplant'}]:
            with self.subTest(overrides=overrides):
                docs = self.bootstrap(**overrides)
                self.assertIsNone(resource(docs, 'Application', 'user-test-guardrails', required=False))


if __name__ == '__main__':
    unittest.main()
