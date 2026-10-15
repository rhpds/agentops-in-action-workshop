{{- define "tg.namespace" -}}
{{- printf "%s-%s" .Values.username .Values.namespaceSuffix -}}
{{- end -}}

{{- define "tg.labels" -}}
app.kubernetes.io/name: nemo-guardrails
app.kubernetes.io/part-of: water-plant
rhdp.redhat.com/lab: agentops-in-action
rhdp.redhat.com/participant: {{ .Values.username | quote }}
{{- end -}}
