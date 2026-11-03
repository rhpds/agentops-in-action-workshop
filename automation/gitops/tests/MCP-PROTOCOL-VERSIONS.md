# MCP registration protocol override

The v1 gateway broker filters upstreams by their supported protocol versions.
An upstream advertising only a 2026 version is omitted from the stateful route
used by the Hermes readiness probe's 2025-06-18 client. A registration can be
Ready while its tools remain unavailable to that client.

Set `platform.mcpSupportedProtocolVersions` on bootstrap-tenant (or the LB1285
v1 test fixture). It forwards the list as indexed Helm parameters to
`mcpGateway.supportedProtocolVersions` in tenant-platform, which writes it to
each of the three MCPServerRegistrations. Both defaults are empty: automatic
discovery remains unchanged. A non-empty list requires `mcp.kuadrant.io/v1`.

This is a compatibility declaration, not protocol translation. Verify every
listed version against every backend before enabling it. The override applies
to all three registrations and must not be used if their support differs.

Before accepting the LB1285 override, verify backend negotiation, then tools
visibility through the gateway, Hermes readiness and Synced/Healthy tenant
Argo applications. Offline rendering does not establish runtime compatibility.
