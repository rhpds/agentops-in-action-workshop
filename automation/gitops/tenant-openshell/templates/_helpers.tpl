{{- define "to.agentopsNamespace" -}}
{{- printf "%s-%s" .Values.username .Values.namespaceSuffix -}}
{{- end -}}

{{- define "to.namespace" -}}
{{- printf "%s-%s" .Values.username .Values.openshellNamespaceSuffix -}}
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
The vendored chart puts everything in the release namespace, and the bridge
assumes it is <username>-openshell.
*/}}
{{- define "to.checks" -}}
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
