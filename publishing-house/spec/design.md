# AgentOps in Action: Evaluate, Secure, and Operate Enterprise AI Agents

## Overview

AI agents interact with enterprise systems, invoke tools, execute generated code, and reach external services. Those capabilities are what make agents useful, and they are also what makes an agent deployed without controls a security, governance, and operational problem. This lab exists to show that the answer is not a different agent framework — it is the identity, isolation, policy, observability, and evaluation infrastructure placed around whichever agent a customer already has.

Participants work with a single predeployed agent running on Red Hat OpenShift AI and never modify its code. They interact with it through a browser UI, inspect its tool calls and MLflow traces, and run a prebuilt EvalHub suite to capture a baseline scorecard. They then attack it — manual prompt injection to invoke a privileged ticket-update tool, generated code that reads a planted test credential, generated code that reaches an unauthorized network endpoint — plus an automated Garak adversarial profile, and confirm each failure in the traces. Next they apply controls without rebuilding the agent: inspect the Kata-backed Agent Sandbox boundary, then use OpenShell to restrict filesystem paths, deny specific process execution, apply per-binary outbound network rules, and move the exposed credential into governed storage. They add identity-aware authorization by running the same prompt as an Analyst persona and an Incident Manager persona and observing MCP Gateway allow one and reject the other. Finally they re-run the identical evaluation suite, compare baseline against hardened scorecards, diagnose one deliberately over-restrictive policy that breaks a legitimate evaluation, and tune it back.

## Target Audience

- **Role:** Solution architects, AI platform architects, consultants and services professionals, technical sales specialists, application and platform architects, Red Hat OpenShift AI administrators supporting AI workloads, and technical leaders advising customers on enterprise AI adoption.
- **Experience level:** Intermediate
- **What they already know:** Containers and Kubernetes or Red Hat OpenShift fundamentals; generative AI, large language models, and the general concept of AI agents; basic command-line use; a conceptual understanding of APIs and application permissions.
- **What they don't know:** Agent runtime sandboxing and execution policy; MCP tool governance; identity-aware agent authorization and token exchange; agent tracing and trace analysis; automated agent evaluation and adversarial red-team testing; how to tune policy to balance security against usability.

## Prerequisites

- Basic understanding of containers and Kubernetes or Red Hat OpenShift
- Familiarity with generative AI, large language models, and the general concept of AI agents
- Basic command-line experience
- Conceptual understanding of APIs and application permissions
- Prior experience building agents, configuring MCP servers, using MLflow, or writing security policy is helpful but explicitly not required

**Can the lab validate these automatically?** No. Prerequisites are knowledge-based and trust-based — there is no automated pre-check. All agent components, tools, identities, and services are predeployed, so a participant who is weaker in one area can still complete every exercise; the lab requires no installation, no agent development, and no extensive coding.

## Learning Objectives

1. Identify and assess common security and operational risks in tool-enabled AI agents by reviewing their permissions, traces, tool calls, and evaluation results
2. Apply runtime controls that restrict an agent's network, filesystem, process, and tool access without rebuilding or redeploying the agent application
3. Configure identity-aware authorization so that agents can access only the enterprise resources and MCP tools permitted for the requesting user
4. Use automated evaluations and red-team tests to detect unsafe behavior and verify that security controls are working as intended
5. Tune agent policies to balance security, usability, and required business functionality in an enterprise deployment
6. Interpret agent execution traces to distinguish model-level behavior from runtime and platform-level enforcement
7. Differentiate the enforcement responsibilities of sandbox isolation, execution policy, tool authorization, and inference guardrails

## Content Type

Lab (hands-on)

## Products & Technologies

**Red Hat products**

- Red Hat OpenShift AI 3.6 — platform baseline and participant-facing experience
- Red Hat OpenShift 4.22 — Kubernetes foundation
- Red Hat OpenShift Sandboxed Containers — VM/kernel isolation boundary for agent execution
- Red Hat build of Agent Sandbox — sandbox lifecycle: `Sandbox`, `SandboxTemplate`, `SandboxClaim`, warm pools
- OpenShell (including the OpenShell Operator and Governed Execution Environment admin UI) — fine-grained agent execution policy covering filesystem, process, and per-binary network controls, plus credential governance and workload identity
- Model Gateway (Red Hat OpenShift AI) — governed inference endpoint
- vLLM (Red Hat OpenShift AI) — serves the tool-calling model, used indirectly: the model is hosted centrally in MaaS and reached through Model Gateway, not deployed in the lab environment
- MCP Gateway (Red Hat OpenShift AI) — enterprise tool connectivity, tool filtering, and token exchange
- MLflow Tracing (Red Hat OpenShift AI) — prompt, LLM call, and tool-execution traces
- EvalHub (Red Hat OpenShift AI) — functional and security evaluation, before/after scorecards
- Guardrails Orchestrator (Red Hat OpenShift AI) — model input/output safety at the inference boundary
- Red Hat Connectivity Link / Kuadrant AuthPolicy — authorization enforcement at the gateway boundary

**Upstream projects and third-party components**

- Kata Containers — kernel isolation underlying OpenShift Sandboxed Containers
- MCP (Model Context Protocol) servers — the enterprise capabilities exposed to the agent
- SPIFFE / SPIRE — cryptographic workload and agent identity
- OpenTelemetry — trace and telemetry interoperability
- Garak — automated adversarial and jailbreak scanning
- Authorino and Open Policy Agent (OPA) — authorization decision enforcement
- NeMo Guardrails — model safety policy
- HashiCorp Vault or Kubernetes Secrets — backing store for governed credentials
- Kubernetes NetworkPolicy — coarse namespace-level egress control as defense in depth
- Gatekeeper or Kyverno — cluster-level policy enforcement

Final component selection may be adjusted based on supported product availability at the time of the event.

## Module Map

| Module | Title | Duration |
|--------|-------|----------|
| 1 | Introduction to AgentOps | 10 min |
| 2 | Explore the agent and establish a baseline | 15 min |
| 3 | Identify unsafe and unintended behavior | 20 min |
| 4 | Apply runtime isolation and policy controls | 30 min |
| 5 | Add identity-aware access controls | 20 min |
| 6 | Re-evaluate and tune the agent | 15 min |
| 7 | AgentOps lifecycle and wrap-up | 10 min |
| — | **Total hands-on** (modules 2–6) | **1 hour 40 min** |
| — | Intro and wrap-up (modules 1, 7) | ~20 min |
| — | **Total lab** | **2 hours** |

The structure follows a single deliberate arc — observe, baseline, attack, contain, authorize, re-evaluate — applied to one unchanged agent, so that every control participants add is measured against the same starting scorecard. Modules 3 through 6 carry roughly 70 percent of hands-on time because that is where the lab differentiates itself: not building another agent, but moving an existing agent from "works" to observable, contained, identity-aware, and policy-governed. Module 4 is the longest because it contains five separate policy exercises (sandbox boundary, filesystem, process, network, credentials) that each re-run an attack from module 3. Modules 1 and 7 are framing rather than hands-on and are intentionally short. Optional advanced challenges — additional Garak profiles, more granular network and tool policy, policy troubleshooting, deeper trace analysis — are offered in module 7 for participants who finish the core path early.

## Difficulty Level

Intermediate

## Environment

**Learner view:** Each participant or team starts with a fully preconfigured Red Hat OpenShift AI namespace and does no installation. On arrival they have: a predeployed AI agent and its browser UI, already running and answering questions; a `SandboxClaim` already allocated from a warm pool so the Kata-backed execution environment is immediately available; the intentionally permissive baseline OpenShell policy loaded (broad filesystem access inside the sandbox, Python/shell/common utilities permitted, general outbound HTTPS allowed, one deliberately over-broad synthetic credential, both read and privileged update MCP tools reachable, minimal user differentiation, basic content safety only); MCP tools connected through MCP Gateway; two preconfigured test identities (Analyst — search knowledge and read tickets; Incident Manager — search, read, and update tickets); synthetic enterprise incident data populated; a planted fake secret file used as the filesystem attack target; an MLflow experiment already created and collecting traces; an EvalHub project with the 8–10 test baseline suite ready to run; and a Garak profile ready to execute. Participants get a browser-based interface and a terminal environment.

Shared services sit outside the per-participant namespace: MCP Gateway, SPIRE, the identity provider, Vault (if used), MLflow and EvalHub, and the OpenShell and Agent Sandbox control planes. Model access is provided via MaaS through Model Gateway — participants do not deploy or train a model.

**Automation needed:** Yes

Automation must provision:

- Per-participant namespace with the agent workload, its UI, and RBAC
- `SandboxTemplate` and a warm pool sized to peak concurrency, with a `SandboxClaim` pre-allocated per participant so sandbox startup never consumes lab time
- The baseline permissive OpenShell policy and Governed Execution Environment, loaded per participant
- The planted synthetic credential and fake secret file inside the sandbox filesystem
- MCP server registrations and MCP Gateway routing, token-exchange configuration, and per-persona authorization policy
- Two test identities per participant in the identity provider, with SPIFFE/SPIRE workload identity for the agent
- Synthetic incident and knowledge-base data seeded into the MCP-backed tools
- MLflow experiment and OpenTelemetry wiring
- EvalHub project with the prebuilt baseline test suite, and the Garak adversarial profile
- Guardrails Orchestrator with a basic content-safety policy
- Coarse NetworkPolicy egress rules, an approved internal test service, and an intentionally unauthorized test endpoint for the network exercise
- A **reset action** that reclaims the current sandbox and restores the starting policy in under a minute. With several Tech Preview components in play, fast recovery of a broken participant environment matters more than making participants repair a bad configuration by hand.

Zero infrastructure installation by participants is a hard requirement.

## Infrastructure Requirements

- **Cloud provider:** Troshka. Not the CNV default — Red Hat OpenShift Sandboxed Containers is the isolation boundary the entire lab rests on, and Kata requires bare metal or nested virtualization.
- **Cluster type:** Multinode. Shared control-plane services plus per-participant namespaces and a Kata warm pool rule out SNO.
- **OCP version:** 4.22. Red Hat build of Agent Sandbox Tech Preview is tied to OCP 4.22 and OpenShift Sandboxed Containers 1.12, so this is above the 4.20 platform minimum.
- **Topology:** Shared cluster. One cluster with a namespace per participant or team. Max concurrent users: 30. MCP Gateway, SPIRE, the identity provider, Vault, MLflow, EvalHub, and the OpenShell and Agent Sandbox control planes are shared services outside the per-participant namespaces.
- **Sizing:** 3 control plane (16 vCPU, 64 GB RAM); 8 workers (32 vCPU, 64 GB RAM, 200 GB disk). Estimated at 30 concurrent participants from roughly 5 vCPU and 10 GB per participant — agent and UI, Kata sandbox VM, and per-participant MCP servers — plus approximately 40 vCPU and 120 GB of shared services, plus warm-pool headroom. Refine once concurrency is fixed.
- **Automation approach:** GitOps (Helm + ArgoCD).
- **AI/MaaS:** MaaS, open-source model tier. No justification required and no GPU nodes in the lab cluster — the model is hosted centrally in Models as a Service, served there by vLLM and reached through Model Gateway. Specific model is TBD; it must be an instruction-following model supporting agentic tool use, exposed through an OpenAI-compatible endpoint. Participants neither deploy nor train a model.
- **External services:**
  - `registry.redhat.io` — Red Hat product images
  - `quay.io` — operator catalogs, Red Hat build images, and all non-GA and Tech Preview components
  - `github.com` — GitOps chart and manifest sources for ArgoCD
  - MaaS model endpoint — the hosted tool-calling model, reached through Model Gateway; hostname TBD

  No runtime pull from Hugging Face: Garak probe data and equivalent test assets are packaged into the GitOps build. The deliberately unauthorized test endpoint used in modules 3 and 4 is a synthetic in-cluster service, not a real internet host, so it is not an external dependency.
- **AAP version:** Not applicable. Ansible Automation Platform is not part of this lab.
- **Non-GA products:** This design carries an unusually heavy non-GA dependency load, and every core capability of the lab depends on at least one of these:
  - Red Hat OpenShift AI 3.6 — GA 19 November 2026, after content development begins
  - OpenShell, including its Operator, Gateway, Supervisor, Sandbox, CLI, and Admin UI — Tech Preview, RHOAI 3.6 EA1/EA2, September–October 2026
  - Red Hat build of Agent Sandbox — Tech Preview, with OCP 4.22 and OpenShift Sandboxed Containers 1.12
  - MCP Gateway — Tech Preview at 3.5; status at 3.6 to be confirmed before content freeze
  - Garak adversarial testing, via TrustyAI and EvalHub — Tech Preview 3.4
  - EvalHub — GA targeted at 3.5; confirm GA status at 3.6

  **Access plan:** All non-GA components are pulled from quay.io. The lab is delivered on Red Hat OpenShift AI 3.6, at which point every non-GA dependency is at minimum Tech Preview, so the images ship as part of the RHOAI 3.6 deployment rather than requiring separate early-access entitlement or a side-channel build.

## Assessment Strategy

Verification is evidence-based rather than solve/validate-button-based: participants confirm each outcome in an MLflow trace or an EvalHub scorecard, which doubles as the lab's teaching mechanism.

| Module | How success is verified |
|--------|--------------------------|
| 1 | Trust-based. Participants ask the agent one business question and locate the resulting MLflow trace; no automated check. |
| 2 | EvalHub baseline scorecard is saved. The agent should score well functionally — the point is that it succeeds because it has too much authority. |
| 3 | Each of the three manual attacks succeeds and the participant locates the corresponding tool invocation, file read, or outbound connection in the MLflow trace. The Garak profile produces findings. |
| 4 | Each attack from module 3 is re-run and now receives an infrastructure-level denial, visible in the trace, while the legitimate workflow still completes. Credential exfiltration returns a reference rather than the real value. |
| 5 | The same prompt, run as Analyst, is rejected by MCP Gateway; run as Incident Manager, it succeeds. A prompt-injection attempt as Analyst still fails, proving authorization is not derived from prompt content. |
| 6 | EvalHub hardened scorecard is compared side by side against the module 2 baseline. Participants then diagnose one deliberately over-restrictive policy from a failing evaluation and its MLflow trace, correct it, and re-run to green. |
| 7 | Trust-based recap; optional advanced challenges are self-directed. |
