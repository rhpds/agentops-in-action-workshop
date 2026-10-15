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
*/}}
{{- define "waterplant.hermesApprovals" -}}
approvals:
  mode: "off"

agent:
  disabled_toolsets: [code_execution]

platform_toolsets:
  api_server: [terminal, file, skills, web, memory]
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
