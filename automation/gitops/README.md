# Participant deployment layout

Each participant has one workload namespace, `<username>-<namespaceSuffix>`
(default `<username>-agentops`), plus a separate Showroom namespace. The workload
namespace contains the UI, plant API, MCP servers and gateway, OpenShell gateway,
Hermes sandbox and bridge. Shared services, Keycloak and operators stay in their
existing namespaces.

`namespaceSuffix` is the single workload namespace setting in all tenant charts;
`bootstrap-infra` uses `lab.namespaceSuffix` for the matching ArgoCD destination.
The OpenShell Application and Helm release remain `<username>-openshell` because
the vendored chart derives cluster-scoped RBAC names from the release. That name
no longer identifies a namespace.

The separate platform and OpenShell Applications still auto-sync and self-heal.
The policy Application still syncs manually, preserving participant edits.
Bootstrap must be synced before platform to install the participant admission
guards. Initial provisioning must sync the policy Application once before direct
policy editing; an unsynced OpenShell runtime uses its platform-owned fallback
policy until that ConfigMap exists.

## Participant workflow and permissions

Participants can inspect their own workloads, logs, services, gateways, MCP
resources and policies. They can update these existing resources directly:

- NetworkPolicy `allow-ingress-within-namespace`.
- AuthPolicies `mcp-auth-policy` and `mcp-authz-policy`, when enforcement is enabled.

Network-policy workload selectors and policy types stay fixed, keeping the
privileged sandbox, bridge and OpenShell gateway outside the editable policies.
The OpenShell policy inside the sandbox remains editable, including its filesystem
paths and per-binary network rules. The bridge watches that ConfigMap and applies
changes, recreating the sandbox when required by a filesystem restriction.

Participants may also update these Helm parameters on their own policy Application:

- `mcpGateway.enforced`.

Boolean toggles must use `true` or `false`, without `forceString`. Keep the existing
identity and infrastructure parameters in place when patching the parameter list.

A normal sync applies those settings and runs the trusted restart Job:

```sh
oc patch application "${USER_NAME}-policy" -n openshift-gitops --type merge \
  -p '{"operation":{"sync":{"prune":true,"syncStrategy":{"hook":{}}}}}'
```

A sync restores resources from the Application's Helm parameters; it overwrites
any direct edits to those resources. Choose the intended parameter values before
syncing. Direct AuthPolicy edits do not themselves run the PostSync restart Job.
Use the Helm-and-sync workflow for enforcement toggles and gateway restarts.

The participant Role excludes Secrets, pod exec, workload creation/mutation and
RBAC changes. ValidatingAdmissionPolicies prevent using Application updates to
change the deployment source, destination, revision, identity, rollout image or
inline manifests. They also prevent retargeting editable NetworkPolicies to
protected workloads. These guards require the `admissionregistration.k8s.io/v1`
ValidatingAdmissionPolicy API; they are mandatory, not an optional hardening flag.

## Existing deployments

### Hermes report skill

The OpenShell bridge includes the externalized `write-report` skill and its
Python helper in `/hermes`. Upload that directory as usual and run
`start-hermes`; when it sources `hermes-env.sh`, the skill is copied into
`/sandbox/.hermes/skills/write-report`. After changing the skill, re-upload
`/hermes` and restart Hermes.

Both unsandboxed deployments (`hermes-agent` with `agent.hermes.runtime: pod`,
and the comparison deployment `hermes-plain`) install the skill automatically
through their `seed-config` init container. Each mounts an ephemeral `emptyDir` volume at `/reports`, so the path is
writable without an image change. Kubernetes creates the writable report directory. Reports
are discarded when the pod is deleted or replaced.
Skill changes trigger a Deployment rollout through a checksum annotation.
The skill files are packaged in both Helm charts; keep the copies in
`tenant-platform/files/skills/write-report` and
`tenant-openshell/files/skills/write-report` identical.

Example single prompt: `Write a report on the current water plant status.`
The skill saves Markdown under `/reports`, creates the directory when permitted,
and returns a filename such as
`/reports/2026-10-12_14-30-45-123456Z_water-plant-status.md`. Times are UTC;
exclusive creation prevents overwrites even if timestamps collide.

OpenShell runtime prerequisite: provision `/reports` in the sandbox image with
Linux permissions allowing the sandbox user to write there. Do not symlink it
into the already-writable `/sandbox`: Module 4 intentionally starts with report
access denied and then grants access specifically to `/reports`. The image build
is maintained in the agent repository; rebuild and deploy an image containing
that directory before running the exercise. A non-root process cannot create a
new directory directly under `/`, even if the skill requests it. Skill updates
still use the existing bridge upload; verify the image's start script sources
`hermes-env.sh`.

Operators can simply say "Write a report on the current pump status" or "Read
my latest report". The skill always selects `/reports`; operators do not
need to supply or know the Linux path.

No end-user confirmation is requested by the skill or helper. Keep Hermes'
normal command approvals enabled: this helper only creates a directory and a
new report file. Deployment-specific command approval rules must permit this
invocation without interaction; a skill cannot override those rules. Unsandboxed
reports last only for the lifetime of their pod; reports in the sandbox
filesystem do not survive sandbox deletion unless exported.

This is a repository change, not an automatic live migration. Kubernetes resources
cannot be moved between namespaces in place. Recreating a participant environment
is the simplest rollout for disposable lab environments. For an existing event,
use a maintenance window and validate one participant before expanding the change.

1. Record the current Application revisions/parameters and preserve any participant
   policy edits or sandbox files that must survive recreation. Keep MLflow data
   and participant Keycloak realms; their namespaces do not move.
2. Inspect RHDP/catalog overrides outside this repository. Remove the obsolete
   `openshellNamespaceSuffix`, `agent.hermes.openshellNamespaceSuffix`,
   `openshell.namespaceSuffix`, `participantAccess` and OpenShell `policyRollout`
   settings. Update any explicit UI URL, gateway callback URL, sandbox namespace
   override or rollout target referring to the old namespace.
3. Inventory existing bindings, including catalog/Showroom grants. Remove the old
   `<username>-edit` RoleBinding and `<username>-agentops-participant`
   ClusterRoleBinding, plus any equivalent externally managed broad grants in the
   combined namespace, before placing privileged workloads there. RBAC is additive;
   adding the new Role cannot restrict an existing `edit` or `admin` binding.
   Also audit ArgoCD account permissions: the supported participant sync path is
   `oc patch` under their Kubernetes identity. Do not grant unrestricted ArgoCD
   Application updates through a server account that bypasses these user-matched
   admission guards.
4. Coordinate the bootstrap, platform, OpenShell and policy syncs. Do not let
   automated OpenShell sync or namespace pruning start halfway through the change.
   Install and verify the admission policies/bindings before granting Application
   update access. Namespace creation has one owner: bootstrap-tenant/namespace.yaml.
   The rollout Role/Binding has one owner: tenant-platform. Recreate OpenShell in the
   combined namespace; update platform endpoints and sync the policy Application.
5. Verify the UI-to-Hermes round trip, tool discovery/calls, policy tightening and
   rollback, MLflow traces, restart hooks and denied access to Secrets/privileged
   workloads. Test two participants to confirm their endpoints and permissions stay
   separate. Check admission policy status/type-checking and exercise real API
   requests as a participant, not only an administrator.
6. Only after verification, remove old OpenShell resources and namespace. The
   old Namespace manifest is removed from bootstrap, so a pruning sync can delete
   it and everything left inside it. The unused global `agentops-participant`
   ClusterRole can be removed after its old bindings are gone.

`<username>-sandbox` is not created by these charts. Identify its external owner
and contents before deciding whether to remove it.

The combined quota defaults to requests of 8 CPU / 16 GiB, limits of 12 CPU /
24 GiB and 20 pods. Check aggregate cluster capacity for the participant count;
these limits do not reserve that capacity.

## Offline validation

The regression suite renders complete parent/child Application trees for two
participants, a custom suffix and all three agent runtime variants. It checks
resource ownership, namespace references, environment variables, permissions and
network selectors. A small Go helper compiles and evaluates the rendered admission
CEL against permitted edits and attempted infrastructure changes. Application
expressions are also compiled against the recorded Kubernetes CRD schema; see
[the schema fixture notes](../tests/celcheck/README.md) when upgrading Argo CD.

Requires Helm, Python with PyYAML, and Go:

```sh
go -C automation/tests/celcheck build -o /tmp/agentops-celcheck .
CELCHECK=/tmp/agentops-celcheck python3 -m unittest discover -s automation/tests -v
```

These are render and policy-expression checks. They do not replace the live
migration and end-to-end checks above.
