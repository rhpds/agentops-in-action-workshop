{{/*
The OpenShell sandbox policy the bridge uses until the participant's own copy,
tenant-policy's openshell-sandbox-policy ConfigMap, exists.

Keep in step with tenant-policy/templates/_openshell-policy.tpl and its
openshell values: that is the copy participants edit, and an unsynced policy
Application should look exactly like a synced one at baseline.
*/}}
{{- define "to.baselinePolicy" -}}
{{- $p := .Values.baselinePolicy -}}
{{- $modelHost := regexReplaceAll "^https?://([^/:]+).*$" .Values.model.baseUrl "${1}" -}}
version: 1

filesystem_policy:
  include_workdir: true
  read_only:
{{- range $p.filesystem.readOnly }}
    - {{ . }}
{{- end }}
  read_write:
{{- range $p.filesystem.readWrite }}
    - {{ . }}
{{- end }}

landlock:
  compatibility: best_effort

process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  model_endpoint:
    name: "Model endpoint"
    endpoints:
      - { host: {{ $modelHost | quote }}, port: 443, protocol: rest, enforcement: enforce, access: full }
    binaries:
      - { path: /usr/bin/python3 }
      - { path: /usr/bin/python3.12 }
      - { path: /usr/local/bin/hermes }
  mcp_gateway:
    name: "MCP Gateway"
    endpoints:
      - { host: {{ include "to.mcpGatewayHost" . | quote }}, port: 8080, protocol: rest, enforcement: enforce, access: full }
    binaries:
      - { path: /usr/bin/python3 }
      - { path: /usr/bin/python3.12 }
      - { path: /usr/local/bin/hermes }
  keycloak_token:
    name: "Keycloak token endpoint (mcp-token-refresh.py)"
    endpoints:
      - { host: {{ .Values.keycloak.host | quote }}, port: 443, protocol: rest, enforcement: enforce, access: full }
    binaries:
      - { path: /usr/bin/python3 }
      - { path: /usr/bin/python3.12 }
{{- if .Values.mlflow.enabled }}
  mlflow_tracing:
    name: "MLflow tracing (hermes_otel)"
    endpoints:
      - { host: {{ .Values.mlflow.host | quote }}, port: {{ .Values.mlflow.port }}, protocol: rest, enforcement: enforce, access: full }
    binaries:
      - { path: /usr/bin/python3 }
      - { path: /usr/bin/python3.12 }
      - { path: /usr/local/bin/hermes }
{{- end }}
{{- if $p.permissiveEgress }}
  broad_outbound:
    name: "Broad outbound (baseline)"
    endpoints:
{{- range $h := $p.broadOutbound.hosts }}
{{- range $port := $p.broadOutbound.ports }}
      - { host: {{ $h | quote }}, port: {{ $port }}, protocol: rest, enforcement: enforce, access: full }
{{- end }}
{{- end }}
    binaries:
{{- range $p.broadOutbound.binaries }}
      - { path: {{ . | quote }} }
{{- end }}
{{- end }}
{{- end -}}
