# AgentOps in Action: Evaluate, Secure, and Operate Enterprise AI Agents

## Overview

This lab follows the current Showroom content under `content/` as the source of truth. Participants operate *Hermie*, a customized Hermes-based AI assistant for Northgate Water Treatment Works. Hermie can inspect plant telemetry, stop pumps, write reports, read documentation, and use skills and MCP tools. The workshop shows how to keep that assistant useful while tightening what it can do, where it can connect, which tools it can invoke, what files it can write, and what operator input reaches the agent.

Participants start from a working operator console and establish evidence with plant state, saved reports, MLflow traces, attack notifications, and evaluation results. They then put Hermie into an OpenShell sandbox, restore only the network dependencies it needs, narrow Keycloak/MCP Gateway tool roles, add scoped filesystem access for reports, restrict documentation access to safe paths, and finally connect NeMo Guardrails to check operator input before the request reaches Hermie. The lab closes by tying those layers into an AgentOps loop: observe, make a change, take action, evaluate, and continue.

The agent code is not the focus. The focus is the platform and operational controls around a tool-enabled agent: OpenShell sandbox policy, MCP Gateway and Keycloak authorization, scoped network and filesystem permissions, MLflow traces, automated evaluations, attack cases, and guardrails.

## Target Audience

- **Role:** Solution architects, AI platform architects, consultants and services professionals, technical sales specialists, OpenShift AI administrators, platform engineers, and technical leaders advising customers on enterprise AI adoption.
- **Experience level:** Intermediate.
- **What they already know:** Containers and Kubernetes or Red Hat OpenShift fundamentals; generative AI, large language models, and the general concept of AI agents; basic command-line use; and a conceptual understanding of APIs and application permissions.
- **What they do not need to know in advance:** OpenShell, MCP Gateway, Keycloak role mappings, MLflow trace analysis, NeMo Guardrails, or agent sandbox policy authoring. The lab introduces those concepts in the flow of troubleshooting Hermie.

## Prerequisites

- Basic understanding of containers and Kubernetes or Red Hat OpenShift
- Familiarity with generative AI, large language models, and the general concept of AI agents
- Basic command-line experience
- Conceptual understanding of APIs, application permissions, and least privilege

**Can the lab validate these automatically?** No. Prerequisites are knowledge-based and trust-based. All required services are predeployed, and participants complete the lab through the browser console, OpenShift terminal, OpenShell CLI/TUI, Keycloak UI, OpenShift Console, and MLflow links provided in the Showroom experience.

## Learning Objectives

1. Identify operational and security risks in a tool-enabled AI assistant by reviewing plant state, tool calls, traces, logs, reports, attack results, and evaluations.
2. Use OpenShell sandboxing and policy to restrict the agent's network and filesystem access while preserving required workflows.
3. Explain how Keycloak role mappings and MCP Gateway enforcement control which plant tools the operator may use through the agent.
4. Restore required capabilities with least privilege: plant tools, report writes, documentation reads, tracing, and model access.
5. Investigate indirect prompt injection through compromised documentation and installed skills.
6. Add NeMo Guardrails input checks for sensitive contact details and off-topic requests.
7. Distinguish model refusal from enforced runtime, network, filesystem, tool-authorization, and guardrail controls.
8. Apply an AgentOps loop of observe, change, act, evaluate, and continue.

## Content Type

Lab (hands-on)

## Products & Technologies

**Red Hat products and platform components**

- Red Hat OpenShift 4.22 — Kubernetes foundation and participant projects
- Red Hat OpenShift AI 3.5 — participant-facing AI platform services referenced by the current content
- Red Hat build of Agent Sandbox / OpenShell — sandbox, supervisor, gateway, CLI/TUI, and policy enforcement
- MCP Gateway — single gateway for Hermie's plant MCP tools
- MLflow Tracing — request, model, tool, and response evidence
- OpenShift Console and `oc` CLI — environment inspection and configuration changes
- Keycloak — participant realm, users, and tool-role mappings
- NeMo Guardrails — sensitive-data and topic input checks connected to the operator console

**Workshop application components**

- Hermie / Hermes Agent — customized waterplant assistant
- Northgate Water Treatment Works operator console
- Plant telemetry, maintenance, and control MCP tools
- `write-report`, `read-safety-docs`, and handover-related skills
- Waterplant documentation service, including safe `/doc` pages and a compromised bulletin path for the exercise
- Attack and evaluation definitions exposed through the operator console
- MaaS-hosted model endpoint used by Hermie and guardrails checks

## Module Map

| Module | Title | Duration | Objectives | Overview |
|--------|-------|----------|------------|----------|
| 1 | Introduction to AgentOps & Meet Hermie | 20 min | Meet Hermie, identify the starting architecture, run useful plant operations, find evidence in MLflow, and establish baseline attack/evaluation behavior. | Participants use the operator console to ask plant questions, stop one pump, write a report, inspect traces, try broad web/file access, and run baseline attacks and evaluations. |
| 2 | Sandbox the Agent | 20 min | Explain sandboxing, create sandboxed Hermie, restore required network dependencies, and verify broad access remains blocked. | Participants create an OpenShell sandbox, point the UI at it, inspect default-deny failures, and add scoped rules for Keycloak, MCP Gateway, the model endpoint, and MLflow. |
| 3 | Let the Agent Use Its Tools | 15 min | Trace unsafe tool calls, narrow operator tool roles, and verify legitimate plant tools still work. | Participants reproduce whole-plant shutdown and configuration-dump attacks, remove the corresponding Keycloak tool roles, and confirm telemetry plus individual pump control still work. |
| 4 | Let the Agent Write Files | 20 min | Diagnose report-write failures, add scoped filesystem access, and explain the limits of broad write permissions. | Participants inspect the write-report skill, recreate Hermie with /reports writable, verify report generation, and review accidental deletion and instruction-poisoning risks. |
| 5 | Let the Agent Reach the Docs Website | 20 min | Restore documentation reads, investigate indirect prompt injection, and constrain documentation access by method and path. | Participants allow the docs service, observe a compromised bulletin redirect, replace broad host access with GET /doc and GET /doc/**, and verify /attack/override is denied. |
| 6 | Check What Goes In and Comes Out | 20 min | Inspect and enable NeMo Guardrails input checks, verify sensitive-data and topic blocks, and preserve useful plant workflows. | Participants test poisoned skills, synthetic contact details, and mixed travel requests, connect the console to NeMo Guardrails, and re-check operational prompts and plant queries. |
| 7 | Keep Hermie Working Safely | 5 min | Map each control to its responsibility and describe the continuing AgentOps loop. | Participants recap what each layer contributed, keep remaining gaps visible, and carry forward observe-change-act-evaluate operations. |

The Publishing House spec keeps the lab at **2 hours total** (120 min). The flow is deliberately operational. Module 1 establishes Hermie's useful baseline and over-broad access. Module 2 puts Hermie in a sandbox and restores required network dependencies one at a time. Module 3 narrows plant-tool access through Keycloak and MCP Gateway. Module 4 restores report writing with scoped filesystem access and shows the limits of broad write permission. Module 5 restores documentation reads and then narrows access to safe documentation paths after a compromised bulletin redirects to an attack endpoint. Module 6 adds NeMo Guardrails checks on operator input and demonstrates both their value and limits. Module 7 summarizes the controls and the ongoing AgentOps loop.

## Difficulty Level

Intermediate

## Environment

**Learner view:** Each participant starts with a dedicated `{user}-agentops` namespace and a predeployed waterplant environment. The operator console is reachable through the Showroom URL list and includes plant status panels, chat with Hermie, attack controls, evaluation controls, reset, and MLflow trace links. The participant also has an OpenShift terminal, OpenShift Console access, Keycloak admin access for their realm, and an OpenShell Term tab.

The environment includes:

- Water-plant UI / operator console
- Baseline Hermie agent and sandboxable Hermes image
- OpenShell gateway and Hermes bridge
- Participant-specific Keycloak realm and operator user
- MCP Gateway with telemetry, maintenance, and control MCP tools
- MLflow tracing and relay
- Waterplant documentation service
- NeMo Guardrails service and configuration ConfigMap
- Attack definitions, evaluation definitions, reset behavior, and supporting plant state
- MaaS-hosted model endpoint

**Automation needed:** Yes. Automation must provision the participant namespace, operator console, Hermie/Hermes components, OpenShell gateway and bridge, MCP Gateway and plant tools, Keycloak realm and roles, MLflow wiring, documentation service, NeMo Guardrails, attack/evaluation definitions, reset support, routes, RBAC, and Showroom variables.

Zero installation by participants is a hard requirement. Participants configure and tune the already-provisioned environment rather than deploying the platform from scratch.

## Infrastructure Requirements

- **Platform:** Red Hat OpenShift shared cluster with one namespace per participant/team.
- **Topology:** Shared cluster, max concurrent users 30.
- **OCP version:** 4.22, matching the current Showroom content.
- **OpenShift AI version:** 3.5 in the current Showroom text; update the content and this spec together if the delivered environment moves to another version.
- **Automation approach:** GitOps/ArgoCD and Helm-based workshop deployment.
- **AI/MaaS:** MaaS-hosted model endpoint; no participant-deployed GPU model is required.
- **External services:** Red Hat and Quay registries for images, GitHub for GitOps sources, and the MaaS model endpoint. Runtime workshop exercises use in-cluster services for plant tools, docs, guardrails, tracing, attacks, and evaluations.
- **Reset/recovery:** The operator console reset and automation must restore plant state, reports, skills, Hermie instructions, and other lab state quickly enough for participants to recover from misconfiguration.

## Assessment Strategy

Verification is evidence-based rather than solve-button-based. Participants confirm outcomes through the operator console, plant panels, saved reports, OpenShell logs, Keycloak role mappings, MLflow traces, guardrail verdicts, attack notifications, and evaluation results.

| Module | How success is verified |
|--------|--------------------------|
| 1 | Hermie answers plant questions, stops an individual pump, writes a report, demonstrates broad access, records traces, and produces baseline attack/evaluation results. |
| 2 | Sandboxed Hermie runs through the bridge, plant queries work again after scoped network rules, MLflow traces are restored, and unnecessary web/file/report access remains blocked. |
| 3 | The whole-plant shutdown and configuration-dump tools are identified in traces, corresponding Keycloak roles are removed from `operator`, attacks are blocked, and telemetry plus individual pump control still work. |
| 4 | `/reports` write access is restored through sandbox filesystem policy, report generation succeeds, and participants can explain why broad write access can still permit deletion or instruction poisoning. |
| 5 | The safety documentation lookup works, the compromised bulletin redirect is identified, broad docs access is replaced with `GET /doc` and `GET /doc/**`, `/attack/override` is denied, and legitimate docs still work. |
| 6 | NeMo Guardrails blocks synthetic email/phone input and the mixed Berlin travel request, allows operational prompts, keeps plant queries working, and participants can explain what guardrails do not cover. |
| 7 | Participants can map each layer to its responsibility and describe the continuing AgentOps loop with the remaining gaps visible. |
