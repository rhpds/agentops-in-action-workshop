#!/usr/bin/env python3
"""Keeps Hermes's MCP Gateway OAuth token fresh from inside the sandbox.

Adapted from the normal Hermes chart's token-refresher CronJob
(chart/templates/token-refresher.yaml in the cai-krew hermes-container repo),
but runs as an in-process background loop instead of an external CronJob +
`oc exec` — this adapter already runs inside the sandbox, so there's no need
for the extra pods/exec RBAC or a second container image.

Fetches a token via the OAuth 2.0 Resource Owner Password Credentials grant,
authenticating as the realm's `operator` user through the public `mcp-gateway`
client (directAccessGrantsEnabled) — the same identity and tool-role scope a
human operator gets, deliberately, not Hermes's own `wp-dev/hermes-agent`
service-account identity (which has full tool access, including tools the
operator persona is withheld from — see hermes/README.md's "no per-user
attribution" gap). Writes the token to
$HERMES_HOME/mcp-tokens/<server_name>.json. Hermes picks up the refreshed
token automatically via its built-in disk-watch
(MCPOAuthManager.invalidate_if_disk_changed) — no restart needed.

Run once synchronously (so the token file exists before Hermes' first MCP
handshake), then call again on an interval well inside the realm's
accessTokenLifespan (default 1800s in waterplant-realm-template.yaml) — the
caller (.sandbox-init.sh / the setup script) loops this with `sleep`.

stdlib only.

Required env vars: MCP_CLIENT_ID (the public client, "mcp-gateway"),
MCP_USERNAME, MCP_PASSWORD, MCP_TOKEN_URL.
Optional: MCP_SERVER_NAME (default "gateway", must match config.yaml's
mcp_servers key), HERMES_HOME (default /sandbox/.hermes).
"""

from __future__ import annotations

import json
import os
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def _log(*args: object) -> None:
    print(*args, file=sys.stderr, flush=True)


def refresh_once() -> None:
    keycloak_url = os.environ["MCP_TOKEN_URL"]
    client_id = os.environ["MCP_CLIENT_ID"]
    username = os.environ["MCP_USERNAME"]
    password = os.environ["MCP_PASSWORD"]
    server_name = os.environ.get("MCP_SERVER_NAME", "gateway")

    data = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
        }
    ).encode()

    ctx = ssl.create_default_context()

    req = urllib.request.Request(keycloak_url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            resp = json.loads(r.read())
    except urllib.error.URLError as exc:
        _log(f"ERROR: Keycloak request failed: {exc}")
        raise

    if "access_token" not in resp:
        _log(f"ERROR: unexpected Keycloak response: {resp}")
        raise RuntimeError("no access_token in Keycloak response")

    # ------------------------------------------------------------------
    # Agent identity: exchange the operator's token for one that names the
    # agent as well (RFC 8693 standard token exchange, Keycloak >= 26.2).
    #
    # Without this the agent IS the operator: the token above carries
    # azp=mcp-gateway -- the public client every caller in the realm shares --
    # and, because the realm import replaces Keycloak's built-in client
    # scopes, no sub and no aud either. Measured on RHBK 26.4.18: claims were
    # [azp exp groups iat iss jti resource_access scope sid typ]. Eighteen
    # permissions with no principal attached.
    #
    # After the exchange the same call carries sub + preferred_username (the
    # operator), azp=hermes-agent (the software acting for them) and aud
    # scoped to the gateway, with resource_access unchanged. tenant-policy's
    # mcp-authz-policy can then require BOTH.
    #
    # Env-gated: with MCP_EXCHANGE_CLIENT_ID unset this behaves exactly as it
    # always did, so a tenant without the realm delta is unaffected.
    #
    # FAILS CLOSED on purpose. A silent fall back to the raw operator token
    # would de-identify the agent at exactly the moment the policy starts
    # requiring identity, and the symptom would surface as the misleading
    # "network issue or service outage" Hermes already reports for a 403.
    #
    # Two prerequisites, both of which fail confusingly if missed:
    #   * the operator token must carry the exchange client in `aud`, or
    #     Keycloak answers 400 "Client is not within the token audience";
    #   * the exchange client needs the realm's `roles` scope, or the
    #     exchanged token has no resource_access and every tool call fails
    #     the FIRST authz predicate, which reads like a policy bug.
    # See docs/agent-identity/09-implementation-plan.md Stage 1.
    # ------------------------------------------------------------------
    exchange_client = os.environ.get("MCP_EXCHANGE_CLIENT_ID", "").strip()
    if exchange_client:
        exchange_secret = os.environ.get("MCP_EXCHANGE_CLIENT_SECRET", "")
        xdata = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": exchange_client,
                "client_secret": exchange_secret,
                "subject_token": resp["access_token"],
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                # Deliberately NO `audience`: requesting one re-scopes which
                # client's protocol mappers apply and can drop resource_access.
                # Per-hop audience comes from a fixed mapper on the client.
            }
        ).encode()
        xreq = urllib.request.Request(keycloak_url, data=xdata, method="POST")
        try:
            with urllib.request.urlopen(xreq, context=ctx, timeout=15) as r:
                xresp = json.loads(r.read())
        except urllib.error.URLError as exc:
            _log(f"ERROR: token exchange as {exchange_client} failed: {exc}")
            raise
        if "access_token" not in xresp:
            _log(f"ERROR: unexpected exchange response: {xresp}")
            raise RuntimeError("no access_token in token-exchange response")
        _log(f"exchanged operator token for one acting as {exchange_client}")
        resp = xresp

    expires_in = resp.get("expires_in", 1800)
    token_data = {
        "access_token": resp["access_token"],
        "token_type": resp.get("token_type", "bearer"),
        "expires_in": expires_in,
        "expires_at": time.time() + expires_in,
    }

    hermes_home = os.environ.get("HERMES_HOME", "/sandbox/.hermes")
    token_dir = os.path.join(hermes_home, "mcp-tokens")
    os.makedirs(token_dir, mode=0o700, exist_ok=True)
    token_path = os.path.join(token_dir, f"{server_name}.json")

    tmp = token_path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(token_data, f, indent=2)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, token_path)
    _log(
        f"token written to {token_path} "
        f"(expires_in={expires_in}s, {expires_in // 60}min)"
    )


def main() -> None:
    # One-shot mode: called by the setup script to seed the initial token.
    # Loop mode: `--loop <seconds>` re-runs on an interval, tolerating
    # transient Keycloak failures (retries next cycle rather than exiting).
    if len(sys.argv) >= 3 and sys.argv[1] == "--loop":
        interval = float(sys.argv[2])
        while True:
            try:
                refresh_once()
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                _log(f"refresh failed, will retry in {interval}s: {exc}")
            time.sleep(interval)
    else:
        refresh_once()


if __name__ == "__main__":
    main()
