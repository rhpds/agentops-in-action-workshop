# Create an environment from namespace-consolidation

`namespace-consolidation.yaml` defines two manual-sync bootstrap Applications.
Both use `https://github.com/rhpds/agentops-in-action-workshop.git` at branch
`namespace-consolidation`. The tenant's `gitops.targetRevision` also pins its
platform, OpenShell and policy children to that branch.

Prerequisites: the branch and its changes are pushed, OpenShift GitOps is installed
in `openshift-gitops`, and the cluster has the RHDP Keycloak and model endpoint
expected by the charts. These Applications do not provision the cluster, participant
login, model API key or Showroom instructions. The participant name must match an
existing OpenShift user. Keycloak defaults to `sso.<APPS_DOMAIN>`; change `keycloak.host`
in the tenant values if the cluster uses another hostname.

Set the two non-secret inputs and render directly into the Kubernetes API:

```sh
export PARTICIPANT=user1
export APPS_DOMAIN=apps.your-cluster.example.com
set -o pipefail
python3 automation/argocd/render-applications.py | oc apply -f -
```

The renderer prompts privately for the participant's model API key and a Hermes
API server bearer key. Alternatively provide `MODEL_API_KEY` and
`HERMES_API_SERVER_KEY` through your environment. No credentials are written to a
local file. Do not redirect the rendered output into the repository. The current
bootstrap chart receives credentials through Helm values, so they will be present
in the Argo CD Application object as well as the generated Kubernetes Secret;
restrict access to those objects.

If shared infrastructure already has an Argo CD owner, reuse that Application:
change the first definition's `metadata.name` and `helm.releaseName` to match the
existing Application/release, preserving any cluster-specific overrides. Do not
sync two Applications over the same shared operators, AppProject and services.

After applying, sync in this order (Argo CD UI or authenticated CLI):

```sh
argocd app sync agentops-bootstrap-infra
argocd app wait agentops-bootstrap-infra --health --timeout 1800
argocd app sync "${PARTICIPANT}-bootstrap"
# These two children normally auto-sync; explicit sync is also safe for a new tenant.
argocd app sync "${PARTICIPANT}-platform"
argocd app wait "${PARTICIPANT}-platform" --health --timeout 1200
argocd app sync "${PARTICIPANT}-openshell"
argocd app wait "${PARTICIPANT}-openshell" --health --timeout 1200
argocd app sync "${PARTICIPANT}-policy"
argocd app wait "${PARTICIPANT}-policy" --health --timeout 1200
```

Use the existing infrastructure Application name in these commands if you reused
one. The workload namespace will be `${PARTICIPANT}-agentops`; the OpenShell
Application's name remains `${PARTICIPANT}-openshell`, but creates no extra namespace.

For an existing participant, follow the [migration instructions](../gitops/README.md#existing-deployments)
instead of treating this as a fresh deployment.
