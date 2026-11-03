# LB1285 upstream MCP tenant fixture

Copied from `automation/gitops/bootstrap-tenant` at `f8d94b619b867eed0609f213f551f5f8ffba7a0f` (PRs #68 and #69).
The only rendering change forwards `mcpGateway.apiVersion=mcp.kuadrant.io/v1` to the tenant-platform Application.
Use only with the pinned LB1285 upstream-development MCP controller. Set gitops.targetRevision to the immutable fixture commit so child charts include the deletion fixes.
The production bootstrap chart and its default v1alpha1 behavior are unchanged.
