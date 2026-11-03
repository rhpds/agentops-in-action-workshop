"""Offline Helm regression checks; run with python3 and PyYAML installed."""
import pathlib
import subprocess
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(chart, *settings, check=True):
    command = ["helm", "template", "test", str(ROOT / chart)]
    for setting in settings:
        command.extend(["--set" if setting == "mcpGateway.enabled=true"
                        else "--set-string", setting])
    result = subprocess.run(command, capture_output=True, text=True)
    if check:
        if result.returncode:
            raise AssertionError(result.stderr)
        return list(yaml.safe_load_all(result.stdout))
    return result


class ProtocolVersions(unittest.TestCase):
    def registrations(self, *settings):
        return [doc for doc in render(
            "tenant-platform", "mcpGateway.enabled=true", "keycloak.host=sso.example.com",
            "attackRunner.sharedNamespace=shared-services", *settings
        ) if doc and doc.get("kind") == "MCPServerRegistration"]

    def test_default_does_not_override_discovery(self):
        registrations = self.registrations()
        self.assertEqual(len(registrations), 3)
        for registration in registrations:
            self.assertNotIn("supportedProtocolVersions", registration["spec"])

    def test_v1_registration_versions(self):
        versions = ["2025-06-18", "2026-07-28"]
        registrations = self.registrations(
            "mcpGateway.apiVersion=mcp.kuadrant.io/v1",
            *[f"mcpGateway.supportedProtocolVersions[{i}]={v}"
              for i, v in enumerate(versions)]
        )
        self.assertEqual(len(registrations), 3)
        for registration in registrations:
            self.assertEqual(registration["spec"]["supportedProtocolVersions"], versions)

    def test_unsupported_crd_fails_closed(self):
        result = render("tenant-platform", "keycloak.host=sso.example.com",
                        "mcpGateway.enabled=true",
                        "attackRunner.sharedNamespace=shared-services",
                        "mcpGateway.supportedProtocolVersions[0]=2025-06-18",
                        check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires mcp.kuadrant.io/v1", result.stderr)

    def test_parent_charts_forward_values(self):
        for chart in ["bootstrap-tenant", "tests/lb1285-tenant-v1"]:
            for versions in [[], ["2025-06-18", "2026-07-28"]]:
                with self.subTest(chart=chart, versions=versions):
                    docs = render(chart, "tenant.username=example",
                                  "secrets.modelApiKey=offline-placeholder",
                                  "secrets.apiServerKey=offline-placeholder",
                                  *[f"platform.mcpSupportedProtocolVersions[{i}]={v}"
                                    for i, v in enumerate(versions)])
                    app = next(d for d in docs if d and
                               d.get("kind") == "Application" and
                               d["metadata"]["name"].endswith("-platform"))
                    params = app["spec"]["source"]["helm"]["parameters"]
                    forwarded = [p for p in params if p["name"].startswith(
                        "mcpGateway.supportedProtocolVersions[")]
                    self.assertEqual(forwarded, [
                        {"name": f"mcpGateway.supportedProtocolVersions[{i}]",
                         "value": v, "forceString": True}
                        for i, v in enumerate(versions)])


if __name__ == "__main__":
    unittest.main()
