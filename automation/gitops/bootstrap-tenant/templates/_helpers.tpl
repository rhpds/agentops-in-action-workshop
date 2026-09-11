{{/*
Participant username.

The tenant catalog item passes it as `tenant.username` inside
ocp4_workload_gitops_bootstrap_helm_values, but this chart originally read
`.Values.username`. Nothing errored — Helm just fell back to the values.yaml
default, so every participant rendered `user1-agentops` and all thirty tenants
collided in one namespace. Accept both spellings, preferring the CI's.
*/}}
{{- define "tenant.username" -}}
{{- $t := .Values.tenant | default dict -}}
{{- $name := $t.username | default .Values.username -}}
{{- if not $name -}}
{{- fail "username is required: set tenant.username (catalog item) or username" -}}
{{- end -}}
{{- $name -}}
{{- end -}}

{{- define "tenant.namespace" -}}
{{- printf "%s-%s" (include "tenant.username" .) .Values.namespaceSuffix -}}
{{- end -}}
