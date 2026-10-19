{{- define "to.agentopsNamespace" -}}
{{- include "to.namespace" . -}}
{{- end -}}

{{- define "to.namespace" -}}
{{- printf "%s-%s" .Values.username .Values.namespaceSuffix -}}
{{- end -}}

{{/*
The OpenShell gateway's name, which the vendored chart derives from the release.

When the release name contains "openshell", the chart's fullname IS the release
name, and it names the Service, the sandbox ServiceAccount and a ClusterRole and
ClusterRoleBinding after it. Those two are cluster-scoped, so the name must be
unique per participant: a fixed name collides with the next tenant. bootstrap-tenant
names the release <username>-openshell.
*/}}
{{- define "to.gatewayName" -}}
{{- if not (contains "openshell" .Release.Name) -}}
{{- fail (printf "release name %q must contain \"openshell\"; bootstrap-tenant uses <username>-openshell" .Release.Name) -}}
{{- end -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "to.gatewayHost" -}}
{{- printf "%s.%s.svc.cluster.local" (include "to.gatewayName" .) (include "to.namespace" .) -}}
{{- end -}}

{{- define "to.mcpGatewayHost" -}}
{{- printf "%s-%s.%s.svc.cluster.local" .Values.mcpGateway.gatewayName .Values.mcpGateway.gatewayClassName (include "to.agentopsNamespace" .) -}}
{{- end -}}

{{/*
The MLflow relay, in the bridge pod. Hermes posts spans to it over plain HTTP
and nginx forwards them to MLflow over HTTPS, because OpenShell's egress proxy
cannot verify MLflow's service-CA certificate. See values.yaml's mlflow.relay.
*/}}
{{- define "to.mlflowRelayHost" -}}
{{- printf "%s.%s.svc.cluster.local" .Values.mlflow.relay.serviceName (include "to.namespace" .) -}}
{{- end -}}

{{/*
The vendored chart puts everything in the release namespace, and the bridge
requires it to match the combined <username>-<namespaceSuffix> namespace.
*/}}
{{- define "to.checks" -}}
{{- $sandboxNs := (index .Values "helm-chart").server.sandboxNamespace | default .Release.Namespace -}}
{{- if ne $sandboxNs (include "to.namespace" .) -}}
{{- fail "helm-chart.server.sandboxNamespace must match the participant namespace" -}}
{{- end -}}
{{- if ne .Release.Namespace (include "to.namespace" .) -}}
{{- fail (printf "deploy into %s, not %s" (include "to.namespace" .) .Release.Namespace) -}}
{{- end -}}
{{- if not .Values.keycloak.host -}}
{{- fail "keycloak.host is required (forwarded by bootstrap-tenant)" -}}
{{- end -}}
{{- end -}}

{{- define "to.labels" -}}
app.kubernetes.io/part-of: water-plant
rhdp.redhat.com/lab: agentops-in-action
rhdp.redhat.com/participant: {{ .Values.username }}
{{- end -}}

{{- /*
Approvals off and execute_code removed, for the reasons set out beside the
identical block in tenant-platform/templates/_approvals.tpl. In short: the
console speaks /v1/chat/completions, which registers no approval callback, so
Hermes' default approvals.mode of manual parks the prompt in a queue with no
listener and the agent waits on an operator who is never asked. Must stay
byte-identical to that copy — the two configs should differ only by runtime.

platform_toolsets pins api_server's toolsets explicitly, which is what makes
`terminal` reachable at all: Hermes otherwise infers the enabled set by subset
and drops the whole terminal toolset, because it resolves to four tools while
hermes-api-server carries only two of them. Same defect here as on the plain
Hermes — this chart runs the same api_server platform.

A named template so it can be hashed into the bridge's pod annotation:
checksum/bridge covers .Values and the bridge files but not inline config text,
and the supervisor renders config.yaml only at start-up, so an inline edit
would update the ConfigMap while the old file kept being published to /hermes.

Here the sandbox is the control that matters anyway. OpenShell's filesystem and
network policy decide what the agent may touch, and that is what module 4 has
participants tighten. An approval the operator is never shown adds no
containment; it only looks like a broken agent.

Memory off, all three ways it can be on.

Each lab session has to start from the same place. Hermes' memory does not:
it persists across sessions in $HERMES_HOME, which is the sandbox's own volume
for hermie and a PVC for the plain agent, so what one run learns the next one
carries. For a long-lived assistant that is the feature. For a lab whose
modules are measured against each other — run the evals, add a control, run
them again — it is a variable nobody declared, and a module that passes
because an earlier session left a note about pump 4 has measured nothing.

It is also an attack surface of the same shape as the skill-patching the
skills block closes off. An injected instruction that reaches MEMORY.md is
injected into every later turn, in modules that never saw the injection.

Both halves are needed, and neither is redundant. The upstream docs give the
config flags as the way to do this, and on this build they are not enough on
their own — NousResearch/hermes-agent#45422 reports exactly that, and the
behaviour was confirmed against the installed package:

  disabled_toolsets: [memory]      removes the tool from the schema, and with
  memory out of platform_toolsets  it MEMORY_GUIDANCE from the system prompt.
                                   This is the only thing that does: agent.tools
                                   is built by model_tools.get_tool_definitions
                                   from the toolsets alone (agent_init ~1037),
                                   and system_prompt gates the guidance on
                                   `"memory" in agent.valid_tool_names`, not on
                                   the flag. The flags are not read until ~1208,
                                   after the schema exists. Measured: with only
                                   code_execution disabled the schema still
                                   contains `memory`; adding it to
                                   disabled_toolsets is what drops it. The
                                   platform_toolsets list is direct membership
                                   (see above), so leaving `memory` there would
                                   re-offer what disabled_toolsets just took.

  memory_enabled: false            stops the store itself. agent_init only
  user_profile_enabled: false      constructs the MemoryStore when one of these
                                   is set, so with both off MEMORY.md and
                                   USER.md are never read or written — and
                                   system_prompt's `if agent._memory_store`
                                   block never injects their contents. Without
                                   these, subtracting the toolset would take the
                                   tool away and still paste yesterday's
                                   memories into today's prompt.

user_profile_enabled is not optional: USER.md is a separate file with its own
flag and persists just as long.

The memory toolset contributes exactly one tool, `memory`, so subtracting it
costs nothing else. #45422's other complaint — that disabling the toolset also
kills external providers — cannot bite here: `provider` is empty.

Existing MEMORY.md and USER.md are left on disk. Nothing reads them once the
store is gone, and they were empty in every participant namespace when this
was written.

Not covered by any of this: session_search, which recalls across sessions from
state.db and is deliberately outside the memory flags (the upstream docs are
explicit). It is already unreachable here — it belongs to no toolset in the
platform_toolsets list above, so the api_server platform never offers it.
Verified against the installed registry alongside the rest.

Not mem0. `memory.provider` is empty, which means the built-in store; no
chart sets it. MEM0_DB_PATH used to be exported beside HERMES_HOME in
bridge-supervisor.sh and did nothing at all, which made it look as though
mem0 were wired up — it has been removed rather than left to mislead the next
reader.

Verified on cluster-zwtpw before the change: the agent's own loader reported
memory_enabled true, user_profile_enabled true, provider "".
*/}}
{{- define "waterplant.hermesApprovals" -}}
approvals:
  mode: "off"

agent:
  disabled_toolsets: [code_execution, memory]

platform_toolsets:
  api_server: [terminal, file, skills, web]

memory:
  memory_enabled: false
  user_profile_enabled: false
{{- end -}}

{{- /*
Hermes' post-turn skill review off, for the reasons set out beside the
identical block in tenant-platform/templates/_approvals.tpl. In short:
turn_finalizer spawns a self-improvement fork after any turn of ten or more
tool iterations, and that fork patches SKILL.md — so module 5's injected
bulletin ends up written into read-safety-docs as a standing rule that fires
in every later module. Must stay byte-identical to that copy.

Named, so checksum/bridge-equivalent annotations can cover it: the supervisor
renders config.yaml only at start-up, so an inline edit would update the
ConfigMap while the old file kept being published to /hermes.
*/}}
{{- define "waterplant.hermesSkills" -}}
skills:
  creation_nudge_interval: 0
{{- end -}}
