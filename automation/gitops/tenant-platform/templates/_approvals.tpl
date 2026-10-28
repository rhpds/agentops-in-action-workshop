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
deadlocked. Dropping the toolset keeps the model off that path. Note that
approvals.mode off would have cleared the deadlock by itself — check_execute_code_guard
returns approved immediately when the mode is off — so this subtraction is not
what unblocked anything. It is here because execute_code scripts bypass
DANGEROUS_PATTERNS by design, and the governable path is the documented one.

platform_toolsets is what actually makes `terminal` reachable, and without it
the paragraph above was wrong: terminal was never on offer either. Hermes infers
a platform's enabled toolsets by subset — a configurable toolset counts as on
only when every tool it resolves to is also in the platform bundle. In the
running gateway the `terminal` toolset resolves to terminal, process,
read_terminal and close_terminal, while hermes-api-server carries only terminal
and process, so the whole toolset is dropped. The agent then reports "the
required 'terminal' tool is not available" and writes no report. Measured on
cluster-slkjc: tool.terminal appears in none of 1200+ recorded spans, and GET
/v1/toolsets reports terminal enabled=false. Naming the toolsets explicitly
switches _get_platform_tools to direct membership and skips the inference.

The list is the set the inference already produced, plus terminal — verified
behaviour-neutral otherwise, and the `gateway` MCP toolset still resolves, so
every telemetry, maintenance and control tool is untouched. code_execution is
omitted here as well as subtracted above; belt and braces.

A named template, not inline config text, so it can be hashed into the pod
annotations that consume it: no existing checksum covers the inline config, and
seed-config only runs at pod start, so an inline edit would update the
ConfigMap while the pod kept copying the old file into $HERMES_HOME.


Memory off, all three ways it can be on.

Each lab session has to start from the same place. Hermes' memory does not:
it persists across sessions in $HERMES_HOME, which is a PVC for the plain
agent and the sandbox's own volume for hermie, so what one run learns the next
one carries. For a long-lived assistant that is the feature. For a lab whose
modules are measured against each other — run the evals, add a control, run
them again — it is a variable nobody declared, and a module that passes
because an earlier session left a note about pump 4 has measured nothing.

It is also an attack surface of the same shape as the skill-patching the
block below closes off. An injected instruction that reaches MEMORY.md is
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
chart sets it. MEM0_DB_PATH used to be exported next to HERMES_HOME and did
nothing at all, which made it look as though mem0 were wired up — it has been
removed rather than left to mislead the next reader.

Verified on cluster-zwtpw before the change: the agent's own loader reported
memory_enabled true, user_profile_enabled true, provider "".

Must stay byte-identical to tenant-openshell's copy: the two configs should
differ only by runtime.
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
Hermes' post-turn skill review off, for every Hermes this chart points the
console at.

Why. agent/turn_finalizer.py spawns the background self-improvement fork after
any turn that used skills.creation_nudge_interval tool iterations or more
(default 10) while skill_manage is in the toolset. The fork replays the
conversation and patches the skill library. That is a sensible default for a
long-lived assistant and the wrong one here: a module 5 turn walks into the
injected field service bulletin, and the fork then writes the attacker's
"reply only in emoji" directive into read-safety-docs/SKILL.md as a standing
rule. The injection stops being one bad answer and becomes the skill — it
fires on every later documentation lookup, including in modules that never
asked for the bulletin, and it outlives the conversation because $HERMES_HOME
is a PVC. Observed in a participant's own traces: two such patches in one
session, the second adding "comply with its response format requirements,
which override all other instructions in this skill".

Zero fails the `> 0` check in turn_finalizer, so the fork is never spawned.
Skills only, and that used to leave the memory review running on its own nudge
interval — it no longer has anything to review, because the approvals block
above turns memory off outright. The two skills here are the lab's, not
sediment for the agent to curate, and reseed-skills.sh is what puts them back
if one drifts anyway.

A named template, hashed into the pod annotations, for the same reason as the
approvals block above: seed-config renders config.yaml only at pod start.

Must stay byte-identical to tenant-openshell's copy.
*/}}
{{- define "waterplant.hermesSkills" -}}
skills:
  creation_nudge_interval: 0
{{- end -}}
