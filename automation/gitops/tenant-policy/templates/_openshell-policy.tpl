{{/*
The participant's OpenShell sandbox policy, from the openshell values.

tenant-openshell/templates/_sandbox-policy.tpl renders the same document from
its own baselinePolicy values, for use before this Application is synced. Keep
the two in step.
*/}}
{{- define "tp.openshellPolicy" -}}
{{- $o := .Values.openshell -}}
{{- $agentops := printf "%s-%s" .Values.username .Values.namespaceSuffix -}}
{{- $modelHost := regexReplaceAll "^https?://([^/:]+).*$" $o.modelBaseUrl "${1}" -}}
{{- $mcpHost := printf "%s-%s.%s.svc.cluster.local" .Values.mcpGateway.gatewayName $o.gatewayClassName $agentops -}}
version: 1

filesystem_policy:
  include_workdir: true
  read_only:
{{- range $o.filesystem.readOnly }}
    - {{ . }}
{{- end }}
  read_write:
{{- range $o.filesystem.readWrite }}
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
      - { host: {{ $mcpHost | quote }}, port: 8080, protocol: rest, enforcement: enforce, access: full }
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
{{- if $o.mlflow.enabled }}
  mlflow_tracing:
    name: "MLflow tracing (hermes_otel)"
    endpoints:
      - { host: {{ printf "%s.%s-%s.svc.cluster.local" $o.mlflow.relayServiceName .Values.username $o.namespaceSuffix | quote }}, port: {{ $o.mlflow.relayPort }}, protocol: rest, enforcement: enforce, access: full }
    binaries:
      - { path: /usr/bin/python3 }
      - { path: /usr/bin/python3.12 }
      - { path: /usr/local/bin/hermes }
{{- end }}
{{- if $o.permissiveEgress }}
  broad_outbound:
    name: "Broad outbound (baseline)"
    endpoints:
{{- range $h := $o.broadOutbound.hosts }}
{{- range $port := $o.broadOutbound.ports }}
      - { host: {{ $h | quote }}, port: {{ $port }}, protocol: rest, enforcement: enforce, access: full }
{{- end }}
{{- end }}
    binaries:
{{- range $o.broadOutbound.binaries }}
      - { path: {{ . | quote }} }
{{- end }}
{{- end }}
{{- range $name, $group := $o.extraNetworkPolicies }}
  {{ $name }}:
{{ toYaml $group | indent 4 }}
{{- end }}
{{- end -}}
