# LB1285 development MCP deletion regression fixture

Test-only bootstrap for one authorized LB1285 AWS deployment/destruction cycle.
This is not a production operator recommendation or a functional workshop test.

The bootstrap files are copied from `rhpds/agentops-in-action-workshop`, tag
`rh1-2027-aws-test-snapshot-20261022-26d2aba302ef`, directory
`automation/gitops/bootstrap-infra`. They deliberately preserve the failed run's
baseline rather than advance the rest of the workshop to current main.

Changes from that snapshot:

- Disable `operators.mcpGatewayOperator.enabled` to prevent two controllers
  managing the same APIs. RHCL and the remaining operator pins are unchanged.
- Add `templates/mcp-development.yaml`: a cascading Argo CD Application installing
  the upstream chart at commit `3ba95b69effe22e47552d64e7339f429322a4a18` with
  digest-pinned controller and broker images from that build. The commit contains
  [Kuadrant/mcp-gateway#1574](https://github.com/Kuadrant/mcp-gateway/pull/1574),
  the HTTPRoute status ownership/deletion fix.
- Disable upstream Gateway and MCPGatewayExtension creation: the original tenant
  charts still own those resources. Install the upstream CRDs using server-side
  apply and wait for the child Application to be synced and healthy before the
  bootstrap completes. The readiness Job has no automatic retry.

Keep the tenant and content snapshot pins unchanged. Point only the backing
catalog item's `test.yaml` bootstrap URL/revision/path to this fixture's reviewed
commit. Do not use this fixture against an existing OLM-managed installation.
Retire the tenant and verify absence before retiring the backing cluster, so the
MCP controller remains available to handle tenant finalizers.

The separate historical bootstrap-removal `resources` lookup failure is not fixed
here and must remain independently visible if it recurs.
