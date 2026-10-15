{{- /*
Approvals off and execute_code removed, for every Hermes this chart points the
console at.

Why. The console speaks /v1/chat/completions, and that handler registers no
approval callback — only /v1/runs does, with /v1/runs/{id}/approval to resolve
it. So a manual-mode prompt calls submit_pending() into a per-session queue
with no listener, and the tool returns "Asking the user for approval". The
agent then blocks forever and tells the operator it is waiting on them, while
nothing in the console can grant it: saying "yes" in the chat is a new turn,
not an approval, so the queue entry is untouched. Hermes defaults
approvals.mode to manual, so leaving it unset is what selects this.

mode: off rather than smart — smart needs auxiliary.approval configured, and an
escalate verdict falls through to the same dead queue. Coherent with the soul,
too: the agent is not an authorization boundary here, the platform is. And
approval.py's hardline blocklist is unconditional, so it still applies.

execute_code is gated unconditionally in a gateway context whatever the script
does (check_execute_code_guard), which is how a module 1 report write
deadlocked. write-report tells the agent to use `terminal`, whose command trips
no dangerous pattern — the model reached for execute_code anyway. Dropping the
toolset leaves terminal, read_file and write_file, so the skill's documented
path is the only one on offer.

A named template, not inline config text, so it can be hashed into the pod
annotations that consume it: no existing checksum covers the inline config, and
seed-config only runs at pod start, so an inline edit would update the
ConfigMap while the pod kept copying the old file into $HERMES_HOME.

Must stay byte-identical to tenant-openshell's copy: the two configs should
differ only by runtime.
*/}}
{{- define "waterplant.hermesApprovals" -}}
approvals:
  mode: "off"

agent:
  disabled_toolsets: [code_execution]
{{- end -}}
