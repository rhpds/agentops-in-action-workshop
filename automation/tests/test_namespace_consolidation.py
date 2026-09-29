"""Render complete tenant trees and exercise namespace/RBAC/admission boundaries.

Requires Helm, PyYAML, and CELCHECK pointing to the built celcheck helper.
No cluster credentials or network access are used.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1] / 'gitops'


def render(chart, release, namespace, params):
    cmd = ['helm', 'template', release, str(ROOT / chart), '--namespace', namespace]
    for key, value in params.items():
        cmd += ['--set', f'{key}={value}']
    result = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def resource(docs, kind, name):
    return next(d for d in docs if d['kind'] == kind and d['metadata']['name'] == name)


def tenant(user='user1', suffix='agentops', runtime='openshell', harness='hermes', enforced='false'):
    ns = f'{user}-{suffix}'
    bootstrap = render('bootstrap-tenant', f'{user}-bootstrap', 'openshift-gitops', {
        'tenant.username': user, 'namespaceSuffix': suffix,
        'secrets.modelApiKey': 'test-only', 'secrets.apiServerKey': 'test-only',
        'platform.hermesRuntime': runtime, 'platform.agentHarness': harness,
        'policy.mcpGatewayEnforced': enforced,
    })
    all_docs = list(bootstrap)
    children = {}
    for app in (d for d in bootstrap if d['kind'] == 'Application'):
        source = app['spec']['source']
        chart = source['path'].split('/')[-1]
        docs = render(chart, source['helm']['releaseName'], app['spec']['destination']['namespace'],
                      {p['name']: p['value'] for p in source['helm']['parameters']})
        children[chart] = docs
        all_docs.extend(docs)
    return ns, bootstrap, children, all_docs


def selects(selector, labels):
    if any(labels.get(k) != v for k, v in selector.get('matchLabels', {}).items()):
        return False
    for expr in selector.get('matchExpressions', []):
        k, op = expr['key'], expr['operator']
        if op == 'Exists' and k not in labels:
            return False
        if op == 'DoesNotExist' and k in labels:
            return False
        if op == 'NotIn' and labels.get(k) in expr['values']:
            return False
        if op == 'In' and labels.get(k) not in expr['values']:
            return False
    return True


class Consolidation(unittest.TestCase):
    def test_tenant_matrix(self):
        for user, suffix, runtime, harness, enforced in [
            ('user1', 'agentops', 'openshell', 'hermes', 'false'),
            ('user2', 'training', 'openshell', 'hermes', 'true'),
            ('user3', 'agentops', 'pod', 'hermes', 'true'),
            ('user4', 'training', 'pod', 'waterplant', 'false'),
        ]:
            with self.subTest(user=user):
                ns, bootstrap, children, docs = tenant(user, suffix, runtime, harness, enforced)
                self.assertEqual([d['metadata']['name'] for d in docs if d['kind'] == 'Namespace'], [ns])
                identities = set()
                for d in docs:
                    meta = d['metadata']
                    key = (d['apiVersion'], d['kind'], meta.get('namespace', ns), meta['name'])
                    self.assertNotIn(key, identities, f'duplicate ownership: {key}')
                    identities.add(key)
                    self.assertIn(meta.get('namespace', ns), [ns, 'openshift-gitops', 'keycloak'])
                    self.assertNotIn(f'{user}-openshell.svc', json.dumps(d))
                    for subject in d.get('subjects', []):
                        if subject['kind'] == 'ServiceAccount':
                            self.assertEqual(subject.get('namespace', ns), ns)
                for app in (d for d in bootstrap if d['kind'] == 'Application'):
                    self.assertEqual(app['spec']['destination']['namespace'], ns)
                ui = resource(docs, 'Deployment', 'water-plant-ui')
                env = {e['name']: e.get('value') for e in ui['spec']['template']['spec']['containers'][0]['env']}
                if harness == 'hermes':
                    self.assertEqual(env['AGENT_URL'], f'http://hermes-agent.{ns}.svc:8787')
                if runtime == 'openshell':
                    gateway = resource(docs, 'StatefulSet', f'{user}-openshell')
                    gateway_labels = gateway['spec']['template']['metadata']['labels']
                    self.assertTrue(selects(resource(docs, 'NetworkPolicy', 'openshell-gateway-ingress')['spec']['podSelector'], gateway_labels))
                    self.assertTrue(selects(resource(docs, 'NetworkPolicy', 'hermes-openshell-bridge-ingress')['spec']['ingress'][0]['from'][0]['podSelector'], ui['spec']['template']['metadata']['labels']))
                    bridge = resource(docs, 'Deployment', 'hermes-openshell-bridge')
                    env = {e['name']: e.get('value') for e in bridge['spec']['template']['spec']['containers'][0]['env']}
                    self.assertEqual(env['OPENSHELL_NS'], ns)
                    self.assertEqual(env['AGENTOPS_NS'], ns)
                    self.assertEqual(env['GATEWAY_HOST'], f'{user}-openshell.{ns}.svc.cluster.local')
                    self.assertIn(f'.{ns}.svc.cluster.local', env['MCP_GATEWAY_URL'])
                    policy = resource(docs, 'ConfigMap', 'openshell-sandbox-policy')['data']['policy.yaml']
                    self.assertIn(f'hermes-mlflow-relay.{ns}.svc.cluster.local', policy)
                    job = resource(docs, 'Job', 'mcp-gateway-rollout')
                    env = {e['name']: e.get('value') for e in job['spec']['template']['spec']['containers'][0]['env']}
                    self.assertIn('hermes-openshell-bridge', env['CLIENTS'])
                    self.assertNotIn('/', env['CLIENTS'])
                role = resource(bootstrap, 'Role', 'participant')
                for rule in role['rules']:
                    self.assertNotIn('secrets', rule['resources'])
                    self.assertNotIn('pods/exec', rule['resources'])
                    self.assertNotIn('create', rule['verbs'])
                    if any(v in rule['verbs'] for v in ['patch', 'update', 'delete']):
                        self.assertTrue(rule.get('resourceNames'))
                        self.assertTrue(set(rule['resources']) <= {'configmaps', 'networkpolicies', 'authpolicies'})
                self.assertFalse(any(d['kind'] == 'ClusterRoleBinding' and any(s['kind'] == 'User' for s in d.get('subjects', [])) for d in docs))
                for policy in [d for d in children['tenant-policy'] if d['kind'] == 'NetworkPolicy']:
                    for labels in [
                        {'app.kubernetes.io/name': 'openshell'},
                        {'app.kubernetes.io/name': 'hermes-openshell-bridge'},
                        {'agents.x-k8s.io/sandbox-name-hash': 'abc'},
                    ]:
                        self.assertFalse(selects(policy['spec']['podSelector'], labels))
                if runtime == 'openshell':
                    ingress = resource(docs, 'NetworkPolicy', 'openshell-gateway-ingress')['spec']['ingress'][0]['from']
                    for labels, allowed in [
                        ({'app.kubernetes.io/name': 'hermes-openshell-bridge'}, True),
                        ({'agents.x-k8s.io/sandbox-name-hash': 'abc'}, True),
                        ({'app.kubernetes.io/name': 'water-plant-ui'}, False),
                        ({}, False),
                    ]:
                        self.assertEqual(any(selects(p['podSelector'], labels) for p in ingress), allowed)

    def test_sandbox_namespace_override_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError):
            render('tenant-openshell', 'user1-openshell', 'user1-agentops', {
                'username': 'user1', 'keycloak.host': 'sso.example.com',
                'helm-chart.server.sandboxNamespace': 'user1-sandbox',
            })

    def test_admission_expressions(self):
        ns, bootstrap, children, _ = tenant()
        app = resource(bootstrap, 'Application', 'user1-policy')
        guard = resource(bootstrap, 'ValidatingAdmissionPolicy', f'{ns}-policy-application')
        cases = []
        def case(name, change, allowed):
            obj = copy.deepcopy(app)
            change(obj)
            cases.append(dict(name=name, object=obj, oldObject=app, allowed=allowed,
                              request={'namespace': 'openshift-gitops'},
                              expressions=[v['expression'] for v in guard['spec']['validations']]))
        def parameter(obj, name, value):
            ps = obj['spec']['source']['helm']['parameters']
            existing = next((p for p in ps if p['name'] == name), None)
            if existing:
                existing['value'] = value
            else:
                ps.append({'name': name, 'value': value})
        case('unchanged', lambda o: None, True)
        case('normal sync', lambda o: o.update(operation={'sync': {'prune': True, 'syncStrategy': {'hook': {}}}}), True)
        for name in ['mcpGateway.enforced', 'networkPolicy.permissiveEgress', 'openshell.permissiveEgress', 'openshell.filesystem.readOnly[0]', 'openshell.broadOutbound.hosts[0]']:
            case(f'edit {name}', lambda o, n=name: parameter(o, n, 'true'), True)
        for name in ['username', 'namespaceSuffix', 'openshell.enabled', 'keycloak.host', 'mcpGateway.rollout.image', 'mcpGateway.rollout.clientDeployments[0]', 'mcpGateway.rollout.serviceAccount']:
            case(f'override {name}', lambda o, n=name: parameter(o, n, 'attacker'), False)
        for key in ['repoURL', 'path', 'targetRevision']:
            case(f'change source {key}', lambda o, k=key: o['spec']['source'].update({k: 'other'}), False)
        case('invalid boolean', lambda o: parameter(o, 'mcpGateway.enforced', 'true,username=user2'), False)
        case('string boolean', lambda o: next(p for p in o['spec']['source']['helm']['parameters'] if p['name'] == 'mcpGateway.enforced').update(forceString=True), False)
        case('change destination', lambda o: o['spec']['destination'].update(namespace='user2-agentops'), False)
        case('change project', lambda o: o['spec'].update(project='default'), False)
        case('add source field', lambda o: o['spec']['source'].update(plugin={'name': 'other'}), False)
        case('inline Helm values', lambda o: o['spec']['source']['helm'].update(values='username: user2'), False)
        case('delete source identity', lambda o: o['spec']['source'].pop('repoURL'), False)
        case('sync alternate revision', lambda o: o.update(operation={'sync': {'revision': 'other', 'syncStrategy': {'hook': {}}}}), False)
        case('sync inline manifests', lambda o: o.update(operation={'sync': {'manifests': ['evil'], 'syncStrategy': {'hook': {}}}}), False)
        case('force hook sync', lambda o: o.update(operation={'sync': {'syncStrategy': {'hook': {'force': True}}}}), False)
        case('apply sync', lambda o: o.update(operation={'sync': {'syncStrategy': {'apply': {}}}}), False)
        case('override sync source', lambda o: o.update(operation={'sync': {'source': {'repoURL': 'other'}, 'syncStrategy': {'hook': {}}}}), False)
        case('multiple sources', lambda o: o['spec'].update(sources=[{'repoURL': 'other'}]), False)
        case('ignore differences', lambda o: o['spec'].update(ignoreDifferences=[{'kind': '*', 'jsonPointers': ['/spec']}]), False)
        # Every typed field outside the editable branches must be guarded. Update
        # the schema fixture when upgrading Argo CD to catch newly added fields.
        schema = json.loads((Path(__file__).parent / 'celcheck/application-schema.json').read_text())
        expressions = ' '.join(v['expression'] for v in guard['spec']['validations'])
        for path, editable in [('spec', {'source'}), ('spec.source', {'helm'}),
                               ('spec.source.helm', {'parameters'}), ('operation', {'sync'}),
                               ('operation.sync', {'prune', 'syncStrategy'})]:
            node = schema
            for part in path.split('.'):
                node = node['properties'][part]
            for field in node['properties'].keys() - editable:
                cel_field = '__namespace__' if field == 'namespace' else field
                self.assertIn(f'has(object.{path}.{cel_field})', expressions)
        case('duplicate parameter', lambda o: o['spec']['source']['helm']['parameters'].append({'name': 'username', 'value': 'user2'}), False)
        network = resource(children['tenant-policy'], 'NetworkPolicy', 'egress-baseline')
        guard = resource(bootstrap, 'ValidatingAdmissionPolicy', f'{ns}-policy-network')
        for name, change, allowed in [
            ('tighten egress', lambda o: o['spec'].update(egress=[]), True),
            ('target all pods', lambda o: o['spec'].update(podSelector={}), False),
            ('change policy type', lambda o: o['spec'].update(policyTypes=['Ingress', 'Egress']), False),
        ]:
            obj = copy.deepcopy(network)
            change(obj)
            cases.append(dict(name=name, object=obj, oldObject=network, allowed=allowed,
                              request={'namespace': ns}, expressions=[v['expression'] for v in guard['spec']['validations']]))
        helper = os.environ.get('CELCHECK')
        self.assertTrue(helper, 'Build automation/tests/celcheck and set CELCHECK to its executable')
        subprocess.run([helper], input=json.dumps(cases), text=True, check=True)


if __name__ == '__main__':
    unittest.main()
